# Licensed under the Apache License, Version 2.0
"""Regression tests: the event loop must stay free during synthesis.

``synthesize()`` is a blocking call. If a request handler awaits it directly
on the event loop (instead of running it in a worker thread), the whole
server stalls for the duration of synthesis: concurrent synthesis requests
serialize instead of overlapping, and unrelated endpoints like ``/status``
cannot be answered until the in-flight synthesis finishes.

This was observed on a live deployment: during a single cold-voice
synthesis, ``GET /status`` did not respond within 30s (repeated 3x) while
container CPU sat at 0.59%, proving the event loop -- not the CPU -- was the
bottleneck.

These tests use a real concurrent client (httpx.AsyncClient over
ASGITransport) and asyncio.gather so a still-blocking handler actually fails
the assertions, rather than a sync TestClient which cannot observe
event-loop stalls.

Tests are plain sync functions that drive their own asyncio.run(...) so
they do not depend on the pytest-asyncio plugin being autoloaded (this repo
runs pytest with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 to avoid clashing
plugins in the shared venv).
"""
import asyncio
import tempfile
import threading
import time
import wave
from typing import List, Optional, Tuple
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from ovos_tts_server import create_app
from ovos_tts_server.routers import elevenlabs as elevenlabs_mod
from ovos_tts_server.routers.elevenlabs import make_elevenlabs_router

SLEEP_SECONDS = 2.0


def run_async(coro_fn, *args, **kwargs):
    """Run an async test body without relying on the pytest-asyncio plugin."""
    return asyncio.run(coro_fn(*args, **kwargs))


def _write_wav(path: str) -> None:
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)


class SlowEngine:
    """Stand-in for TTSEngineWrapper whose synthesize() blocks for a while.

    Mimics a real cold-voice synthesis: CPU-cheap but wall-clock slow
    (e.g. waiting on a model load or a subprocess), which is exactly the
    shape that exposes an event-loop stall.
    """

    plugin_name: str = "slow-fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us"]
    voices: List[str] = ["voice1"]

    def __init__(self, sleep_seconds: float = SLEEP_SECONDS):
        self.sleep_seconds = sleep_seconds
        self.calls: List[Tuple[str, dict, float]] = []

        class _InnerEngine:
            config = {"model": "fakemodel", "voice": "fakevoice"}

        self.engine = _InnerEngine()

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        start = time.monotonic()
        time.sleep(self.sleep_seconds)  # blocking, deliberately not asyncio.sleep
        self.calls.append((utterance, kwargs, start))
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        _write_wav(tmp.name)
        return tmp.name, None


@pytest.fixture
def engine() -> SlowEngine:
    return SlowEngine()


class TestServerStaysResponsiveDuringSynthesis:
    """The /v2/synthesize and legacy /synthesize handlers must not block
    the event loop -- other requests must be served while synthesis runs.
    """

    def test_status_answers_promptly_during_synthesis(self, engine):
        async def _run():
            app = create_app(engine)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                synth_task = asyncio.create_task(
                    client.get("/v2/synthesize", params={"utterance": "hello"})
                )
                # Give the synth request a head start so it is in flight.
                await asyncio.sleep(0.2)

                start = time.monotonic()
                status_resp = await client.get("/status")
                elapsed = time.monotonic() - start

                synth_resp = await synth_task
            return status_resp, synth_resp, elapsed

        status_resp, synth_resp, elapsed = run_async(_run)

        assert status_resp.status_code == 200
        assert synth_resp.status_code == 200
        # If the loop were blocked by synthesize(), /status would only
        # answer after the ~2s sleep finished.
        assert elapsed < SLEEP_SECONDS / 2, (
            f"/status took {elapsed:.2f}s while synthesis was in flight -- "
            "the event loop is blocked"
        )

    def test_legacy_synthesize_does_not_block_status(self, engine):
        async def _run():
            app = create_app(engine)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                synth_task = asyncio.create_task(client.get("/synthesize/hello"))
                await asyncio.sleep(0.2)

                start = time.monotonic()
                status_resp = await client.get("/status")
                elapsed = time.monotonic() - start

                await synth_task
            return status_resp, elapsed

        status_resp, elapsed = run_async(_run)

        assert status_resp.status_code == 200
        assert elapsed < SLEEP_SECONDS / 2

    def test_two_concurrent_synth_requests_overlap(self, engine):
        """Two synthesis calls should run concurrently, not serialize.

        With a blocking event loop, request B's call to synthesize() cannot
        even start until request A's synthesize() call returns, so B's
        start time would be >= A's finish time. With the fix, both worker
        threads run the blocking call in parallel, so B starts before A
        finishes.
        """
        async def _run():
            app = create_app(engine)
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                overall_start = time.monotonic()
                await asyncio.gather(
                    client.get("/v2/synthesize", params={"utterance": "a"}),
                    client.get("/v2/synthesize", params={"utterance": "b"}),
                )
                overall_elapsed = time.monotonic() - overall_start
            return overall_elapsed

        overall_elapsed = run_async(_run)

        # Serialized: ~2 * SLEEP_SECONDS. Overlapped: ~SLEEP_SECONDS. Since
        # overall_elapsed can never go below SLEEP_SECONDS, comparing against
        # a multiple of SLEEP_SECONDS leaves only ~1.0s of headroom on a
        # shared CI runner. Assert on the discriminating quantity instead:
        # overlapped ~= 0 extra seconds, serialized ~= +SLEEP_SECONDS extra.
        assert overall_elapsed - SLEEP_SECONDS < 0.5, (
            f"two concurrent synth requests took {overall_elapsed:.2f}s -- "
            "they serialized instead of overlapping"
        )
        assert len(engine.calls) == 2
        start_a, start_b = sorted(c[2] for c in engine.calls)
        # B must start before A finishes (A's start + sleep_seconds).
        assert start_b < start_a + engine.sleep_seconds


