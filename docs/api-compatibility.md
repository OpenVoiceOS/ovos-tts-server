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

This document currently covers: **OpenAI TTS (`/openai`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## OpenAI TTS (`/openai`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/openai/v1/audio/speech` | Synthesize speech |

**Auth:** `Authorization: Bearer <any>` (ignored).

```bash
curl -X POST \
  -H "Authorization: Bearer fake" \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "hello world", "voice": "alloy", "response_format": "mp3"}' \
  http://localhost:9666/openai/v1/audio/speech \
  -o out.mp3
```

Valid `voice` values: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`.
Valid `model` values: `tts-1`, `tts-1-hd`.
`speed` range: 0.25–4.0.
`input` max length: 4096 characters.

---
