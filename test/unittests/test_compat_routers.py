# Licensed under the Apache License, Version 2.0
"""Unit tests for TTS server compatibility routers.

Uses a lightweight mock engine to avoid loading any OVOS TTS plugin.

All compat routers are mounted under a named prefix (e.g. /elevenlabs, /openai)
to avoid path conflicts when all routers are registered in the same FastAPI app.
"""
import base64
import os
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeEngine:
    """Mock TTSEngineWrapper for testing routers without a real plugin."""

    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        """Write a minimal WAV and return its path."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)
        return tmp.name, None


@pytest.fixture(scope="module")
def engine():
    """Provide a shared FakeEngine instance."""
    return FakeEngine()

def _make_app(engine) -> FastAPI:
    """Build a FastAPI app with the compat routers exercised here."""
    from ovos_tts_server.routers.elevenlabs import make_elevenlabs_router
    from ovos_tts_server.routers.marytts import (
        make_marytts_router,
        make_marytts_root_router,
    )

    app = FastAPI()
    app.include_router(make_elevenlabs_router(engine))
    app.include_router(make_marytts_router(engine))
    app.include_router(make_marytts_root_router(engine))
    return app


@pytest.fixture(scope="module")
def client(engine):
    """Return a TestClient wired to the compat router app."""
    app = _make_app(engine)
    return TestClient(app)


# ---------------------------------------------------------------------------
# ElevenLabs  (prefix: /elevenlabs)
# ---------------------------------------------------------------------------

class TestElevenLabsRouter:
    def test_list_voices_returns_voices(self, client):
        resp = client.get("/elevenlabs/v1/voices")
        assert resp.status_code == 200
        body = resp.json()
        assert "voices" in body
        assert len(body["voices"]) >= 1
        assert "voice_id" in body["voices"][0]
        assert "name" in body["voices"][0]

    def test_list_voices_api_key_ignored(self, client):
        resp = client.get("/elevenlabs/v1/voices", headers={"xi-api-key": "fake-key"})
        assert resp.status_code == 200

    def test_list_models(self, client):
        resp = client.get("/elevenlabs/v1/models")
        assert resp.status_code == 200
        models = resp.json()
        assert isinstance(models, list)
        assert len(models) >= 1
        assert models[0]["model_id"] == "fake-tts"

    def test_tts_default_voice(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/default",
            json={"text": "hello world"},
        )
        assert resp.status_code == 200

    def test_tts_named_voice(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/voice1",
            json={"text": "test"},
        )
        assert resp.status_code == 200

    def test_tts_output_format_mp3(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/default?output_format=mp3_44100_128",
            json={"text": "test"},
        )
        assert resp.status_code == 200

    def test_tts_empty_text_rejected(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/default",
            json={"text": ""},
        )
        assert resp.status_code == 422

    def test_tts_voice_settings_accepted(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/default",
            json={"text": "hello", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# MaryTTS  (prefix: /marytts + root aliases)
# ---------------------------------------------------------------------------

class TestMaryTTSRouter:
    def test_locales_returns_plain_text(self, client):
        r = client.get("/marytts/locales")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        assert "en-us" in r.text
        assert "de-de" in r.text

    def test_voices_returns_plain_text(self, client):
        r = client.get("/marytts/voices")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        # FakeEngine.voices=['voice1','voice2'], one line per voice/lang
        # pair in MaryTTS wire format: "<voice> <lang> <gender> <plugin>"
        assert "voice1" in r.text
        assert "voice2" in r.text
        assert "fake-tts" in r.text

    def test_process_get_returns_wav(self, client):
        r = client.get("/marytts/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"

    def test_process_post_returns_wav(self, client):
        r = client.post("/marytts/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200

    def test_process_requires_input_text(self, client):
        r = client.get("/marytts/process")
        assert r.status_code == 422

    def test_process_accepts_locale_and_voice(self, client):
        r = client.get(
            "/marytts/process",
            params={"INPUT_TEXT": "hi", "LOCALE": "en_US", "VOICE": "some_voice"},
        )
        assert r.status_code == 200


class TestMaryTTSRootAlias:
    """Bare-path aliases for legacy assistive-tech clients."""

    def test_root_locales(self, client):
        r = client.get("/locales")
        assert r.status_code == 200
        assert "en-us" in r.text

    def test_root_voices(self, client):
        r = client.get("/voices")
        assert r.status_code == 200
        assert "voice1" in r.text

    def test_root_process_get(self, client):
        r = client.get("/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"

    def test_root_process_post(self, client):
        r = client.post("/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Cartesia  (prefix: /cartesia)
# ---------------------------------------------------------------------------


def _make_cartesia_app(engine) -> FastAPI:
    from ovos_tts_server.routers.cartesia import make_cartesia_router
    app = FastAPI()
    app.include_router(make_cartesia_router(engine))
    return app


@pytest.fixture(scope="module")
def cartesia_client(engine):
    return TestClient(_make_cartesia_app(engine))


class TestCartesiaRouter:
    def test_tts_bytes_success(self, cartesia_client):
        resp = cartesia_client.post(
            "/cartesia/tts/bytes",
            json={"model_id": "sonic-english", "transcript": "hello world"},
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0

    def test_tts_bytes_empty_transcript_rejected(self, cartesia_client):
        resp = cartesia_client.post(
            "/cartesia/tts/bytes",
            json={"model_id": "sonic-english", "transcript": ""},
        )
        assert resp.status_code == 422

    def test_tts_bytes_with_voice(self, cartesia_client):
        resp = cartesia_client.post(
            "/cartesia/tts/bytes",
            json={
                "model_id": "sonic-english",
                "transcript": "test",
                "voice": {"id": "voice1", "mode": "id"},
            },
        )
        assert resp.status_code == 200

    def test_tts_bytes_mp3_format(self, cartesia_client):
        resp = cartesia_client.post(
            "/cartesia/tts/bytes",
            json={
                "model_id": "sonic-english",
                "transcript": "test",
                "output_format": {"container": "mp3"},
            },
        )
        assert resp.status_code == 200

    def test_tts_bytes_api_key_ignored(self, cartesia_client):
        resp = cartesia_client.post(
            "/cartesia/tts/bytes",
            json={"model_id": "sonic-english", "transcript": "hi"},
            headers={"X-API-Key": "fake-key"},
        )
        assert resp.status_code == 200


