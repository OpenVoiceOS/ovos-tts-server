"""Live test: drive the /elevenlabs compat router with the official
`elevenlabs` Python SDK pointed at a uvicorn server in this process.
"""
import pytest

elevenlabs = pytest.importorskip("elevenlabs")

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.elevenlabs import make_elevenlabs_router
    app.include_router(make_elevenlabs_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


@pytest.fixture(scope="module")
def client(base_url):
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key="ignored", base_url=f"{base_url}/elevenlabs")


class TestElevenLabsSDK:
    def test_list_voices(self, client):
        page = client.voices.get_all()
        # SDK returns an object with a `.voices` attribute
        voices = getattr(page, "voices", None) or page
        assert len(voices) >= 1
        first = voices[0]
        # Either an object with .voice_id/.name or a dict
        vid = getattr(first, "voice_id", None) or first["voice_id"]
        name = getattr(first, "name", None) or first["name"]
        assert vid
        assert name

    def test_text_to_speech_convert_returns_audio(self, client):
        audio_chunks = client.text_to_speech.convert(
            voice_id="default",
            text="hello world",
        )
        # SDK returns an iterator of bytes
        audio = b"".join(audio_chunks)
        assert audio  # non-empty
        # Without pydub, our server falls back to WAV bytes
        assert audio.startswith(b"RIFF") or audio.startswith(b"ID3") or len(audio) > 16
