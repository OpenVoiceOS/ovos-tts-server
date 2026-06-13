"""Drive the official OpenAI Python SDK (Kokoro-compatible) against ovos-tts-server.

Kokoro / kokoro-fastapi expose the OpenAI ``/v1/audio/speech`` shape, so the
official ``openai`` SDK is the canonical client — point ``base_url`` at the
server's ``/kokoro`` prefix.

Prerequisites:
    pip install openai
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/kokoro_example.py "hello world" out.wav
"""
import sys

from openai import OpenAI


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    client = OpenAI(base_url=f"{OVOS_HOST}/kokoro/v1", api_key="ignored")
    with client.audio.speech.with_streaming_response.create(
        model="kokoro",
        voice="af_heart",
        input=text,
        response_format="wav",
    ) as response:
        response.stream_to_file(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
