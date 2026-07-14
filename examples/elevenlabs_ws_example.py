"""Stream from the official ElevenLabs SDK over the stream-input WebSocket.

`client.text_to_speech.convert_realtime()` opens
`/v1/text-to-speech/{voice_id}/stream-input`, which ovos-tts-server implements.

The SDK derives the WebSocket URL from `base_url=` but forces the `wss` scheme,
so it cannot reach a plaintext `http://` server. Either put a TLS terminator in
front of ovos-tts-server (then no patching is needed), or teach the SDK to keep
`ws` for `http` base URLs with the patch below.

Prerequisites:
    pip install elevenlabs
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/elevenlabs_ws_example.py "hello world" out.pcm
"""
import sys
import urllib.parse

from elevenlabs import VoiceSettings, realtime_tts
from elevenlabs.client import ElevenLabs

OVOS_HOST = "http://localhost:9666"


def use_ws_scheme_for_http() -> None:
    """Let the SDK's realtime client speak ws:// to a plaintext server."""
    original_init = realtime_tts.RealtimeTextToSpeechClient.__init__

    def __init__(self, *, client_wrapper):
        original_init(self, client_wrapper=client_wrapper)
        parsed = urllib.parse.urlparse(client_wrapper.get_base_url())
        scheme = "ws" if parsed.scheme == "http" else "wss"
        self._ws_base_url = parsed._replace(scheme=scheme).geturl()

    realtime_tts.RealtimeTextToSpeechClient.__init__ = __init__


def main(text: str, out_path: str) -> None:
    use_ws_scheme_for_http()

    client = ElevenLabs(base_url=f"{OVOS_HOST}/elevenlabs", api_key="ignored")
    audio_iter = client.text_to_speech.convert_realtime(
        voice_id="default",
        text=iter([text]),
        model_id="eleven_monolingual_v1",
        # the SDK unconditionally serializes voice_settings into its BOS frame
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8),
        # headerless mono 16-bit little-endian PCM at 24 kHz
        output_format="pcm_24000",
    )
    with open(out_path, "wb") as fp:
        for chunk in audio_iter:
            if chunk:
                fp.write(chunk)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.pcm>")
    main(sys.argv[1], sys.argv[2])
