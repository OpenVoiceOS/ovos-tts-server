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
    """Build a minimal FastAPI app with only the amazon-polly compat router."""
    from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router

    app = FastAPI()
    app.include_router(make_amazon_polly_router(engine))
    return app


@pytest.fixture(scope="module")
def client(engine):
    """Return a TestClient wired to the compat router app."""
    app = _make_app(engine)
    return TestClient(app)




# ---------------------------------------------------------------------------
# Amazon Polly  (prefix: /amazon-polly)
# ---------------------------------------------------------------------------

class TestAmazonPollyRouter:
    def test_speech_basic(self, client):
        resp = client.post(
            "/amazon-polly/v1/speech",
            json={"Text": "hello", "VoiceId": "Joanna", "OutputFormat": "pcm"},
        )
        assert resp.status_code == 200

    def test_speech_invalid_format(self, client):
        resp = client.post(
            "/amazon-polly/v1/speech",
            json={"Text": "hello", "VoiceId": "Joanna", "OutputFormat": "flac"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Azure TTS  (prefix: /azure-tts)
# ---------------------------------------------------------------------------
