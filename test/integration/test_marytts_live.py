"""Live test: drive the /marytts router with raw HTTP requests, exactly
as the upstream MaryTTS HTTP API expects.

There's no canonical MaryTTS Python SDK — the upstream `MaryClient` is
Java and Home Assistant / Mycroft community clients all hand-roll HTTP.
This test replays those bare requests against a uvicorn server running
the compat router, proving wire-level drop-in compatibility.

Upstream reference:
    https://github.com/marytts/marytts/blob/master/marytts-runtime/src/main/java/marytts/server/http/MaryHttpServer.java
"""
import pytest
import requests

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.marytts import (
        make_marytts_router,
        make_marytts_root_router,
    )
    app.include_router(make_marytts_router(engine))
    app.include_router(make_marytts_root_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


# Upstream MaryTTS responds with plain-text bodies for /locales and /voices.
# Synthesis is the /process endpoint, with INPUT_TEXT/INPUT_TYPE/OUTPUT_TYPE
# form-encoded as either GET query or POST body.

class TestMaryTTSWireProtocol:
    def test_locales_plaintext(self, base_url):
        r = requests.get(f"{base_url}/marytts/locales")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        # Newline-separated locales, e.g. "en-us\nde-de"
        locales = [ln for ln in r.text.splitlines() if ln.strip()]
        assert "en-us" in locales

    def test_voices_plaintext(self, base_url):
        r = requests.get(f"{base_url}/marytts/voices")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")
        # Format: "<name> <locale> <gender> <plugin>"
        first = r.text.strip().splitlines()[0].split()
        assert len(first) >= 3

    def test_process_get(self, base_url):
        r = requests.get(
            f"{base_url}/marytts/process",
            params={
                "INPUT_TEXT": "hello from raw http",
                "INPUT_TYPE": "TEXT",
                "OUTPUT_TYPE": "AUDIO",
                "AUDIO": "WAVE_FILE",
                "LOCALE": "en_US",
            },
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content.startswith(b"RIFF")

    def test_process_post_querystring(self, base_url):
        """Upstream MaryTTS clients use POST with the params in the query
        string; some also use form-encoded bodies. The router accepts the
        query-string form (which is what most HA/Mycroft clients send)."""
        r = requests.post(
            f"{base_url}/marytts/process",
            params={
                "INPUT_TEXT": "post querystring",
                "INPUT_TYPE": "TEXT",
                "OUTPUT_TYPE": "AUDIO",
                "AUDIO": "WAVE_FILE",
            },
        )
        assert r.status_code == 200
        assert r.content.startswith(b"RIFF")

    def test_root_alias_used_by_assistive_tech(self, base_url):
        """Legacy clients that hardcode bare paths hit the root alias."""
        r = requests.get(
            f"{base_url}/process",
            params={"INPUT_TEXT": "screen reader test"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"

    def test_voice_underscore_to_space(self, base_url):
        """The router converts `_` to space in VOICE to match upstream behavior."""
        r = requests.get(
            f"{base_url}/marytts/process",
            params={"INPUT_TEXT": "hi", "VOICE": "some_voice_name"},
        )
        assert r.status_code == 200
