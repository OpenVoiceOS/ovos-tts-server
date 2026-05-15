# `ovos-tts-server` Documentation Hub

`ovos-tts-server` exposes any OVOS TTS plugin as a network service. On its
own it speaks one native protocol — but with compat routers enabled it
also pretends to be every major cloud TTS API and every popular
self-hosted server, so **unmodified consumer apps transparently land on
this box** instead of a third-party cloud.

| Goal | Read |
| :--- | :--- |
| Make unmodified consumer apps stop calling cloud TTS services | [voice-pihole.md](voice-pihole.md) |
| Drive this server with the official Python/Node SDK of a specific vendor | [api-compatibility.md](api-compatibility.md) |
| Replace an existing self-hosted TTS server on the wire | [api-compatibility.md](api-compatibility.md) |
| Bridge Home Assistant Voice / Voice PE | [wyoming-integration.md](wyoming-integration.md) |
| Audio format negotiation | [audio-formats.md](audio-formats.md) |
| Voice + language plumbing | [configuration.md](configuration.md) |
| Native `/v2/synthesize` endpoint | [index.md](index.md) |

## Compat coverage matrix

- ✅ **merged** — landed on `dev`
- 🟡 **open** — PR up
- ⚪ **planned**

### Commercial cloud TTS

| Vendor | Prefix | Status | PR |
| :--- | :--- | :--- | :--- |
| ElevenLabs | `/elevenlabs` | 🟡 open | [#87](https://github.com/OpenVoiceOS/ovos-tts-server/pull/87) |
| OpenAI TTS | `/openai` | 🟡 open | [#88](https://github.com/OpenVoiceOS/ovos-tts-server/pull/88) |
| Google Cloud TTS | `/google-tts` | 🟡 open | [#90](https://github.com/OpenVoiceOS/ovos-tts-server/pull/90) |
| Amazon Polly | `/amazon-polly` | 🟡 open | [#91](https://github.com/OpenVoiceOS/ovos-tts-server/pull/91) |
| Microsoft Azure Speech | `/azure-tts` (REST + WS) | 🟡 open | [#92](https://github.com/OpenVoiceOS/ovos-tts-server/pull/92) |

### Self-hosted / open-source TTS server protocols

| Server | Prefix | Status | PR |
| :--- | :--- | :--- | :--- |
| Coqui TTS server | `/coqui` | 🟡 open | [#89](https://github.com/OpenVoiceOS/ovos-tts-server/pull/89) |
| Piper HTTP server | `/piper` | 🟡 open | [#93](https://github.com/OpenVoiceOS/ovos-tts-server/pull/93) |
| MaryTTS | `/marytts` + root aliases | 🟡 open | [#94](https://github.com/OpenVoiceOS/ovos-tts-server/pull/94) |

## Voice-pihole

[voice-pihole.md](voice-pihole.md) collects every DNS-rewrite + reverse-proxy
+ CA-trust recipe across all the above vendors.

---

## TODO

### Streaming partial audio

The OpenAI / ElevenLabs / Azure SDKs all support streaming synthesis
(audio chunks delivered as the model generates them). Our compat routers
emit the entire WAV body in one response after the OVOS plugin finishes
— which is what OVOS TTS plugins natively produce. True chunked
streaming needs either a streaming-aware plugin contract (OPM change) or
server-side chunking of the produced WAV.

### Vendor coverage gaps

- Cartesia / PlayHT / Resemble / Murf — emerging neural-TTS APIs.
- Microsoft Speech SDK WS — the `output_format` enum doesn't cover every
  Microsoft profile.
- Mimic 3 / Mycroft Mimic server.
- Festival / espeak-ng HTTP wrappers.

### Docs

- One-pager per deployment (Raspberry Pi, Tailscale, Caddy alternative).
- mkcert / step-ca walkthrough.
- Per-vendor migration guide (SDK → drop-in).
- Native `/v2/synthesize` deep-dive.
