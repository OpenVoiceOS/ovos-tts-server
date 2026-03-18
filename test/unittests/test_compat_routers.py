# Licensed under the Apache License, Version 2.0
"""Unit tests for TTS server compatibility routers.

Uses a lightweight mock engine to avoid loading any OVOS TTS plugin.
"""
import base64
import json
import os
import tempfile
import wave
from typing import List, Optional, Tuple
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav_bytes() -> bytes:
    """Return minimal valid WAV file bytes."""
    buf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    buf.close()
    with wave.open(buf.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)
    with open(buf.name, "rb") as f:
        data = f.read()
    os.unlink(buf.name)
    return data


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
    """Build a minimal FastAPI app with all compat routers."""
    from ovos_tts_server.routers.elevenlabs import make_elevenlabs_router
    from ovos_tts_server.routers.openai_tts import make_openai_tts_router
    from ovos_tts_server.routers.coqui import make_coqui_router
    from ovos_tts_server.routers.google_tts import make_google_tts_router
    from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router
    from ovos_tts_server.routers.piper import make_piper_router

    app = FastAPI()
    app.include_router(make_elevenlabs_router(engine))
    app.include_router(make_openai_tts_router(engine))
    app.include_router(make_coqui_router(engine))
    app.include_router(make_google_tts_router(engine))
    app.include_router(make_amazon_polly_router(engine))
    app.include_router(make_piper_router(engine))
    return app


@pytest.fixture(scope="module")
def client(engine):
    """Return a TestClient wired to the compat router app."""
    app = _make_app(engine)
    return TestClient(app)


# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------

class TestElevenLabsRouter:
    def test_list_voices_returns_voices(self, client):
        resp = client.get("/v1/voices")
        assert resp.status_code == 200
        body = resp.json()
        assert "voices" in body
        assert len(body["voices"]) >= 1
        assert "voice_id" in body["voices"][0]
        assert "name" in body["voices"][0]

    def test_list_voices_api_key_ignored(self, client):
        resp = client.get("/v1/voices", headers={"xi-api-key": "fake-key"})
        assert resp.status_code == 200

    def test_list_models(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        models = resp.json()
        assert isinstance(models, list)
        assert len(models) >= 1
        assert models[0]["model_id"] == "fake-tts"

    def test_tts_default_voice(self, client):
        resp = client.post(
            "/v1/text-to-speech/default",
            json={"text": "hello world"},
        )
        assert resp.status_code == 200

    def test_tts_named_voice(self, client):
        resp = client.post(
            "/v1/text-to-speech/voice1",
            json={"text": "test"},
        )
        assert resp.status_code == 200

    def test_tts_output_format_mp3(self, client):
        resp = client.post(
            "/v1/text-to-speech/default?output_format=mp3_44100_128",
            json={"text": "test"},
        )
        assert resp.status_code == 200

    def test_tts_empty_text_rejected(self, client):
        resp = client.post(
            "/v1/text-to-speech/default",
            json={"text": ""},
        )
        assert resp.status_code == 422

    def test_tts_voice_settings_accepted(self, client):
        resp = client.post(
            "/v1/text-to-speech/default",
            json={"text": "hello", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# OpenAI TTS
# ---------------------------------------------------------------------------

class TestOpenAITTSRouter:
    def test_speech_default(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "hello world", "voice": "alloy"},
        )
        assert resp.status_code == 200

    def test_speech_hd_model(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1-hd", "input": "hello", "voice": "nova"},
        )
        assert resp.status_code == 200

    def test_speech_empty_input_rejected(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "", "voice": "alloy"},
        )
        assert resp.status_code == 422

    def test_speech_input_too_long_rejected(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "x" * 4097, "voice": "alloy"},
        )
        assert resp.status_code == 422

    def test_speech_invalid_voice_rejected(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": "unknown_voice"},
        )
        assert resp.status_code == 422

    def test_speech_invalid_model_rejected(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "gpt-4", "input": "hi", "voice": "alloy"},
        )
        assert resp.status_code == 422

    def test_speech_speed_out_of_range(self, client):
        resp = client.post(
            "/v1/audio/speech",
            json={"model": "tts-1", "input": "hi", "voice": "alloy", "speed": 5.0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Coqui
# ---------------------------------------------------------------------------

class TestCoquiRouter:
    def test_tts_basic(self, client):
        resp = client.get("/api/tts?text=hello")
        assert resp.status_code == 200

    def test_tts_with_speaker(self, client):
        resp = client.get("/api/tts?text=hello&speaker_id=voice1")
        assert resp.status_code == 200

    def test_tts_with_language(self, client):
        resp = client.get("/api/tts?text=hello&language_id=de-de")
        assert resp.status_code == 200

    def test_tts_empty_text_rejected(self, client):
        resp = client.get("/api/tts?text=")
        assert resp.status_code == 422

    def test_tts_missing_text_rejected(self, client):
        resp = client.get("/api/tts")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Google Cloud TTS
# ---------------------------------------------------------------------------

class TestGoogleTTSRouter:
    def test_synthesize_basic(self, client):
        resp = client.post(
            "/v1/text:synthesize",
            json={
                "input": {"text": "hello"},
                "voice": {"languageCode": "en-US", "name": "en-US-Standard-A"},
                "audioConfig": {"audioEncoding": "LINEAR16"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "audioContent" in body
        # Should be base64-encoded
        base64.b64decode(body["audioContent"])

    def test_synthesize_missing_input_rejected(self, client):
        resp = client.post(
            "/v1/text:synthesize",
            json={"voice": {"languageCode": "en-US"}, "audioConfig": {"audioEncoding": "MP3"}},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Amazon Polly
# ---------------------------------------------------------------------------

class TestAmazonPollyRouter:
    def test_speech_basic(self, client):
        resp = client.post(
            "/v1/speech",
            json={"Text": "hello", "VoiceId": "Joanna", "OutputFormat": "pcm"},
        )
        assert resp.status_code == 200

    def test_speech_invalid_format(self, client):
        resp = client.post(
            "/v1/speech",
            json={"Text": "hello", "VoiceId": "Joanna", "OutputFormat": "flac"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Piper
# ---------------------------------------------------------------------------

class TestPiperRouter:
    def test_tts_basic(self, client):
        resp = client.get("/?text=hello")
        assert resp.status_code == 200

    def test_tts_with_voice(self, client):
        resp = client.get("/?text=hello&voice=voice1")
        assert resp.status_code == 200
