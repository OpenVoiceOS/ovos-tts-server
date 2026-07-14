"""Live test: drive the /elevenlabs compat router with the official
`elevenlabs` Python SDK pointed at a uvicorn server in this process.
"""
import pytest

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


class TestElevenLabsStreamInput:
    """Drive the stream-input WebSocket against a live uvicorn server.

    The wire messages are exactly those the ElevenLabs SDKs send: a BOS frame
    with voice settings, content frames, then an empty-text EOS frame.
    """

    def test_stream_input_wire_protocol(self, base_url):
        import asyncio
        import base64
        import json

        import websockets

        ws_url = (
            base_url.replace("http://", "ws://")
            + "/elevenlabs/v1/text-to-speech/default/stream-input"
              "?model_id=eleven_monolingual_v1&output_format=pcm_24000"
        )

        async def stream() -> bytes:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "text": " ",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                    "xi_api_key": "ignored",
                }))
                await ws.send(json.dumps({"text": "hello "}))
                await ws.send(json.dumps({"text": "world"}))
                await ws.send(json.dumps({"text": ""}))

                audio = b""
                while True:
                    frame = json.loads(await ws.recv())
                    if frame["audio"]:
                        audio += base64.b64decode(frame["audio"])
                    if frame["isFinal"]:
                        return audio

        audio = asyncio.run(stream())
        # pcm_* is headerless: 0.1s of 24 kHz 16-bit mono
        assert not audio.startswith(b"RIFF")
        assert len(audio) // 2 == pytest.approx(2400, abs=2)

    def test_sdk_convert_realtime_with_ws_scheme_patch(self, base_url, monkeypatch):
        """The SDK reaches a plaintext server once its realtime client keeps ws://.

        The SDK's realtime client forces the `wss` scheme onto the base URL, so
        a plaintext deployment either sits behind a TLS terminator or applies
        this patch — the one shipped in examples/elevenlabs_ws_example.py.
        """
        import urllib.parse

        from elevenlabs import VoiceSettings, realtime_tts
        from elevenlabs.client import ElevenLabs

        original_init = realtime_tts.RealtimeTextToSpeechClient.__init__

        def __init__(self, *, client_wrapper):
            original_init(self, client_wrapper=client_wrapper)
            parsed = urllib.parse.urlparse(client_wrapper.get_base_url())
            scheme = "ws" if parsed.scheme == "http" else "wss"
            self._ws_base_url = parsed._replace(scheme=scheme).geturl()

        monkeypatch.setattr(
            realtime_tts.RealtimeTextToSpeechClient, "__init__", __init__
        )

        client = ElevenLabs(api_key="ignored", base_url=f"{base_url}/elevenlabs")
        audio = b"".join(client.text_to_speech.convert_realtime(
            voice_id="default",
            text=iter(["hello ", "world"]),
            output_format="pcm_24000",
            # the SDK unconditionally serializes voice_settings into its BOS frame
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8),
        ))

        assert not audio.startswith(b"RIFF")
        assert len(audio) // 2 == pytest.approx(2400, abs=2)
