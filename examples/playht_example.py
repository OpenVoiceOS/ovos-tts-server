"""Drive the official PlayHT SDK (``pyht``) against an ovos-tts-server instance.

ovos-tts-server implements PlayHT's ``/api/v4/sdk-auth`` inference-coordinates
handshake, so a stock ``pyht.Client`` works once its coordinates ``api_url`` is
repointed at the server's ``/playht`` prefix — no monkey-patching of SDK
internals. Use the HTTP protocol with ``auto_connect=False`` so the SDK never
reaches out to play.ht's gRPC lease/warmup endpoints.

Prerequisites:
    pip install pyht
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/playht_example.py "hello world" out.wav
"""
import sys

from pyht import Client, TTSOptions
from pyht.client import Format
from pyht.inference_coordinates import InferenceCoordinatesOptions


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    client = Client(
        user_id="ignored",
        api_key="ignored",
        auto_connect=False,
        advanced=Client.AdvancedOptions(
            inference_coordinates_options=InferenceCoordinatesOptions(
                api_url=f"{OVOS_HOST}/playht/api/v4",
            ),
        ),
    )
    opts = TTSOptions(voice="default", format=Format.FORMAT_WAV)
    with open(out_path, "wb") as f:
        for chunk in client.tts(text, opts, voice_engine="Play3.0-mini", protocol="http"):
            f.write(chunk)
    client.close()
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
