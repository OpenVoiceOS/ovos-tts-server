# API Compatibility Reference

`ovos-tts-server` exposes its underlying OVOS TTS plugin behind drop-in
compatibility endpoints for popular cloud TTS APIs. Each vendor lives
under its own URL prefix so multiple compat layers coexist with no path
collisions.

All routers accept any auth token / API key from the client and silently
ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion is provided by `ovos_tts_server.audio_utils.convert_audio()`.
Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable
non-WAV outputs via `pydub`.

This document currently covers: **Google Cloud TTS (`/google-tts`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## Google Cloud TTS (`/google-tts`)

**Upstream sources**:
- Python SDK: [googleapis/python-texttospeech](https://github.com/googleapis/python-texttospeech) — REST transport in [`services/text_to_speech/transports/rest.py`](https://github.com/googleapis/python-texttospeech/blob/main/google/cloud/texttospeech_v1/services/text_to_speech/transports/rest.py)
- API reference: [`texttospeech.googleapis.com/v1/text:synthesize`](https://cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize)
- Proto definitions: [googleapis/googleapis — `google/cloud/texttospeech/v1/cloud_tts.proto`](https://github.com/googleapis/googleapis/blob/master/google/cloud/texttospeech/v1/cloud_tts.proto)


| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/google-tts/v1/text:synthesize` | Synthesize speech |

**Auth:** `Authorization: Bearer <any>` or `x-goog-api-key` header (ignored).

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"text": "hello world"},
    "voice": {"languageCode": "en-US", "name": "en-US-Standard-A"},
    "audioConfig": {"audioEncoding": "LINEAR16"}
  }' \
  http://localhost:9666/google-tts/v1/text:synthesize
```

Response: `{"audioContent": "<base64-encoded audio>"}`.
`audioEncoding` values: `LINEAR16`, `MP3`, `OGG_OPUS`, `MULAW`, `ALAW`.
Either `input.text` or `input.ssml` must be provided.

---

### Pointing apps at this server

The Google Cloud TTS Python SDK accepts a custom `api_endpoint` in `client_options`. Set it to this server (note: SDKs assume HTTPS — use a reverse proxy with TLS for production, or stick to direct REST calls).

**REST / curl** (drop-in: change only the host):
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"input":{"text":"hello"},"voice":{"languageCode":"en-US"},"audioConfig":{"audioEncoding":"MP3"}}' \
  http://localhost:9666/google-tts/v1/text:synthesize
```

The response is `{"audioContent": "<base64 mp3/wav>"}` — same shape as the real API; decode with `base64 -d`.

**Home Assistant** (`google_translate` won't work — different API; for Google Cloud TTS the official integration requires a service-account JSON and HTTPS endpoint, so this compat layer is best used via custom integrations / scripts that hit the REST endpoint directly).

**Python (raw `requests`)** instead of the SDK:
```python
import base64, requests
r = requests.post(
    "http://localhost:9666/google-tts/v1/text:synthesize",
    json={"input": {"text": "hello"},
          "voice": {"languageCode": "en-US"},
          "audioConfig": {"audioEncoding": "MP3"}},
)
open("out.mp3", "wb").write(base64.b64decode(r.json()["audioContent"]))
```
