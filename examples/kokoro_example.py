"""Drive ovos-tts-server using the Kokoro-compatible endpoint.

The endpoint accepts the same body as OpenAI /v1/audio/speech with Kokoro voice names.

Prerequisites:
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/kokoro_example.py "hello world" out.wav

Equivalent curl:
    curl -X POST http://localhost:9666/kokoro/v1/audio/speech \\
         -H "Content-Type: application/json" \\
         -d '{"model":"kokoro","input":"hello world","voice":"af_heart","response_format":"wav"}' \\
         --output out.wav
"""
import sys

import requests

OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    resp = requests.post(
        f"{OVOS_HOST}/kokoro/v1/audio/speech",
        json={
            "model": "kokoro",
            "input": text,
            "voice": "af_heart",
            "response_format": "wav",
        },
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.wav>")
    main(sys.argv[1], sys.argv[2])
