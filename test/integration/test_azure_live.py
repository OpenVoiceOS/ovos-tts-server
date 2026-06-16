"""Live test: drive the /azure-tts router against Azure's documented REST
contract.

Azure has two synthesis APIs:

- **REST**: `POST /cognitiveservices/v1` with an SSML body, returns audio
  bytes. Documented, supported, widely used in serverless/curl/embedded
  contexts. **This is what our router implements.**
- **WebSocket streaming**: `wss://.../cognitiveservices/websocket/v1`, a
  proprietary streaming protocol with viseme/timing metadata. The official
  `azure-cognitiveservices-speech` Python SDK uses this by default for
  synthesis. We do not implement the WebSocket protocol.

The tests here send the exact SSML POST bodies Azure's REST docs show,
proving our compat router matches the REST wire format. Any client that
speaks Azure REST (curl, requests, custom wrappers, third-party clients)
is a drop-in.

For full official-SDK drop-in, terminate TLS in a reverse proxy and put
a WebSocket → REST bridge in front (out of scope for this PR).
"""
import pytest
import requests

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.azure_tts import make_azure_tts_router
    app.include_router(make_azure_tts_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


def _ssml(text: str, voice: str = "default", lang: str = "en-US") -> str:
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="{lang}">'
        f'<voice name="{voice}">{text}</voice>'
        f'</speak>'
    )


class TestAzureRestContract:
    def test_synthesize_returns_audio_bytes(self, base_url):
        r = requests.post(
            f"{base_url}/azure-tts/cognitiveservices/v1",
            data=_ssml("hello azure"),
            headers={
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "Ocp-Apim-Subscription-Key": "ignored",
                "User-Agent": "live-integration-test",
            },
        )
        assert r.status_code == 200
        assert len(r.content) > 16

    def test_riff_format_returns_wav(self, base_url):
        r = requests.post(
            f"{base_url}/azure-tts/cognitiveservices/v1",
            data=_ssml("wav format"),
            headers={
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
                "Ocp-Apim-Subscription-Key": "ignored",
                "User-Agent": "live-integration-test",
            },
        )
        assert r.status_code == 200
        assert r.content.startswith(b"RIFF")

    def test_voice_name_and_lang_parsed_from_ssml(self, base_url):
        """The router should accept SSML with custom voice/lang and not 500."""
        r = requests.post(
            f"{base_url}/azure-tts/cognitiveservices/v1",
            data=_ssml("german voice", voice="voice1", lang="de-DE"),
            headers={
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "Ocp-Apim-Subscription-Key": "ignored",
                "User-Agent": "live-integration-test",
            },
        )
        assert r.status_code == 200
        assert len(r.content) > 16

    def test_subscription_key_is_ignored(self, base_url):
        """Any value for Ocp-Apim-Subscription-Key is accepted."""
        r = requests.post(
            f"{base_url}/azure-tts/cognitiveservices/v1",
            data=_ssml("auth test"),
            headers={
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "Ocp-Apim-Subscription-Key": "completely-fake-key-12345",
                "User-Agent": "live-integration-test",
            },
        )
        assert r.status_code == 200


# Note on the official Azure SDK:
#
#   import azure.cognitiveservices.speech as speechsdk
#   config = speechsdk.SpeechConfig(endpoint="http://.../azure-tts/...", subscription="x")
#   synth  = speechsdk.SpeechSynthesizer(speech_config=config)
#   synth.speak_text_async("hi").get()
#
# This opens a WebSocket to /cognitiveservices/websocket/v1 (not REST), so
# it will not hit this router. Implementing Microsoft's WebSocket streaming
# protocol is meaningful work and intentionally out of scope.
