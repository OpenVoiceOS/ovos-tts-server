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

The server can additionally expose its underlying TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs — MaryTTS, ElevenLabs, OpenAI, Coqui, Google Cloud TTS, Amazon Polly, Azure, Piper, and Cartesia. Each vendor lives under its own URL prefix so multiple compat layers coexist with no path collisions. Auth tokens are accepted and silently ignored — wrap behind a reverse proxy if you need real auth.

**Cartesia** (`/cartesia/tts/bytes`) accepts `model_id`, `transcript`, `voice` (object with optional `id` key), and `output_format` (object with `container` field). The official `cartesia` SDK works by overriding its `base_url` to the `/cartesia` prefix (see `examples/cartesia_example.py`).

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

## Credits

Developed by [TigreGótico](https://tigregotico.pt) for
[OpenVoiceOS](https://openvoiceos.org).

[![NGI0 Commons Fund](./ngi.png)](https://nlnet.nl/project/OpenVoiceOS)

This project was funded through the [NGI0 Commons Fund](https://nlnet.nl/commonsfund),
a fund established by [NLnet](https://nlnet.nl) with financial support from the
European Commission's [Next Generation Internet](https://ngi.eu) programme, under
the aegis of [DG Communications Networks, Content and Technology](https://commission.europa.eu/about-european-commission/departments-and-executive-agencies/communications-networks-content-and-technology_en)
under grant agreement No [101135429](https://cordis.europa.eu/project/id/101135429).
