# OpenVoiceOS TTS Server

Turn any OVOS TTS plugin into a microservice — a small, stateless FastAPI app that exposes a TTS plugin over HTTP.

## Install

```bash
pip install ovos-tts-server

# Optional: enable non-WAV output (mp3, ogg, flac, ...) via pydub
pip install "ovos-tts-server[audio]"
```

## Companion plugin

Use in your voice assistant via the [companion TTS plugin](https://github.com/OpenVoiceOS/ovos-tts-server-plugin).

## Configuration

The plugin is configured the same way as if it were running inside the assistant — through `mycroft.conf`:

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

## Usage

```bash
ovos-tts-server --help
usage: ovos-tts-server [-h] [--engine ENGINE] [--port PORT] [--host HOST] [--cache]

options:
  -h, --help       show this help message and exit
  --engine ENGINE  tts plugin to be used
  --port PORT      port number (default: 9666)
  --host HOST      host (default: 0.0.0.0)
  --cache          save every synth to disk
```

Example — serve the [Piper plugin](https://github.com/OpenVoiceOS/ovos-tts-plugin-piper):

```bash
ovos-tts-server --engine ovos-tts-plugin-piper --cache
```

Then GET `http://localhost:9666/synthesize/hello`.

## Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/status` | Plugin name, supported languages, default voice/model |
| GET | `/v2/synthesize?utterance=<text>[&lang=...][&voice=...]` | Primary synthesis endpoint — returns WAV audio |
| GET | `/synthesize/<utterance>` | Legacy path-based synthesis endpoint |

CORS is enabled for all origins.

### Third-party API compatibility

The server can additionally expose its underlying TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs — MaryTTS, ElevenLabs, OpenAI, Coqui, Google Cloud TTS, Amazon Polly, Azure, Piper, and PlayHT. Each vendor lives under its own URL prefix so multiple compat layers coexist with no path collisions. Auth tokens are accepted and silently ignored — wrap behind a reverse proxy if you need real auth.

**PlayHT** (`/playht/api/v2/tts/stream`) accepts `text`, `voice`, `output_format`, `quality`, `speed`, and `sample_rate`. The server also implements PlayHT's `/api/v4/sdk-auth` inference-coordinates handshake, so the official `pyht` SDK works as a drop-in by overriding only its coordinates `api_url` to the `/playht` prefix (see `examples/playht_example.py`).

See [docs/api-compatibility.md](docs/api-compatibility.md) for the full reference.

## Documentation

- [Configuration & voice/language flow](docs/configuration.md)
- [Audio format conversion](docs/audio-formats.md)
- [API compatibility reference](docs/api-compatibility.md)

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
```

Then GET `http://localhost:8080/synthesize/hello`.

Each plugin can ship its own Dockerfile in its repository using `ovos-tts-server`.

## Development

```bash
pip install -e ".[audio,test]"
pytest test/ -v
```

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
