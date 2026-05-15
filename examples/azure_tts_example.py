"""Drive Microsoft Azure Speech REST synthesis against ovos-tts-server.

The official `azure-cognitiveservices-speech` SDK works against
this server too — see docs/voice-pihole.md for the SDK + nginx setup
(the SDK rejects ws:// URLs so TLS termination is mandatory). For local
testing, raw REST is simpler:

Prerequisites:
    pip install requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/azure_tts_example.py "hello world" out.mp3
"""
import sys

import requests


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    ssml = (
        f"<speak version='1.0' xml:lang='en-US'>"
        f"<voice name='en-US-JennyNeural' xml:lang='en-US'>{text}</voice>"
        f"</speak>"
    )
    r = requests.post(
        f"{OVOS_HOST}/azure-tts/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "Ocp-Apim-Subscription-Key": "ignored",
        },
    )
    r.raise_for_status()
    with open(out_path, "wb") as fp:
        fp.write(r.content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
