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

This document currently covers: **ElevenLabs (`/elevenlabs`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## ElevenLabs (`/elevenlabs`)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/elevenlabs/v1/voices` | List available voices |
| GET | `/elevenlabs/v1/models` | List available models |
| POST | `/elevenlabs/v1/text-to-speech/{voice_id}` | Synthesize speech |

**Auth:** `xi-api-key` header (ignored).

```bash
# List voices
curl -H "xi-api-key: fake" http://localhost:9666/elevenlabs/v1/voices

# Synthesize
curl -X POST \
  -H "xi-api-key: fake" \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world"}' \
  "http://localhost:9666/elevenlabs/v1/text-to-speech/default?output_format=mp3_44100_128" \
  -o out.mp3
```

`output_format` values: `mp3_44100_128`, `pcm_16000`, `ulaw_8000`, etc. Falls back to WAV if pydub absent.

---
