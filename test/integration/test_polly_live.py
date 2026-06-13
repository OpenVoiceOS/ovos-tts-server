"""Live test: drive the /amazon-polly router with the official boto3 client.

We use boto3's REST endpoint override (`endpoint_url=`) to redirect Polly
calls at this server. Polly's real wire format is AWS SigV4-signed JSON
to /v1/speech; our compat router accepts the same JSON shape and ignores
auth.

Note: boto3 expects a particular endpoint URL structure ending after the
service base path. Because our router lives under /amazon-polly/v1/speech
and boto3 builds the path as `<endpoint>/v1/speech`, we point endpoint_url
at `<server>/amazon-polly`.
"""
import pytest

boto3 = pytest.importorskip("boto3")

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router
    app.include_router(make_amazon_polly_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


@pytest.fixture(scope="module")
def polly(base_url):
    return boto3.client(
        "polly",
        endpoint_url=f"{base_url}/amazon-polly",
        aws_access_key_id="ignored",
        aws_secret_access_key="ignored",
        region_name="us-east-1",
    )


class TestPollyBoto3:
    def test_synthesize_speech_mp3(self, polly):
        resp = polly.synthesize_speech(
            Text="hello from boto3",
            VoiceId="Joanna",
            OutputFormat="mp3",
        )
        audio = resp["AudioStream"].read()
        assert len(audio) > 16

    def test_synthesize_speech_pcm(self, polly):
        resp = polly.synthesize_speech(
            Text="pcm output",
            VoiceId="Joanna",
            OutputFormat="pcm",
        )
        audio = resp["AudioStream"].read()
        assert len(audio) > 16

    def test_synthesize_speech_with_engine_param(self, polly):
        resp = polly.synthesize_speech(
            Text="neural test",
            VoiceId="Joanna",
            OutputFormat="mp3",
            Engine="neural",
        )
        audio = resp["AudioStream"].read()
        assert len(audio) > 16
