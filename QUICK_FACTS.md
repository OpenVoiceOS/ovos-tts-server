# QUICK_FACTS — ovos-tts-server

| Field | Value |
| :--- | :--- |
| Package name | `ovos-tts-server` |
| Version | `1.0.0a1` (see `ovos_tts_server/version.py`) |
| Entry point script | `ovos-tts-server` → `ovos_tts_server.__main__:main` |
| Default port | `9666` |
| Key class | `TTSEngineWrapper` — `ovos_tts_server/__init__.py:21` |
| App factory | `create_app(tts_engine)` — `ovos_tts_server/__init__.py:76` |
| Framework | FastAPI + uvicorn |
| Plugin discovery | `ovos-plugin-manager` (`load_tts_plugin`) |
| CORS | Unconditional `allow_origins=["*"]` |
| MaryTTS compat | `/process`, `/locales`, `/voices` endpoints |
| License | Apache 2.0 |
