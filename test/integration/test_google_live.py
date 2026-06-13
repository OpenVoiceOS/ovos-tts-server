"""Live test against /google-tts.

The official `google-cloud-texttospeech` SDK builds request URLs from a
**host-only** `api_endpoint` plus a hardcoded `/v1/text:synthesize`
path. It cannot be aimed at a sub-path, so the SDK cannot directly drive
a router mounted under `/google-tts/`.

Two test surfaces here:

1. `TestGoogleTTSSDK_AtRoot` — uses the official SDK against an app that
   mounts the router with NO prefix. Proves the wire format matches what
   the SDK sends/expects. In production, use a reverse proxy to expose
   `/v1/text:synthesize` at the SDK's expected URL.

2. `TestGoogleTTSRestContract` — drives the prefixed `/google-tts/v1/...`
   endpoint with raw HTTP, sending exactly what the SDK's REST transport
   would send. Proves the contract is correct under the canonical prefix.
"""
import base64
import json

import pytest

texttospeech = pytest.importorskip("google.cloud.texttospeech")
pytest.importorskip("google.api_core")
pytest.importorskip("google.auth")
import requests  # noqa: E402

from test.integration.conftest import run_live_server


# ---------- shared fakes ----------

def _register_prefixed(app, engine):
    from ovos_tts_server.routers.google_tts import make_google_tts_router
    app.include_router(make_google_tts_router(engine))


def _register_at_root(app, engine):
    """Mount the same handlers at the root (no prefix) so the Google SDK
    can find /v1/text:synthesize directly."""
    from fastapi import APIRouter
    from ovos_tts_server.routers.google_tts import make_google_tts_router

    prefixed = make_google_tts_router(engine)
    root = APIRouter()
    for route in prefixed.routes:
        # strip the "/google-tts" prefix
        if route.path.startswith("/google-tts"):
            route.path = route.path[len("/google-tts"):] or "/"
            route.path_format = route.path
        root.routes.append(route)
    app.include_router(root)


# ---------- TLS-bypass shim for the SDK ----------

@pytest.fixture(scope="module")
def _https_to_http_patch():
    """Rewrite https://<host>/... -> http://... inside the SDK's session."""
    import google.auth.transport.requests as gat
    original = gat.AuthorizedSession.request

    def patched(self, method, url, *args, **kwargs):
        if url.startswith("https://127.0.0.1") or url.startswith("https://localhost"):
            url = "http://" + url[len("https://"):]
        return original(self, method, url, *args, **kwargs)

    gat.AuthorizedSession.request = patched
    yield
    gat.AuthorizedSession.request = original


# ---------- SDK at root ----------

@pytest.fixture(scope="module")
def root_url():
    yield from run_live_server(_register_at_root)


@pytest.fixture(scope="module")
def google_client(root_url, _https_to_http_patch):
    from google.auth.credentials import AnonymousCredentials
    from google.api_core.client_options import ClientOptions
    from google.cloud import texttospeech

    host = root_url.replace("http://", "")
    return texttospeech.TextToSpeechClient(
        credentials=AnonymousCredentials(),
        client_options=ClientOptions(api_endpoint=host),
        transport="rest",
    )


class TestGoogleTTSSDK_AtRoot:
    """Drive the official google-cloud-texttospeech SDK against an
    unprefixed mount, proving wire-level drop-in compatibility."""

    def test_synthesize_mp3(self, google_client):
        from google.cloud import texttospeech

        resp = google_client.synthesize_speech(
            input=texttospeech.SynthesisInput(text="hello google"),
            voice=texttospeech.VoiceSelectionParams(language_code="en-US"),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
            ),
        )
        assert resp.audio_content
        assert len(resp.audio_content) > 16

    def test_synthesize_linear16_wav(self, google_client):
        from google.cloud import texttospeech

        resp = google_client.synthesize_speech(
            input=texttospeech.SynthesisInput(text="linear16 test"),
            voice=texttospeech.VoiceSelectionParams(
                language_code="en-US", name="voice1"
            ),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            ),
        )
        assert resp.audio_content.startswith(b"RIFF")


# ---------- raw REST against the canonical /google-tts prefix ----------

@pytest.fixture(scope="module")
def prefixed_url():
    yield from run_live_server(_register_prefixed)


class TestGoogleTTSRestContract:
    """Send exactly the JSON the SDK's REST transport would send, against
    the canonical /google-tts/v1/text:synthesize endpoint."""

    def test_rest_synthesize(self, prefixed_url):
        body = {
            "input": {"text": "raw rest"},
            "voice": {"languageCode": "en-US"},
            "audioConfig": {"audioEncoding": "MP3"},
        }
        r = requests.post(
            f"{prefixed_url}/google-tts/v1/text:synthesize", json=body,
        )
        assert r.status_code == 200
        data = r.json()
        assert "audioContent" in data
        audio = base64.b64decode(data["audioContent"])
        assert len(audio) > 16
