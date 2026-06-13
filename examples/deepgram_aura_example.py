"""Drive ovos-tts-server using the Deepgram Aura-compatible endpoint.

The endpoint mirrors Deepgram's POST /v1/speak API.

Prerequisites:
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/deepgram_aura_example.py "hello world" out.wav

Equivalent curl:
    curl -X POST "http://localhost:9666/deepgram/v1/speak?model=aura-asteria-en" \\
         -H "Content-Type: application/json" \\
         -H "Authorization: Token ignored" \\
         -d '{"text":"hello world"}' \\
         --output out.wav
"""
import sys

import requests

OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    resp = requests.post(
        f"{OVOS_HOST}/deepgram/v1/speak",
        params={"model": "aura-asteria-en"},
        json={"text": text},
        headers={"Authorization": "Token ignored"},
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
