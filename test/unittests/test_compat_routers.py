# Licensed under the Apache License, Version 2.0
"""Unit tests for the MaryTTS compatibility router."""
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeEngine:
    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
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
    return FakeEngine()


def _make_app(engine) -> FastAPI:
    from ovos_tts_server.routers.marytts import make_marytts_router
    app = FastAPI()
    app.include_router(make_marytts_router(engine))
    return app


@pytest.fixture(scope="module")
def client(engine):
    return TestClient(_make_app(engine))


class TestMaryTTSRouter:
    def test_locales_returns_plain_text(self, client):
        r = client.get("/locales")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        assert "en-us" in r.text
        assert "de-de" in r.text

    def test_voices_returns_plain_text(self, client):
        r = client.get("/voices")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        assert "default" in r.text
        assert "fake-tts" in r.text

    def test_process_get_returns_wav(self, client):
        r = client.get("/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"

    def test_process_post_returns_wav(self, client):
        r = client.post("/process", params={"INPUT_TEXT": "hello"})
        assert r.status_code == 200

    def test_process_requires_input_text(self, client):
        r = client.get("/process")
        assert r.status_code == 422

    def test_process_accepts_locale_and_voice(self, client):
        r = client.get(
            "/process",
            params={"INPUT_TEXT": "hi", "LOCALE": "en_US", "VOICE": "some_voice"},
        )
        assert r.status_code == 200
