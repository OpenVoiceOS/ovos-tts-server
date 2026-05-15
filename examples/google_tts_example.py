"""Drive the official `google-cloud-texttospeech` SDK against ovos-tts-server.

The SDK builds host-only endpoints, so we pass `api_endpoint` for the host
and monkey-patch the `AuthorizedSession` so the wss:// → http:// scheme
swap lands on our local server. In production deployments the nginx
config in docs/voice-pihole.md (TLS on texttospeech.googleapis.com) makes
the monkey-patch unnecessary.

Prerequisites:
    pip install google-cloud-texttospeech requests
    ovos-tts-server --engine <some-ovos-tts-plugin> --port 9666

Usage:
    python examples/google_tts_example.py "hello world" out.mp3
"""
import sys
from urllib.parse import urlparse

from google.auth.credentials import AnonymousCredentials
from google.auth.transport.requests import AuthorizedSession
from google.cloud import texttospeech_v1


OVOS_HOST = "http://localhost:9666"


def main(text: str, out_path: str) -> None:
    # Rewrite outbound URLs from the SDK so they land on our prefix.
    real_request = AuthorizedSession.request

    def patched(self, method, url, *args, **kwargs):
        for host in ("https://texttospeech.googleapis.com",
                     "https://localhost", "http://localhost"):
            if url.startswith(host):
                url = OVOS_HOST + "/google-tts" + url[len(host):]
                break
        return real_request(self, method, url, *args, **kwargs)

    AuthorizedSession.request = patched

    client = texttospeech_v1.TextToSpeechClient(
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": urlparse(OVOS_HOST).netloc},
        transport="rest",
    )
    response = client.synthesize_speech(
        input=texttospeech_v1.SynthesisInput(text=text),
        voice=texttospeech_v1.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech_v1.SsmlVoiceGender.NEUTRAL,
        ),
        audio_config=texttospeech_v1.AudioConfig(
            audio_encoding=texttospeech_v1.AudioEncoding.MP3,
        ),
    )
    with open(out_path, "wb") as fp:
        fp.write(response.audio_content)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <text> <out.mp3>")
    main(sys.argv[1], sys.argv[2])
