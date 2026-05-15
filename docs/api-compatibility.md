# Third-Party API Compatibility

`ovos-tts-server` exposes its underlying OVOS TTS plugin behind drop-in
compatibility endpoints for popular cloud TTS APIs. Each vendor lives
under its own URL prefix so multiple compat layers coexist with no path
collisions.

All routers accept any auth token / API key supplied by the client and
silently ignore it — authentication is the responsibility of your
reverse proxy.

Audio format conversion across `wav`, `mp3`, `ogg`, `flac`, `pcm`, etc.
is provided by `ovos_tts_server.audio_utils.convert_audio()`. Install
the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable
non-WAV outputs via `pydub`.

The shared network-redirect concept lives in
[`voice-pihole.md`](voice-pihole.md); per-vendor sections cross-reference
it.

Status reflects merge state into `dev`:

- ✅ **merged** — full per-vendor docs section below the index.
- 🟡 **open** — PR is up; full docs on the feature branch.

## Commercial cloud TTS

| Vendor | Prefix | Status | PR |
| :--- | :--- | :--- | :--- |
| ElevenLabs | `/elevenlabs` | 🟡 open | [#87](https://github.com/OpenVoiceOS/ovos-tts-server/pull/87) |
| OpenAI TTS | `/openai` | 🟡 open | [#88](https://github.com/OpenVoiceOS/ovos-tts-server/pull/88) |
| Google Cloud TTS | `/google-tts` | 🟡 open | [#90](https://github.com/OpenVoiceOS/ovos-tts-server/pull/90) |
| Amazon Polly | `/amazon-polly` | 🟡 open | [#91](https://github.com/OpenVoiceOS/ovos-tts-server/pull/91) |
| Microsoft Azure TTS | `/azure-tts` (REST + WS) | 🟡 open | [#92](https://github.com/OpenVoiceOS/ovos-tts-server/pull/92) |

## Self-hosted / OSS server protocols

| Server | Prefix | Status | PR |
| :--- | :--- | :--- | :--- |
| Coqui TTS server | `/coqui` | 🟡 open | [#89](https://github.com/OpenVoiceOS/ovos-tts-server/pull/89) |
| Piper HTTP server | `/piper` | 🟡 open | [#93](https://github.com/OpenVoiceOS/ovos-tts-server/pull/93) |
| MaryTTS | `/marytts` + root aliases | 🟡 open | [#94](https://github.com/OpenVoiceOS/ovos-tts-server/pull/94) |
