# Custom containers for ovos-tts-server

The base image provides only the server framework.  Swap in any OVOS TTS plugin
by layering it on top of the base image.

## Quick example: Piper (local neural TTS, no API key needed)

```dockerfile
FROM ghcr.io/openvoiceos/ovos-tts-server:dev

RUN pip install --no-cache-dir --pre ovos-tts-plugin-piper

COPY config/mycroft.conf /config/mycroft/mycroft.conf

CMD ["--engine", "ovos-tts-plugin-piper", \
     "--host", "0.0.0.0", "--port", "9666", "--cache"]
```

`config/mycroft.conf` for this image:

```json
{
  "tts": {
    "module": "ovos-tts-plugin-piper",
    "ovos-tts-plugin-piper": {
      "model": "alan-low",
      "cache": true
    }
  }
}
```

Build and run:

```bash
docker build -t my-tts-piper .
docker run -p 8080:9666 my-tts-piper
curl "http://localhost:8080/v2/synthesize?utterance=hello+world" -o hello.wav
```

## Compose override for the custom image

Create `docker-compose.override.yml` alongside the root `docker-compose.yml`:

```yaml
services:
  ovos-tts:
    build: .
    image: my-tts-piper
    command:
      - "--engine"
      - "ovos-tts-plugin-piper"
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "9666"
      - "--cache"
    volumes:
      - ./config:/config/mycroft
      - tts-cache:/tmp/tts_cache

volumes:
  tts-cache:
```

Run with `docker compose up`.

## Other plugin options

| Plugin | Notes |
|---|---|
| `ovos-tts-plugin-piper` | Fast neural TTS, many voices and languages |
| `ovos-tts-plugin-mimic3` | Mycroft Mimic 3, lightweight |

## MCP and UTCP

`GET /utcp` needs no change to the image. To serve MCP, install `ovos-tts-server[mcp]` in the image and add `--mcp` to the start command. [AI agents: Docker](ai-agents.md#docker) has the steps.
