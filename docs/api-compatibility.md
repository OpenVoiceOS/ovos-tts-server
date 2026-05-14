# Third-Party API Compatibility

`ovos-tts-server` can expose its underlying OVOS TTS plugin behind drop-in compatibility endpoints for popular cloud TTS APIs. This lets existing apps that already speak a vendor's HTTP API use OVOS as a drop-in replacement — no client code changes required.

Each vendor's endpoints live under a dedicated URL prefix so multiple compat layers can coexist in one FastAPI app with no path collisions. Concrete vendor sections (request schema, query params, response shape, curl examples) are added by each compat-router PR as it lands.

All routers accept any auth token / API key supplied by the client and silently ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion across `wav`, `mp3`, `ogg`, `flac`, `pcm`, etc. is provided by `ovos_tts_server.audio_utils.convert_audio()`. Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable non-WAV outputs via `pydub`.
