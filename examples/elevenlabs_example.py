"""Drive the official ElevenLabs SDK against an ovos-tts-server instance.

The SDK accepts `base_url=` cleanly — no monkey-patching needed.

Prerequisites:
    pip install elevenlabs
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/elevenlabs_example.py "hello world" out.mp3
"""
import sys

from elevenlabs.client import ElevenLabs


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    client = ElevenLabs(base_url=f"{OVOS_HOST}/elevenlabs", api_key="ignored")
    audio_iter = client.text_to_speech.convert(
        voice_id="default",
        text=text,
        model_id="eleven_monolingual_v1",
    )
    with open(out_path, "wb") as fp:
        for chunk in audio_iter:
            if chunk:
                fp.write(chunk)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
