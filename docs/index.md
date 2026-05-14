# ovos-tts-server

HTTP server that exposes any OVOS TTS plugin as a REST service using FastAPI.

## Overview

`ovos-tts-server` loads an OVOS TTS plugin at startup and serves synthesis requests over HTTP. It is stateless: each request calls the plugin and returns the generated audio file.

## Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/status` | Plugin name, supported languages, default voice/model |
| GET | `/v2/synthesize?utterance=<text>[&lang=...][&voice=...]` | Primary synthesis endpoint — returns WAV audio |
| GET | `/synthesize/<utterance>` | Legacy path-based synthesis endpoint |
| GET/POST | `/process` | MaryTTS-compatible synthesis endpoint |
| GET | `/locales` | MaryTTS-compatible: newline-separated locale list |
| GET | `/voices` | MaryTTS-compatible: newline-separated voice list |

## Key Classes

- `TTSEngineWrapper` — loads and wraps a TTS plugin for dependency injection — `ovos_tts_server/__init__.py:21`
- `MaryTTSInput` — Pydantic request model for `/process` — `ovos_tts_server/__init__.py:8`
- `create_app(tts_engine)` — factory that returns the configured FastAPI app — `ovos_tts_server/__init__.py:76`
- `start_tts_server(tts_plugin, cache)` — top-level entry point used by `__main__` — `ovos_tts_server/__init__.py:197`

## Entry Point

```
ovos-tts-server --engine <plugin_name> [--host 0.0.0.0] [--port 9666] [--cache]
```

## CORS

All origins are allowed unconditionally (`CORSMiddleware(allow_origins=["*"])`).

## Compatibility Routers

Seven vendor-prefixed routers make the server a drop-in replacement for popular TTS APIs:

| Vendor | Prefix | Key Endpoint |
| :--- | :--- | :--- |
| ElevenLabs | `/elevenlabs` | `POST /elevenlabs/v1/text-to-speech/{voice_id}` |
| OpenAI TTS | `/openai` | `POST /openai/v1/audio/speech` |
| Coqui TTS | `/coqui` | `GET /coqui/api/tts?text=...` |
| Google Cloud TTS | `/google-tts` | `POST /google-tts/v1/text:synthesize` |
| Amazon Polly | `/amazon-polly` | `POST /amazon-polly/v1/speech` |
| Azure Cognitive TTS | `/azure-tts` | `POST /azure-tts/cognitiveservices/v1` |
| Piper | `/piper` | `GET /piper/?text=...` |

Authentication is accepted but ignored — any key/token/header works.

## Documentation

- [API Compatibility Reference](api-compatibility.md)
- [Audio Format Conversion](audio-formats.md)
- [Voice & Language Configuration](configuration.md)
