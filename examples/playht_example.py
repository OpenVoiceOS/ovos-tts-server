"""Drive the official PlayHT SDK (pyht) against an ovos-tts-server instance.

pyht hard-codes play.ht's hosts and exposes no base-URL option, so we
monkey-patch its HTTP API base to point at the server's ``/playht`` prefix.
The attribute name can vary between pyht versions — adjust the patch below to
match your installed version (inspect ``pyht.client``).

Prerequisites:
    pip install pyht
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/playht_example.py "hello world" out.wav
"""
import sys

import pyht.client as _pyht_client
from pyht import Client, TTSOptions
from pyht.client import Format


OVOS_HOST = "http://localhost:9666"

# --- monkey-patch: repoint pyht's HTTP API base at the OVOS /playht prefix ---
_pyht_client.API_URL = f"{OVOS_HOST}/playht/api/v2"


def main(text: str, out_path: str) -> None:
    client = Client(user_id="ignored", api_key="ignored")
    opts = TTSOptions(voice="default", format=Format.FORMAT_WAV)
    with open(out_path, "wb") as f:
        for chunk in client.tts(text, opts):
            f.write(chunk)
    client.close()
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
