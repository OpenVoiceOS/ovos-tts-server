# Third-Party API Compatibility

`ovos-tts-server` can expose its underlying OVOS TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs. This lets existing apps that already speak a vendor's HTTP API use OVOS as a drop-in replacement — no client code changes required.

Each vendor's endpoints live under a dedicated URL prefix so multiple compat layers can coexist in one FastAPI app with no path collisions. Concrete vendor sections (request schema, query params, response shape, curl examples) are added by each compat-router PR as it lands.

All routers accept any auth token / API key supplied by the client and silently ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion across `wav`, `mp3`, `ogg`, `flac`, `pcm`, etc. is provided by `ovos_tts_server.audio_utils.convert_audio()`. Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable non-WAV outputs via `pydub`.

This document currently covers: **MaryTTS** (mounted under `/marytts`).

---

## MaryTTS (`/marytts`)

The MaryTTS compat router exposes the classic MaryTTS HTTP endpoints so apps that already speak MaryTTS can swap in OVOS without code changes.

**Upstream sources** (no canonical Python SDK — most clients hand-roll HTTP):
- Reference server: [marytts/marytts — `MaryHttpServer.java`](https://github.com/marytts/marytts/blob/master/marytts-runtime/src/main/java/marytts/server/http/MaryHttpServer.java)
- Request handler defining `/process`, `/voices`, `/locales`: [`InfoRequestHandler.java`](https://github.com/marytts/marytts/blob/master/marytts-runtime/src/main/java/marytts/server/http/InfoRequestHandler.java)
- Home Assistant client: [`homeassistant/components/marytts/tts.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/marytts/tts.py)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/marytts/locales` | Newline-separated supported locales |
| GET | `/marytts/voices` | Newline-separated voices, format `name locale gender plugin` |
| GET/POST | `/marytts/process` | Synthesize — returns `audio/wav` |

### Root-path aliases

Because MaryTTS predates modern API gateways and is heavily used in
**accessibility / assistive tech** (screen-reader bridges, NVDA/Orca TTS
adaptors, Home Assistant's `marytts` integration), the same three endpoints
are **also exposed at the server root** so legacy clients that hardcode
bare paths work out of the box:

| Method | Path | Same as |
| :--- | :--- | :--- |
| GET | `/locales` | `/marytts/locales` |
| GET | `/voices` | `/marytts/voices` |
| GET/POST | `/process` | `/marytts/process` |

Prefer the `/marytts/...` paths in new code — the bare aliases exist
purely for drop-in compatibility with software that can't be reconfigured.

### `/marytts/process` parameters

| Name | Type | Notes |
| :--- | :--- | :--- |
| `INPUT_TEXT` | str (required) | Text or SSML to synthesize |
| `INPUT_TYPE` | `TEXT` \| `SSML` | Default `TEXT` |
| `LOCALE` | str | Mapped to `lang=` plugin kwarg |
| `VOICE` | str | Underscores converted to spaces, mapped to `voice=` |
| `OUTPUT_TYPE` | str | Accepted, ignored (always `AUDIO`) |
| `AUDIO` | str | Accepted, ignored (always `WAVE_FILE`) |

### Example

```bash
# List locales
curl http://localhost:9666/marytts/locales

# List voices
curl http://localhost:9666/marytts/voices

# Synthesize
curl -G http://localhost:9666/marytts/process \
  --data-urlencode "INPUT_TEXT=hello world" \
  --data-urlencode "LOCALE=en_US" \
  -o out.wav
```

### Pointing apps at this server

MaryTTS clients are configured with a base URL. Set it to where this server runs (path prefix `/marytts`).

**Mycroft / OVOS** (`mycroft.conf` — any TTS plugin that speaks MaryTTS HTTP and accepts a `url` setting):
```json
{
  "tts": {
    "module": "<your-marytts-plugin>",
    "<your-marytts-plugin>": { "url": "http://localhost:9666/marytts" }
  }
}
```

**Home Assistant** (`configuration.yaml`, `marytts` integration). HA's built-in
integration hardcodes bare paths (`/process`, `/voices`, `/locales`) — point
it directly at the server, no path-stripping proxy needed because the
root-alias router handles those:
```yaml
tts:
  - platform: marytts
    host: localhost
    port: 9666
```

**curl**:
```bash
curl -G http://localhost:9666/marytts/process \
  --data-urlencode "INPUT_TEXT=hello" -o out.wav
```
