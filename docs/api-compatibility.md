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
