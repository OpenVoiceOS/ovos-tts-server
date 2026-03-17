# AUDIT.md — ovos-tts-server

## Documentation Status
- [x] docs/index.md
- [x] QUICK_FACTS.md
- [x] FAQ.md
- [x] MAINTENANCE_REPORT.md
- [x] AUDIT.md
- [x] SUGGESTIONS.md

## Known Issues & Technical Debt

### CRITICAL
_(none)_

### MAJOR
- `[MAJOR]` **tests**: No unit tests found. `TTSEngineWrapper`, `create_app()`, and all endpoints lack test coverage. — `ovos_tts_server/__init__.py:21`

### MINOR
- `[MINOR]` **voices endpoint**: `/voices` always returns a single hardcoded `default` entry because OVOS TTS plugins do not expose a standard `available_voices` property — `ovos_tts_server/__init__.py:132`.
- `[MINOR]` **ci**: `pypa/gh-action-pypi-publish` pinned to `@master` in `publish_stable.yml` (should be `@release/v1`).
- `[MINOR]` **ci**: Python matrix missing: 3.10, 3.12.
- `[MINOR]` **return type mismatch**: `synth_v2` docstring says it returns `dict` on error, but actually returns `Response` — `ovos_tts_server/__init__.py:174`.
- `[MINOR]` **setup.py**: `setup.py` is still present alongside `pyproject.toml`; should be removed.

### INFO
- `[INFO]` **lang CLI arg**: `--lang` is accepted by `__main__.py` but never passed into `TTSEngineWrapper`; it has no effect — `ovos_tts_server/__main__.py:31`.
