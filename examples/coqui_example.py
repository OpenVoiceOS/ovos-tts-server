"""Drive the Coqui TTS server protocol against ovos-tts-server.

Coqui TTS's HTTP server has no official Python client; raw `requests`
is canonical (matches `coqui-ai/TTS/.../server.py`).

Prerequisites:
    pip install requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/coqui_example.py "hello world" out.wav
"""
import sys

import requests


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    r = requests.get(
        f"{OVOS_HOST}/coqui/api/tts",
        params={"text": text},
    )
    r.raise_for_status()
    with open(out_path, "wb") as fp:
        fp.write(r.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
