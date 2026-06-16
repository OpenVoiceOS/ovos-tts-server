"""Drive the official OpenAI Python SDK against an ovos-tts-server instance.

The SDK accepts `base_url=` cleanly — no monkey-patching needed.

Prerequisites:
    pip install openai
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/openai_tts_example.py "hello world" out.mp3
"""
import sys

from openai import OpenAI


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    client = OpenAI(base_url=f"{OVOS_HOST}/openai/v1", api_key="ignored")
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=text,
        response_format="mp3",
    ) as response:
        response.stream_to_file(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
