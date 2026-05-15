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

**Upstream sources**:
- Python SDK: [openai/openai-python — `resources/audio/speech.py`](https://github.com/openai/openai-python/blob/main/src/openai/resources/audio/speech.py)
- API reference: [OpenAI Audio Speech docs](https://platform.openai.com/docs/api-reference/audio/createSpeech)
- Node SDK: [openai/openai-node](https://github.com/openai/openai-node)


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

### Pointing apps at this server

The OpenAI SDK reads `OPENAI_BASE_URL` (or the `base_url=` constructor arg).
Point it at `http://localhost:9666/openai/v1`.

**Python SDK** ([`openai`](https://github.com/openai/openai-python)):
```python
from openai import OpenAI
client = OpenAI(api_key="ignored", base_url="http://localhost:9666/openai/v1")
client.audio.speech.create(model="tts-1", voice="alloy", input="hello")
```

**Environment variables** (works with most OpenAI-compatible clients incl. LangChain, LiteLLM, OpenWebUI, etc.):
```bash
export OPENAI_BASE_URL=http://localhost:9666/openai/v1
export OPENAI_API_KEY=ignored
```

**Node SDK** (`openai`):
```js
new OpenAI({ apiKey: "ignored", baseURL: "http://localhost:9666/openai/v1" });
```

**curl**:
```bash
curl -X POST -H "Authorization: Bearer x" -H "Content-Type: application/json" \
  -d '{"model":"tts-1","voice":"alloy","input":"hello"}' \
  http://localhost:9666/openai/v1/audio/speech -o out.mp3
```
