"""Drive the official boto3 Polly client against an ovos-tts-server instance.

boto3 accepts `endpoint_url=` cleanly — no monkey-patching needed.

Prerequisites:
    pip install boto3
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/amazon_polly_example.py "hello world" out.mp3
"""
import sys

import boto3


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    polly = boto3.client(
        "polly",
        endpoint_url=f"{OVOS_HOST}/amazon-polly",
        region_name="us-east-1",
        aws_access_key_id="ignored",
        aws_secret_access_key="ignored",
    )
    response = polly.synthesize_speech(
        Text=text,
        VoiceId="Joanna",
        OutputFormat="mp3",
        Engine="neural",
    )
    with open(out_path, "wb") as fp:
        fp.write(response["AudioStream"].read())
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
