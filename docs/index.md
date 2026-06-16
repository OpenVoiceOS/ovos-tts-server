# ovos-tts-server — Architecture Overview

An HTTP server that exposes any OVOS TTS plugin as a REST service using
[FastAPI](https://fastapi.tiangolo.com/). It is **stateless**: each request
loads a plugin (once, at startup), calls it, and returns the generated audio.

For installation and usage, start with the [README](../README.md).

## Request flow

```
HTTP request
   │
   ▼
FastAPI route (core endpoint or compat router)
   │   translate vendor params → voice=/lang= kwargs
   ▼
TTSEngineWrapper.synthesize(text, **kwargs)
   │   → (wav_path, phonemes)
   ▼
convert_audio(wav_path, fmt)   # only if a non-WAV format was requested
   │   → (audio_bytes, mime_type)
   ▼
HTTP response (audio file / bytes / base64 JSON, per vendor)
```

## Native endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/status` | Plugin name, supported languages, default voice/model |
| GET | `/v2/synthesize?utterance=<text>[&lang=…][&voice=…]` | Primary synthesis endpoint — returns WAV audio |
| GET | `/synthesize/<utterance>` | Legacy path-based synthesis endpoint |

Extra query parameters are forwarded to the plugin as synthesis options.

## Compatibility routers

Drop-in compatibility endpoints for popular cloud TTS APIs are registered
alongside the native endpoints, each under its own URL prefix:

| Vendor | Prefix |
| :--- | :--- |
| ElevenLabs | `/elevenlabs` |
| OpenAI | `/openai` |
| Coqui | `/coqui` |
| Google Cloud TTS | `/google-tts` |
| Amazon Polly | `/amazon-polly` |
| Azure TTS | `/azure-tts` |
| MaryTTS | `/marytts` (+ root aliases) |
| PlayHT | `/playht` |

Routers are wired up in `create_app()` (`ovos_tts_server/__init__.py`). An Azure
WebSocket bridge router also exists but is not registered by default. See
[api-compatibility.md](api-compatibility.md) for the full reference.

## Key classes & functions

All defined in `ovos_tts_server/__init__.py`:

- **`TTSEngineWrapper`** — loads and wraps a TTS plugin for dependency
  injection; exposes `synthesize()`, `voices`, and `langs`.
- **`create_app(tts_engine) -> FastAPI`** — factory that builds the FastAPI app,
  wires the native endpoints and every compat router, and enables permissive
  CORS.
- **`start_tts_server(tts_plugin, cache=False) -> (FastAPI, TTSEngineWrapper)`** —
  top-level entry point used by `__main__`; constructs the wrapper and the app.

## Entry point

```bash
ovos-tts-server --engine <plugin_name> [--host 0.0.0.0] [--port 9666] [--cache] [--lang en-us]
```

`__main__.py` parses the CLI, calls `start_tts_server(...)`, and runs the app
with `uvicorn`.

## CORS

All origins are allowed unconditionally
(`CORSMiddleware(allow_origins=["*"])`). Restrict this at your reverse proxy if
the server is exposed publicly.

## Documentation map

- [API Compatibility Reference](api-compatibility.md) — every vendor prefix, endpoint, parameter, and SDK snippet
- [Voice & Language Configuration](configuration.md) — how a request maps to the plugin
- [Audio Format Conversion](audio-formats.md) — `convert_audio()` and the `[audio]` extra
