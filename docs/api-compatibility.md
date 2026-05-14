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

This document currently covers: **Azure Cognitive Services TTS (`/azure-tts`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## Azure Cognitive Services TTS (`/azure-tts`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/azure-tts/cognitiveservices/v1` | Synthesize from SSML |

**Auth:** `Ocp-Apim-Subscription-Key` header (accepted, ignored).

```bash
curl -X POST \
  -H "Ocp-Apim-Subscription-Key: fake" \
  -H "Content-Type: application/ssml+xml" \
  -H "X-Microsoft-OutputFormat: audio-24khz-48kbitrate-mono-mp3" \
  -d '<speak><voice name="en-US-JennyNeural" xml:lang="en-US">hello</voice></speak>' \
  http://localhost:9666/azure-tts/cognitiveservices/v1 \
  -o out.mp3
```

Body must be valid SSML XML. Voice name and `xml:lang` are extracted via regex and forwarded as `voice=` and `lang=`.

---
