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

This document currently covers: **Amazon Polly (`/amazon-polly`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## Amazon Polly (`/amazon-polly`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/amazon-polly/v1/speech` | Synthesize speech |

**Auth:** `Authorization` header with AWS SigV4 (accepted, ignored).

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"Text": "hello world", "VoiceId": "Joanna", "OutputFormat": "mp3"}' \
  http://localhost:9666/amazon-polly/v1/speech \
  -o out.mp3
```

`OutputFormat` values: `mp3`, `ogg_vorbis`, `pcm`, `json` (json → WAV stub).

---
