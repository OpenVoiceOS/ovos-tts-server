# OpenVoiceOS TTS Server

[![PyPI](https://img.shields.io/pypi/v/ovos-tts-server)](https://pypi.org/project/ovos-tts-server/)
[![Python](https://img.shields.io/pypi/pyversions/ovos-tts-server)](https://pypi.org/project/ovos-tts-server/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE.md)

Turn **any** [OVOS TTS plugin](https://github.com/OpenVoiceOS) into a microservice — a small, stateless [FastAPI](https://fastapi.tiangolo.com/) app that exposes text-to-speech over HTTP.

- 🔌 **Plugin-agnostic** — serve Piper, Coqui, Azure, or any OVOS TTS plugin behind one consistent HTTP API.
- 🧩 **Drop-in cloud-API compatibility** — speak the ElevenLabs, OpenAI, Coqui, Google, Amazon Polly, Azure, MaryTTS, and Cartesia APIs so existing clients and SDKs work unmodified (see [API compatibility](docs/api-compatibility.md)).
- 🪶 **Stateless & tiny** — each request loads nothing extra; ideal for containers and horizontal scaling.
- 🎛️ **Format conversion** — return WAV out of the box, or mp3/ogg/flac/… with the optional `[audio]` extra.

---

## Install

```bash
pip install ovos-tts-server

# Optional: enable non-WAV output (mp3, ogg, flac, …) via pydub
pip install "ovos-tts-server[audio]"
```

You also need at least one TTS plugin, e.g. [Piper](https://github.com/OpenVoiceOS/ovos-tts-plugin-piper):

```bash
pip install ovos-tts-plugin-piper
```

## Quickstart

```bash
# Start the server with the Piper plugin
ovos-tts-server --engine ovos-tts-plugin-piper

# Synthesize over HTTP
curl "http://localhost:9666/v2/synthesize?utterance=hello%20world" -o hello.wav
```

## Command line

```
ovos-tts-server [-h] [--engine ENGINE] [--port PORT] [--host HOST] [--cache] [--lang LANG]
```

| Option | Default | Description |
| :--- | :--- | :--- |
| `--engine ENGINE` | — | TTS plugin to load (e.g. `ovos-tts-plugin-piper`) |
| `--port PORT` | `9666` | Port to bind |
| `--host HOST` | `0.0.0.0` | Host/interface to bind |
| `--cache` | off | Persist every synth to disk (cache across requests) |
| `--lang LANG` | `en-us` | Default language reported by the plugin |

## Configuration

The plugin is configured exactly as it would be inside the assistant — through `mycroft.conf`:

```json
{
  "tts": {
    "module": "ovos-tts-plugin-piper",
    "ovos-tts-plugin-piper": {
      "model": "alan-low"
    }
  }
}
```

See [docs/configuration.md](docs/configuration.md) for how voice and language flow from a request to the plugin.

## HTTP API

The native OVOS endpoints:

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/status` | Plugin name, supported languages, default voice/model |
| GET | `/v2/synthesize?utterance=<text>[&lang=…][&voice=…]` | Primary synthesis endpoint — returns a WAV file |
| GET | `/synthesize/<utterance>` | Legacy path-based synthesis endpoint |

Any extra query parameters on the synthesis endpoints are forwarded to the plugin as synthesis options. CORS is enabled for all origins.

```bash
curl http://localhost:9666/status
# {"status": "ok", "plugin": "ovos-tts-plugin-piper", "langs": ["en-us"], ...}
```

### Third-party API compatibility

The server can **additionally** expose the same plugin behind drop-in compatibility endpoints for popular cloud TTS APIs. Each vendor lives under its own URL prefix, so every compat layer is active at once with no path collisions. Auth tokens / API keys are accepted and silently ignored — put real auth in a reverse proxy if you need it.

| Vendor | Prefix | Key endpoint |
| :--- | :--- | :--- |
| ElevenLabs | `/elevenlabs` | `POST /v1/text-to-speech/{voice_id}` |
| OpenAI | `/openai` | `POST /v1/audio/speech` |
| Coqui | `/coqui` | `GET /api/tts` |
| Google Cloud TTS | `/google-tts` | `POST /v1/text:synthesize` |
| Amazon Polly | `/amazon-polly` | `POST /v1/speech` |
| Azure TTS | `/azure-tts` | `POST /cognitiveservices/v1` |
| MaryTTS | `/marytts` | `GET/POST /process` (+ root aliases) |
| Cartesia | `/cartesia` | `POST /tts/bytes` |

> **Kokoro / kokoro-fastapi** clients are OpenAI-compatible and need no dedicated prefix — point them at `/openai/v1/audio/speech`.

Most official SDKs accept a custom base URL; point them at `http://<host>:9666/<prefix>` and they work unmodified. See **[docs/api-compatibility.md](docs/api-compatibility.md)** for per-vendor endpoints, parameters, SDK snippets, and curl examples.

## Python API

```python
from ovos_tts_server import start_tts_server

app, engine = start_tts_server("ovos-tts-plugin-piper", cache=False)
# `app` is a FastAPI instance — mount it, test it, or run it with uvicorn
```

`create_app(tts_engine)` is also available if you want to build and inject the `TTSEngineWrapper` yourself.

## Docker

Build a small image that serves any plugin:

```dockerfile
FROM python:3.11-slim

RUN pip install --no-cache-dir "ovos-tts-server[audio]" {PLUGIN_HERE}

ENTRYPOINT ["ovos-tts-server", "--engine", "{PLUGIN_HERE}", "--cache"]
```

```bash
docker build . -t my_ovos_tts_plugin
docker run -p 8080:9666 my_ovos_tts_plugin
curl "http://localhost:8080/v2/synthesize?utterance=hello" -o hello.wav
```

Each plugin can ship its own Dockerfile in its repository using `ovos-tts-server`.

## Companion plugin

Consume this server from a voice assistant via the [companion TTS plugin](https://github.com/OpenVoiceOS/ovos-tts-server-plugin).

## Development

```bash
pip install -e ".[audio,test]"
pytest test/ -v
```

## Documentation

- [API compatibility reference](docs/api-compatibility.md) — every vendor prefix, endpoint, and SDK snippet
- [Voice & language configuration](docs/configuration.md) — how requests map to the plugin
- [Audio format conversion](docs/audio-formats.md) — `convert_audio()` and the `[audio]` extra
- [Architecture overview](docs/index.md) — classes, entry points, request flow

---

## Agent Integration

### UTCP — Universal Tool Calling Protocol

The server exposes a **UTCP manual** at `GET /utcp`.  Any UTCP-aware agent
(e.g. [ovos-tool-adapters](https://github.com/OpenVoiceOS/ovos-tool-adapters)
`UTCPToolBox`) can point at this URL and auto-discover every synthesis endpoint
without additional configuration.

No extra dependencies are needed — `GET /utcp` is always available.

**Example response (abbreviated):**
```json
{
  "utcp_version": "1.0.1",
  "manual_version": "1.0.0",
  "tools": [
    {
      "name": "tts_synthesize_v2",
      "description": "Synthesize speech from text (OVOS v2 endpoint)...",
      "inputs": {
        "type": "object",
        "properties": {
          "utterance": {"type": "string"},
          "voice":     {"type": "string"},
          "lang":      {"type": "string"}
        },
        "required": ["utterance"]
      },
      "tool_call_template": {
        "call_template_type": "http",
        "url": "http://localhost:9666/v2/synthesize",
        "http_method": "GET"
      }
    }
  ]
}
```

**ovos-tool-adapters config example:**
```json
{
  "utcp_config": {
    "providers": [
      {
        "provider_type": "http",
        "name": "ovos-tts",
        "url": "http://localhost:9666/utcp"
      }
    ]
  }
}
```

---

### MCP — Model Context Protocol

The server can optionally expose a **FastMCP server** mounted at `/mcp`,
providing a `synthesize` tool callable by any MCP-compatible agent (Claude
Desktop, Claude Code, etc.).

**Install the extra:**
```bash
pip install "ovos-tts-server[mcp]"
```

**Start with MCP enabled:**
```bash
ovos-tts-server --engine ovos-tts-plugin-piper --mcp
```

Or from Python:
```python
from ovos_tts_server import start_tts_server
app, engine = start_tts_server("ovos-tts-plugin-piper", enable_mcp=True)
```

The MCP server uses **streamable HTTP transport** (SSE-compatible) and is
mounted alongside the existing FastAPI app — no separate process needed.

**Claude Desktop `claude_desktop_config.json` example:**
```json
{
  "mcpServers": {
    "ovos-tts": {
      "transport": "http",
      "url": "http://localhost:9666/mcp"
    }
  }
}
```

**`synthesize` tool:**

| Parameter | Type   | Required | Description                          |
|-----------|--------|----------|--------------------------------------|
| `text`    | string | yes      | Text to synthesize                   |
| `voice`   | string | no       | Voice/speaker identifier             |
| `lang`    | string | no       | BCP-47 language code (e.g. `en-us`)  |

Returns a JSON object:
```json
{
  "mime_type": "audio/wav",
  "data": "<base64-encoded WAV>",
  "path": "/tmp/ovos_synth_abc123.wav",
  "phonemes": null
}
```

---

## Credits

Developed by [TigreGótico](https://tigregotico.pt) for
[OpenVoiceOS](https://openvoiceos.org).

[![NGI0 Commons Fund](./ngi.png)](https://nlnet.nl/project/OpenVoiceOS)

This project was funded through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund),
a fund established by [NLnet](https://nlnet.nl) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu) programme, under
the aegis of [DG Communications Networks, Content and Technology](https://commission.europa.eu/about-european-commission/departments-and-executive-agencies/communications-networks-content-and-technology_en)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429).
