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

This document currently covers: **Piper (`/piper`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## Piper (`/piper`)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/piper/` | Synthesize speech |

```bash
curl "http://localhost:9666/piper/?text=hello+world&voice=voice1" -o out.wav
```

Query params: `text` (required), `voice` (optional).
