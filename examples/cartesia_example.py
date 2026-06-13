"""Drive the official Cartesia Python SDK against an ovos-tts-server instance.

The Cartesia SDK accepts a ``base_url`` override — point it at the server's
``/cartesia`` prefix and it will POST to ``/cartesia/tts/bytes``.

Prerequisites:
    pip install cartesia
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/cartesia_example.py "hello world" out.wav
"""
import sys

from cartesia import Cartesia


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    client = Cartesia(api_key="ignored", base_url=f"{OVOS_HOST}/cartesia")
    chunks = client.tts.bytes(
        model_id="sonic-2",
        transcript=text,
        voice={"mode": "id", "id": "default"},
        output_format={"container": "wav", "sample_rate": 22050, "encoding": "pcm_s16le"},
    )
    with open(out_path, "wb") as f:
        for chunk in chunks:
            f.write(chunk)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
