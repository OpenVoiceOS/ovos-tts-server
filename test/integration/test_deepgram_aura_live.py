"""Live test: drive the official Deepgram SDK (Aura TTS) against our /deepgram router."""
import pytest

pytest.importorskip("deepgram")

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.deepgram_aura import make_deepgram_aura_router
    app.include_router(make_deepgram_aura_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


def test_deepgram_speak_generate(base_url):
    from deepgram import DeepgramClient, DeepgramClientEnvironment

    env = DeepgramClientEnvironment(
        base=f"{base_url}/deepgram",
        production=f"{base_url}/deepgram",
        agent=f"{base_url.replace('http', 'ws')}/deepgram",
        agent_rest=f"{base_url}/deepgram",
    )
    client = DeepgramClient(api_key="ignored", environment=env)
    audio = b"".join(client.speak.v1.audio.generate(
        text="hello from the live test",
        model="aura-asteria-en",
        encoding="linear16",
        container="wav",
    ))
    assert len(audio) > 16
