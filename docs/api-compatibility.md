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

**Upstream sources**:
- Python SDK: [elevenlabs/elevenlabs-python](https://github.com/elevenlabs/elevenlabs-python) — `text_to_speech.convert()` builds `POST /v1/text-to-speech/{voice_id}`
- API reference: [ElevenLabs Text-to-Speech docs](https://elevenlabs.io/docs/api-reference/text-to-speech)
- Node SDK: [elevenlabs/elevenlabs-js](https://github.com/elevenlabs/elevenlabs-js)


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

### Pointing apps at this server

ElevenLabs SDKs accept a custom base URL. Point it at `http://localhost:9666/elevenlabs`.

**Python SDK** ([`elevenlabs`](https://github.com/elevenlabs/elevenlabs-python)):
```python
from elevenlabs.client import ElevenLabs
client = ElevenLabs(api_key="ignored", base_url="http://localhost:9666/elevenlabs")
```

**Environment variable** (community convention used by many apps):
```bash
export ELEVENLABS_BASE_URL=http://localhost:9666/elevenlabs
export ELEVENLABS_API_KEY=ignored
```

**Node SDK** (`@elevenlabs/elevenlabs-js`):
```js
new ElevenLabsClient({ apiKey: "ignored", baseUrl: "http://localhost:9666/elevenlabs" });
```

**curl**:
```bash
curl -X POST -H "xi-api-key: x" -H "Content-Type: application/json" \
  -d '{"text": "hello"}' \
  "http://localhost:9666/elevenlabs/v1/text-to-speech/default" -o out.mp3
```
