# MAINTENANCE_REPORT — ovos-tts-server

## 2026-03-17 — Refactoring: CORS, workflow updates, docs

- **AI Model**: claude-sonnet-4-6
- **Oversight**: Human-reviewed task specification; agent executed changes locally, no push.

### Actions Taken

1. **Added `CORSMiddleware`** unconditionally in `create_app()` — `ovos_tts_server/__init__.py:87`.
   `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.

2. **Removed dead CLI args** from `ovos_tts_server/__main__.py`: `--title`, `--description`, `--info`, `--badge`.
   These referenced a removed Gradio/web-UI feature and had no effect.

3. **Updated gh-automations org reference**: All three existing workflows changed from
   `TigreGotico/gh-automations/...@master` → `OpenVoiceOS/gh-automations/...@dev`.

4. **Added four new GitHub Actions workflows**:
   - `.github/workflows/lint.yml` — PEP 8 / flake8
   - `.github/workflows/build_tests.yml` — build/install smoke test
   - `.github/workflows/license_tests.yml` — Apache 2.0 header check
   - `.github/workflows/pip_audit.yml` — dependency vulnerability scan

5. **Created documentation**:
   - `docs/index.md` — overview, endpoints, key classes
   - `QUICK_FACTS.md` — package reference
   - `FAQ.md` — 9 Q&As covering CORS, plugin config, voice selection, MaryTTS compat
   - `MAINTENANCE_REPORT.md` (this file)
   - Updated `AUDIT.md` — marked resolved items, added new known issues
   - `SUGGESTIONS.md` — agent proposals
