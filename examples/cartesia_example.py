"""Drive ovos-tts-server using the Cartesia Sonic-compatible endpoint.

The endpoint mirrors Cartesia's POST /tts/bytes API.

Prerequisites:
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/cartesia_example.py "hello world" out.wav

Equivalent curl:
    curl -X POST http://localhost:9666/cartesia/tts/bytes \\
         -H "Content-Type: application/json" \\
         -H "X-API-Key: ignored" \\
         -d '{"model_id":"sonic-english","transcript":"hello world","output_format":{"container":"wav"}}' \\
         --output out.wav
"""
import sys

import requests

OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    resp = requests.post(
        f"{OVOS_HOST}/cartesia/tts/bytes",
        json={
            "model_id": "sonic-english",
            "transcript": text,
            "voice": {"id": "default", "mode": "id"},
            "output_format": {"container": "wav"},
        },
        headers={"X-API-Key": "ignored"},
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
