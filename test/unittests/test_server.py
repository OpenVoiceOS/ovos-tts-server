# Licensed under the Apache License, Version 2.0
"""Unit tests for the base ovos-tts-server FastAPI app.

Uses a lightweight FakeEngine that mimics TTSEngineWrapper so the tests
exercise routes and parameter wiring without loading any OVOS TTS plugin.
"""
import asyncio
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from ovos_tts_server import create_app


class FakeEngine:
    """Stand-in for TTSEngineWrapper used by create_app(tts_engine)."""

    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def __init__(self):
        self.last_call: Optional[Tuple[str, dict]] = None

        class _InnerEngine:
            config = {"model": "fakemodel", "voice": "fakevoice"}

        self.engine = _InnerEngine()

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        self.last_call = (utterance, kwargs)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)
        return tmp.name, None


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def client(engine: FakeEngine) -> TestClient:
    return TestClient(create_app(engine))


class TestStatusEndpoint:
    def test_returns_ok_and_engine_metadata(self, client, engine):
        r = client.get("/status")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "status": "ok",
            "plugin": engine.plugin_name,
            "langs": engine.langs,
            "default_lang": engine.lang,
            "default_model": "fakemodel",
            "default_voice": "fakevoice",
        }

    def test_missing_engine_config_keys_yield_none(self, client, engine):
        engine.engine.config = {}
        r = client.get("/status")
        body = r.json()
        assert body["default_model"] is None
        assert body["default_voice"] is None

    def test_engine_without_config_attr_defaults_to_empty(self, engine):
        engine.engine = type("E", (), {})()  # plain object, no `config` attr
        client = TestClient(create_app(engine))
        r = client.get("/status")
        body = r.json()
        assert body["default_model"] is None
        assert body["default_voice"] is None


class TestLegacySynthesize:
    def test_returns_audio_file(self, client, engine):
        r = client.get("/synthesize/hello%20world")
        assert r.status_code == 200
        assert engine.last_call[0] == "hello world"

    def test_forwards_query_params(self, client, engine):
        r = client.get("/synthesize/hi", params={"voice": "v1", "lang": "de-de"})
        assert r.status_code == 200
        utterance, kwargs = engine.last_call
        assert utterance == "hi"
        assert kwargs["voice"] == "v1"
        assert kwargs["lang"] == "de-de"


class TestV2Synthesize:
    def test_returns_audio_when_utterance_given(self, client, engine):
        r = client.get("/v2/synthesize", params={"utterance": "hi"})
        assert r.status_code == 200
        assert engine.last_call[0] == "hi"

    def test_missing_utterance_returns_400(self, client):
        r = client.get("/v2/synthesize")
        assert r.status_code == 400
        assert r.json() == {"error": "Missing utterance"}

    def test_forwards_extra_params_without_utterance_leakage(self, client, engine):
        r = client.get(
            "/v2/synthesize",
            params={"utterance": "hi", "voice": "v1", "lang": "en-us"},
        )
        assert r.status_code == 200
        utterance, kwargs = engine.last_call
        assert utterance == "hi"
        assert "utterance" not in kwargs
        assert kwargs["voice"] == "v1"
        assert kwargs["lang"] == "en-us"


class LoopDrivingEngine(FakeEngine):
    """Mimics a plugin using opm's base streaming ``get_tts``.

    opm's ``TTS.get_tts`` wraps async streaming synthesis into sync usage by
    calling ``asyncio.new_event_loop().run_until_complete(...)``. Python raises
    ``RuntimeError: Cannot run the event loop while another loop is running``
    whenever that runs on a thread that already has a running loop — which is
    exactly what happens if an ``async def`` endpoint calls ``synthesize``
    directly on the request event loop. Running the blocking call in a worker
    thread (run_in_threadpool) is what keeps this working.
    """

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        async def _gen():
            return None

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_gen())
        finally:
            loop.close()
        return super().synthesize(utterance, **kwargs)


class TestNestedEventLoopRegression:
    """Guards against the nested-loop 500 on the async /synthesize endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(create_app(LoopDrivingEngine()))

    def test_legacy_synthesize_survives_loop_driving_plugin(self, client):
        r = client.get("/synthesize/hello")
        assert r.status_code == 200

    def test_v2_synthesize_survives_loop_driving_plugin(self, client):
        r = client.get("/v2/synthesize", params={"utterance": "hello"})
        assert r.status_code == 200


class TestCORS:
    def test_cors_headers_present_on_preflight(self, client):
        r = client.options(
            "/status",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "https://example.com"
