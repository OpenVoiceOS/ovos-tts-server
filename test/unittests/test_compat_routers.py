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
    """Build a minimal FastAPI app with only the openai compat router."""
    from ovos_tts_server.routers.openai_tts import make_openai_tts_router

    app = FastAPI()
    app.include_router(make_openai_tts_router(engine))
    return app


@pytest.fixture(scope="module")
def client(engine):
    """Return a TestClient wired to the compat router app."""
    app = _make_app(engine)
    return TestClient(app)




# ---------------------------------------------------------------------------
# OpenAI TTS  (prefix: /openai)
# ---------------------------------------------------------------------------

class TestOpenAITTSRouter:
    def test_speech_default(self, client):
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1", "input": "hello world", "voice": "alloy"},
        )
        assert resp.status_code == 200

    def test_speech_hd_model(self, client):
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1-hd", "input": "hello", "voice": "nova"},
        )
        assert resp.status_code == 200

    def test_speech_empty_input_rejected(self, client):
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1", "input": "", "voice": "alloy"},
        )
        assert resp.status_code == 422

    def test_speech_input_too_long_rejected(self, client):
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1", "input": "x" * 4097, "voice": "alloy"},
        )
        assert resp.status_code == 422

    def test_speech_arbitrary_voice_accepted(self, client):
        """Any voice string is forwarded to the OVOS plugin to interpret."""
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": "my-plugin-voice"},
        )
        assert resp.status_code == 200

    def test_speech_arbitrary_model_accepted(self, client):
        """Any model string is forwarded to the OVOS plugin to interpret."""
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "gpt-4o-mini-tts", "input": "hi", "voice": "alloy"},
        )
        assert resp.status_code == 200

    def test_speech_speed_out_of_range(self, client):
        resp = client.post(
            "/openai/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": "alloy", "speed": 5.0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Coqui  (prefix: /coqui)
# ---------------------------------------------------------------------------
