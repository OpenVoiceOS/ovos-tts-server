"""Call the PlayHT-compatible endpoint on an ovos-tts-server instance.

Note: PlayHT's official ``pyht`` SDK hard-codes play.ht's own API/gRPC hosts and
offers no base-URL override, so it cannot be pointed at a self-hosted server.
This script therefore issues the same ``POST /api/v2/tts/stream`` request the SDK
would send, using ``requests``.

Prerequisites:
    pip install requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/playht_example.py "hello world" out.wav
"""
import sys

import requests


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    resp = requests.post(
        f"{OVOS_HOST}/playht/api/v2/tts/stream",
        json={"text": text, "voice": "default", "output_format": "wav"},
        headers={"Authorization": "Bearer ignored", "X-User-ID": "ignored"},
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
