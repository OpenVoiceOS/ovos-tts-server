# FAQ — ovos-tts-server

## How do I start the server?

```bash
ovos-tts-server --engine ovos-tts-plugin-mimic3 --port 9666
```

The `--engine` argument must match the plugin entry point name registered under `opm.plugin.tts`.

## How is the TTS plugin configured?

Plugin configuration is read from the OVOS config file under `tts.<plugin_name>`. For example, `Configuration().get("tts", {}).get("ovos-tts-plugin-mimic3", {})`. See `TTSEngineWrapper.__init__` — `ovos_tts_server/__init__.py:24`.

## What does `--cache` do?

Passes `persist_cache=True` to the plugin, keeping generated audio files between server restarts. Without it, temporary files may be deleted on exit. Controlled by `TTSEngineWrapper.__init__` — `ovos_tts_server/__init__.py:34`.

## Is CORS enabled?

Yes, unconditionally. `CORSMiddleware(allow_origins=["*"])` is added in `create_app()` — `ovos_tts_server/__init__.py:87`. No environment variable is needed.

## How do I select a voice or language per request?

Pass `lang` and/or `voice` as query parameters to `/v2/synthesize`:

```
GET /v2/synthesize?utterance=Hello+world&lang=en-us&voice=mycroft
```

All extra query parameters beyond `utterance` are forwarded to the plugin via `TTSEngineWrapper.synthesize` — `ovos_tts_server/__init__.py:60`.

## How does MaryTTS compatibility work?

Three endpoints mimic the MaryTTS HTTP API so that existing MaryTTS clients work without modification:
- `GET /locales` — newline-separated locale list
- `GET /voices` — newline-separated voice list (`name locale gender plugin`)
- `GET|POST /process` — accepts `INPUT_TEXT`, `LOCALE`, `VOICE`, returns WAV

See `MaryTTSInput` — `ovos_tts_server/__init__.py:8`.

## What audio format is returned?

WAV (`audio/wav`) for all synthesis endpoints. The underlying plugin determines sample rate and encoding.

## Which OVOS TTS plugins are supported?

Any plugin discoverable by `ovos-plugin-manager` via the `opm.plugin.tts` entry point group. Pass the plugin's entry point name to `--engine`.

## Why does `/voices` only return one entry?

OVOS TTS plugins do not yet expose a standard `available_voices` property. The endpoint returns a single `default` entry as a placeholder. See comment in `ovos_tts_server/__init__.py:132`.