class TestVendorRouterStaysResponsiveDuringSynthesis:
    """Same property, exercised through a vendor-compat router.

    ElevenLabs HTTP handlers are declared as plain ``def``, which FastAPI
    runs in a threadpool automatically -- but the websocket streaming
    handler contains a nested ``async def generate()`` that must explicitly
    hand the blocking call off to a worker thread, or it stalls the socket
    loop.
    """

    @pytest.fixture
    def app(self, engine):
        app = FastAPI()
        app.include_router(make_elevenlabs_router(engine))
        return app

    def test_http_tts_endpoint_requests_overlap(self, app, engine):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                overall_start = time.monotonic()
                await asyncio.gather(
                    client.post(
                        "/elevenlabs/v1/text-to-speech/default",
                        json={"text": "hello world"},
                    ),
                    client.post(
                        "/elevenlabs/v1/text-to-speech/default",
                        json={"text": "second call"},
                    ),
                )
                overall_elapsed = time.monotonic() - overall_start
            return overall_elapsed

        overall_elapsed = run_async(_run)

        assert overall_elapsed - SLEEP_SECONDS < 0.5, (
            f"two concurrent elevenlabs requests took {overall_elapsed:.2f}s "
            "-- they serialized instead of overlapping"
        )

    def test_stream_input_websocket_does_not_block_concurrent_http_call(self, engine):
        """The websocket generate() must not stall a concurrent HTTP request
        served by the same app/event loop.

        ``with TestClient(app) as client:`` (entering the client itself,
        not just a single ``websocket_connect()``) keeps ONE anyio portal
        -- and therefore one shared event loop -- alive for every call made
        inside the block. A plain ``client.post(...)`` made outside such a
        block gets its own throwaway portal/loop and would never observe a
        stall on the websocket's loop, so it would not be a valid
        regression test; calls must share the portal for this to prove
        anything.
        """
        from fastapi.testclient import TestClient

        full_app = FastAPI()
        full_app.include_router(make_elevenlabs_router(engine))

        results = {}

        with TestClient(full_app) as client:
            def do_http_call():
                time.sleep(0.2)  # let the websocket generation start first
                start = time.monotonic()
                resp = client.post(
                    "/elevenlabs/v1/text-to-speech/default",
                    json={"text": "concurrent http call"},
                )
                results["elapsed"] = time.monotonic() - start
                results["status_code"] = resp.status_code

            thread = threading.Thread(target=do_http_call)
            thread.start()

            with client.websocket_connect(
                    "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
                ws.send_json({"text": " "})
                ws.send_json({"text": "hello"})
                ws.send_json({"text": ""})
                while True:
                    frame = ws.receive_json()
                    if frame["isFinal"]:
                        break

            thread.join()

        assert results["status_code"] == 200
        assert results["elapsed"] < SLEEP_SECONDS * 1.5, (
            f"concurrent HTTP call took {results['elapsed']:.2f}s while the "
            "websocket's synthesize() was in flight -- the event loop is "
            "blocked"
        )

    def test_stream_input_encode_audio_does_not_block_concurrent_http_call(self, engine):
        """The websocket generate() must not stall on a slow encode_audio()
        call either -- not just a slow synthesize() call.

        The default ``stream-input`` output_format is
        ``DEFAULT_OUTPUT_FORMAT`` ("mp3_44100_128"), which drives a real
        pydub/ffmpeg mp3 export inside ``encode_audio``. A 100-frame test wav
        makes that export essentially free, which would let a regression
        where ``encode_audio`` runs inline on the event loop slip past
        ``test_stream_input_websocket_does_not_block_concurrent_http_call``
        undetected. Here ``engine.synthesize`` is fast (sleep_seconds=0) and
        ``encode_audio`` is patched to block for SLEEP_SECONDS, isolating the
        encode step as the only possible source of a stall.
        """
        from fastapi.testclient import TestClient

        fast_engine = type(engine)(sleep_seconds=0.0)

        full_app = FastAPI()
        full_app.include_router(make_elevenlabs_router(fast_engine))

        def _slow_encode_audio(*args, **kwargs):
            time.sleep(SLEEP_SECONDS)  # blocking, deliberately not asyncio.sleep
            return b"\x00" * 16, "audio/mpeg"

        results = {}

        with patch.object(elevenlabs_mod, "encode_audio", side_effect=_slow_encode_audio):
            with TestClient(full_app) as client:
                def do_http_call():
                    time.sleep(0.2)  # let the websocket generation start first
                    start = time.monotonic()
                    resp = client.post(
                        "/elevenlabs/v1/text-to-speech/default",
                        json={"text": "concurrent http call"},
                    )
                    results["elapsed"] = time.monotonic() - start
                    results["status_code"] = resp.status_code

                thread = threading.Thread(target=do_http_call)
                thread.start()

                with client.websocket_connect(
                        "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
                    ws.send_json({"text": " "})
                    ws.send_json({"text": "hello"})
                    ws.send_json({"text": ""})
                    while True:
                        frame = ws.receive_json()
                        if frame["isFinal"]:
                            break

                thread.join()

        assert results["status_code"] == 200
        assert results["elapsed"] < SLEEP_SECONDS * 1.5, (
            f"concurrent HTTP call took {results['elapsed']:.2f}s while the "
            "websocket's encode_audio() was in flight -- the event loop is "
            "blocked"
        )
