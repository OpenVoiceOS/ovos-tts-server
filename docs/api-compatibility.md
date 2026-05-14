# Third-Party API Compatibility

`ovos-tts-server` can expose its underlying OVOS TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs. This lets existing apps that already speak a vendor's HTTP API use OVOS as a drop-in replacement — no client code changes required.

Each vendor's endpoints live under a dedicated URL prefix so multiple compat layers can coexist in one FastAPI app with no path collisions. Concrete vendor sections (request schema, query params, response shape, curl examples) are added by each compat-router PR as it lands.

All routers accept any auth token / API key supplied by the client and silently ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion across `wav`, `mp3`, `ogg`, `flac`, `pcm`, etc. is provided by `ovos_tts_server.audio_utils.convert_audio()`. Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable non-WAV outputs via `pydub`.

This document currently covers: **MaryTTS** (no prefix — mounted at root).

---

## MaryTTS

The MaryTTS compat router exposes the classic MaryTTS HTTP endpoints at the server root, so apps that already speak MaryTTS can swap in OVOS without changes.

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/locales` | Newline-separated supported locales |
| GET | `/voices` | Newline-separated voices, format `name locale gender plugin` |
| GET/POST | `/process` | Synthesize — returns `audio/wav` |

### `/process` parameters

| Name | Type | Notes |
| :--- | :--- | :--- |
| `INPUT_TEXT` | str (required) | Text or SSML to synthesize |
| `INPUT_TYPE` | `TEXT` \| `SSML` | Default `TEXT` |
| `LOCALE` | str | Mapped to `lang=` plugin kwarg |
| `VOICE` | str | Underscores converted to spaces, mapped to `voice=` |
| `OUTPUT_TYPE` | str | Accepted, ignored (always `AUDIO`) |
| `AUDIO` | str | Accepted, ignored (always `WAVE_FILE`) |

### Example

```bash
# List locales
curl http://localhost:9666/locales

# List voices
curl http://localhost:9666/voices

# Synthesize
curl -G http://localhost:9666/process \
  --data-urlencode "INPUT_TEXT=hello world" \
  --data-urlencode "LOCALE=en_US" \
  -o out.wav
```
