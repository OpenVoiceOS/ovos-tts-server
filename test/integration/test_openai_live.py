"""Live test: drive the /openai router with the official `openai` SDK."""
import pytest

openai_mod = pytest.importorskip("openai")

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.openai_tts import make_openai_tts_router
    app.include_router(make_openai_tts_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


@pytest.fixture(scope="module")
def client(base_url):
    from openai import OpenAI
    return OpenAI(api_key="ignored", base_url=f"{base_url}/openai/v1")


class TestOpenAISDK:
    def test_audio_speech_create_returns_bytes(self, client):
        resp = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input="hello from the live test",
        )
        # streaming response — read full content
        audio = resp.read() if hasattr(resp, "read") else bytes(resp)
        assert len(audio) > 16

    def test_audio_speech_response_format_wav(self, client):
        resp = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input="format test",
            response_format="wav",
        )
        audio = resp.read() if hasattr(resp, "read") else bytes(resp)
        assert audio.startswith(b"RIFF")

    def test_audio_speech_with_speed(self, client):
        resp = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input="speed test",
            speed=1.25,
        )
        audio = resp.read() if hasattr(resp, "read") else bytes(resp)
        assert len(audio) > 16
