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

Third-party API compatibility endpoints (MaryTTS, ElevenLabs, OpenAI, Coqui, Google, Polly, Azure, Piper) are added by their respective compat-router PRs and live under per-vendor URL prefixes. See [api-compatibility.md](api-compatibility.md).

## Key Classes

- `TTSEngineWrapper` — loads and wraps a TTS plugin for dependency injection
- `create_app(tts_engine)` — factory that returns the configured FastAPI app
- `start_tts_server(tts_plugin, cache)` — top-level entry point used by `__main__`

All defined in `ovos_tts_server/__init__.py`.

## Entry Point

```
ovos-tts-server --engine <plugin_name> [--host 0.0.0.0] [--port 9666] [--cache]
```

## CORS

All origins are allowed unconditionally (`CORSMiddleware(allow_origins=["*"])`).

## Documentation

- [API Compatibility Reference](api-compatibility.md)
- [Audio Format Conversion](audio-formats.md)
- [Voice & Language Configuration](configuration.md)
