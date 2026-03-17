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
