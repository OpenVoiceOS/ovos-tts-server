"""Drive the Piper HTTP server protocol against ovos-tts-server.

Piper's HTTP server (rhasspy/piper/examples/http_server.py) accepts a
plain POST with the text as the body. No official client SDK; raw
`requests` is canonical.

Prerequisites:
    pip install requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/piper_example.py "hello world" out.wav
"""
import sys

import requests


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    r = requests.post(
        f"{OVOS_HOST}/piper/",
        data=text.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
    )
    r.raise_for_status()
    with open(out_path, "wb") as fp:
        fp.write(r.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
