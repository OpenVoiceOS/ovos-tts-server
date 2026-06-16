"""Live test: drive the WebSocket synthesis bridge with the official
`azure-cognitiveservices-speech` SDK.

The SDK normally connects to a regional `wss://...tts.speech.microsoft.com`
host. We point it at our local server via `SpeechConfig.from_endpoint`,
giving the SDK a `ws://127.0.0.1:<port>/azure-tts/cognitiveservices/websocket/v1`
URL. Our WebSocket bridge speaks enough of Microsoft's protocol for
`speak_text_async()` to complete and return audio bytes.
"""
import azure.cognitiveservices.speech as speechsdk
import pytest

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.azure_ws import make_azure_ws_router
    app.include_router(make_azure_ws_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


def _build_synthesizer(base_url: str):
    """Build a SpeechSynthesizer pointed at the local bridge."""
    ws_url = (
        base_url.replace("http://", "ws://")
        + "/azure-tts/cognitiveservices/websocket/v1"
    )
    config = speechsdk.SpeechConfig(endpoint=ws_url, subscription="ignored")
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm,
    )
    # AudioConfig(None) -> in-memory result, no playback
    return speechsdk.SpeechSynthesizer(
        speech_config=config, audio_config=None,
    )


class TestAzureSpeechSDK:
    def test_speak_text_returns_audio(self, base_url):
        synth = _build_synthesizer(base_url)
        result = synth.speak_text_async("hello from azure sdk").get()
        assert result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted, (
            result.cancellation_details.error_details
            if result.reason == speechsdk.ResultReason.Canceled
            else f"reason={result.reason}"
        )
        assert result.audio_data
        assert len(result.audio_data) > 16

    def test_speak_ssml_returns_audio(self, base_url):
        synth = _build_synthesizer(base_url)
        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="en-US"><voice name="voice1">ssml works</voice></speak>'
        )
        result = synth.speak_ssml_async(ssml).get()
        assert result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted
        assert result.audio_data.startswith(b"RIFF")
