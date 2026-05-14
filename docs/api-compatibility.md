# Third-Party API Compatibility

`ovos-tts-server` can expose its underlying OVOS TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs. This lets existing apps that already speak ElevenLabs, OpenAI, Google, Polly, Azure, Coqui, or Piper use OVOS without code changes — just point them at this server.

Each vendor's endpoints live under a dedicated URL prefix so multiple compat layers can coexist in one FastAPI app with no path collisions:

| Vendor | Prefix | Status |
|---|---|---|
| ElevenLabs | `/elevenlabs/v1/...` | see #PR-1 |
| OpenAI TTS | `/openai/v1/...` | see #PR-2 |
| Coqui | `/coqui/api/tts` | see #PR-3 |
| Google Cloud TTS | `/google-tts/v1/...` | see #PR-4 |
| Amazon Polly | `/amazon-polly/v1/...` | see #PR-5 |
| Azure Cognitive Services | `/azure-tts/...` | see #PR-6 |
| Piper HTTP | `/piper/` | see #PR-7 |

All routers accept any auth token / API key supplied by the client and silently ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion across `wav`, `mp3`, `ogg`, `flac`, `pcm`, etc. is provided by `ovos_tts_server.audio_utils.convert_audio()`. Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable non-WAV outputs via `pydub`.

Per-vendor documentation (request schema, query params, response shape) is added by each compat-router PR.
