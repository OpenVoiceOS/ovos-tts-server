# Custom containers for ovos-tts-server

The base image provides only the server framework.  Swap in any OVOS TTS plugin
by layering it on top of the base image.

## Quick example: Piper (local neural TTS, no API key needed)

```dockerfile
FROM ghcr.io/openvoiceos/ovos-tts-server:dev

RUN pip install --no-cache-dir ovos-tts-plugin-piper

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

## MCP / UTCP extras

`GET /utcp` is always available and returns a UTCP-1.0 tool manifest describing all
synthesis endpoints; no extra dependencies required.

For MCP (streamable-HTTP transport, compatible with Claude Desktop and claude-code):

```dockerfile
RUN pip install --no-cache-dir "ovos-tts-server[mcp]"
```

Start the server with `--mcp` to activate the `/mcp` endpoint.  Mount it in
Claude Desktop with:

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

This feature is already available in the `dev` branch.
