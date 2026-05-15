"""Live test: drive the /piper router with raw HTTP requests.

Piper's upstream `piper.http_server` is a tiny script that exposes
`GET /?text=...` and returns WAV bytes. No Python client SDK exists;
every client (wyoming-piper, ovos-tts-plugin-piper-http, Home Assistant
add-on) uses bare HTTP.

Upstream reference:
    https://github.com/rhasspy/piper/blob/master/src/python_run/piper/http_server.py
"""
import pytest
import requests

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.piper import make_piper_router
    app.include_router(make_piper_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


class TestPiperWireProtocol:
    def test_tts_basic(self, base_url):
        r = requests.get(f"{base_url}/piper/", params={"text": "hello piper"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content.startswith(b"RIFF")
        assert len(r.content) > 16

    def test_tts_with_voice(self, base_url):
        """OVOS extension: pass a voice override (upstream Piper picks
        the voice at process startup, but we support per-request override
        because we're proxying to a plugin that can switch voices)."""
        r = requests.get(
            f"{base_url}/piper/",
            params={"text": "voice test", "voice": "voice1"},
        )
        assert r.status_code == 200
        assert r.content.startswith(b"RIFF")

    def test_tts_missing_text_rejected(self, base_url):
        r = requests.get(f"{base_url}/piper/")
        assert r.status_code == 422

    def test_tts_empty_text_rejected(self, base_url):
        r = requests.get(f"{base_url}/piper/", params={"text": ""})
        assert r.status_code == 422

    def test_long_utterance(self, base_url):
        text = "this is a longer sentence " * 10
        r = requests.get(f"{base_url}/piper/", params={"text": text})
        assert r.status_code == 200
        assert r.content.startswith(b"RIFF")
