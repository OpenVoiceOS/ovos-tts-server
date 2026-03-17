# SUGGESTIONS.md — ovos-tts-server

## S-001: Add unit tests

Priority: High. No tests exist. Minimum coverage should include:
- `TTSEngineWrapper` construction with a mocked plugin
- `create_app()` endpoint responses using FastAPI `TestClient`
- Error handling: missing `utterance` parameter in `/v2/synthesize`

## S-002: Wire `--lang` CLI arg

The `--lang` argument is accepted but silently ignored — `ovos_tts_server/__main__.py:31`. It should override the plugin's default language by passing it into `TTSEngineWrapper.__init__` and storing it as the `self.lang` default.

## S-003: Implement `available_voices` support

`/voices` returns a hardcoded single entry. Define an `available_voices` protocol for TTS plugins and update the endpoint once plugins expose it — `ovos_tts_server/__init__.py:132`.

## S-004: Remove `setup.py`

`pyproject.toml` is the canonical packaging file. `setup.py` is redundant and should be removed to avoid dual-maintenance confusion.

## S-005: Pin `pypa/gh-action-pypi-publish` to `@release/v1`

Current `@master` pin is unsafe. Update in `publish_stable.yml`.

## S-006: Add Python 3.10 and 3.12 to CI matrix

Currently only one Python version is tested. Add a `python-support.yml` workflow using the gh-automations reusable workflow.
