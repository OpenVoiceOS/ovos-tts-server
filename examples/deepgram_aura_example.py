"""Drive the official Deepgram Python SDK (Aura TTS) against ovos-tts-server.

The Deepgram SDK accepts a custom base URL via ``DeepgramClientOptions(url=...)``
— point it at the server's ``/deepgram`` prefix so ``speak`` POSTs to
``/deepgram/v1/speak``.

Prerequisites:
    pip install deepgram-sdk
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/deepgram_aura_example.py "hello world" out.wav
"""
import sys

from deepgram import DeepgramClient, DeepgramClientOptions, SpeakOptions


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    opts = DeepgramClientOptions(api_key="ignored", url=f"{OVOS_HOST}/deepgram")
    client = DeepgramClient("ignored", opts)
    options = SpeakOptions(model="aura-asteria-en", encoding="linear16")
    client.speak.rest.v("1").save(out_path, {"text": text}, options)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
