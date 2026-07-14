"""Live test: drive `ovos-tts-plugin-polly` against our /amazon-polly router.

The plugin uses boto3 internally — `Session(key_id, secret, region).client("polly")`.
boto3 doesn't expose an endpoint_url kwarg on the plugin, so we redirect
via the `AWS_ENDPOINT_URL_POLLY` env var that botocore honours. Set it
before importing the plugin so the boto3 client picks it up at __init__.
"""
import os
import wave

import pytest

from test.integration.conftest import run_live_server


@pytest.fixture(scope="module")
def base_url():
    from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router

    def register(app, engine):
        app.include_router(make_amazon_polly_router(engine))

    yield from run_live_server(register)


def test_polly_plugin_synthesizes_via_compat_router(base_url, tmp_path,
                                                   monkeypatch):
    """End-to-end: PollyTTS plugin renders a sentence to a WAV/MP3 file via
    our /amazon-polly router. boto3 picks up AWS_ENDPOINT_URL_POLLY at
    client construction time, so we set it before importing the plugin.
    """
    monkeypatch.setenv("AWS_ENDPOINT_URL_POLLY", f"{base_url}/amazon-polly")
    # boto3's signing requires creds even when the server ignores them;
    # any non-empty string works.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ignored")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "ignored")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    from ovos_tts_plugin_polly import PollyTTS

    tts = PollyTTS(config={
        "lang": "en-us",
        "voice": "Joanna",
        "region": "us-east-1",
        "engine": "neural",
    })
    out_path = tmp_path / "polly.mp3"
    result_path, phonemes = tts.get_tts(
        "hello world",
        str(out_path),
        lang="en-us",
        voice="Joanna",
    )
    assert result_path == str(out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
