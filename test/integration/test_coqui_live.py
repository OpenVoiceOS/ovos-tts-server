"""Live test: drive the /coqui router with raw HTTP requests.

The official Coqui `tts-server` (CLI in coqui-ai/TTS) does not expose a
canonical Python client SDK; clients (Home Assistant, custom OVOS
plugins, command-line tools) talk to it via bare HTTP. This test
replays those bare requests against a uvicorn server running the compat
router, matching the wire contract.

Upstream reference:
    https://github.com/coqui-ai/TTS/blob/dev/TTS/server/server.py
"""
import pytest
import requests

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.coqui import make_coqui_router
    app.include_router(make_coqui_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


class TestCoquiWireProtocol:
    def test_tts_basic(self, base_url):
        r = requests.get(
            f"{base_url}/coqui/api/tts",
            params={"text": "hello from raw http"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content.startswith(b"RIFF")
        assert len(r.content) > 16

    def test_tts_with_speaker_id(self, base_url):
        r = requests.get(
            f"{base_url}/coqui/api/tts",
            params={"text": "speaker test", "speaker_id": "voice1"},
        )
        assert r.status_code == 200
        assert r.content.startswith(b"RIFF")

    def test_tts_with_language_id(self, base_url):
        r = requests.get(
            f"{base_url}/coqui/api/tts",
            params={
                "text": "language test",
                "speaker_id": "voice1",
                "language_id": "de-de",
            },
        )
        assert r.status_code == 200

    def test_tts_missing_text_rejected(self, base_url):
        r = requests.get(f"{base_url}/coqui/api/tts")
        assert r.status_code == 422

    def test_tts_empty_text_rejected(self, base_url):
        r = requests.get(f"{base_url}/coqui/api/tts", params={"text": ""})
        assert r.status_code == 422
