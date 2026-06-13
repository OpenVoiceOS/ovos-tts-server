"""Drive ovos-tts-server using the PlayHT-compatible endpoint.

The endpoint mirrors PlayHT's POST /api/v2/tts/stream API.

Prerequisites:
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/playht_example.py "hello world" out.mp3

Equivalent curl:
    curl -X POST http://localhost:9666/playht/api/v2/tts/stream \\
         -H "Content-Type: application/json" \\
         -H "Authorization: ignored" \\
         -H "X-USER-ID: ignored" \\
         -d '{"text":"hello world","output_format":"mp3"}' \\
         --output out.mp3
"""
import sys

import requests

OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    resp = requests.post(
        f"{OVOS_HOST}/playht/api/v2/tts/stream",
        json={
            "text": text,
            "output_format": "mp3",
        },
        headers={
            "Authorization": "ignored",
            "X-USER-ID": "ignored",
        },
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
