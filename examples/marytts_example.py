"""Drive the MaryTTS HTTP protocol against ovos-tts-server.

MaryTTS has no Python client SDK (the canonical clients are Java); raw
`requests` matches what `MaryHttpServer.java` accepts.

Prerequisites:
    pip install requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/marytts_example.py "hello world" out.wav
"""
import sys

import requests


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    r = requests.post(
        f"{OVOS_HOST}/marytts/process",
        params={
            "INPUT_TEXT": text,
            "INPUT_TYPE": "TEXT",
            "OUTPUT_TYPE": "AUDIO",
            "AUDIO": "WAVE_FILE",
            "LOCALE": "en_US",
        },
    )
    r.raise_for_status()
    with open(out_path, "wb") as fp:
        fp.write(r.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
