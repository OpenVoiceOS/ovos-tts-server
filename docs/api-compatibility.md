# API Compatibility Reference

All compat routers mount under a vendor-specific prefix to avoid path conflicts
and to make the Swagger UI self-documenting.

Authentication is mocked on every router: any API key, Bearer token, or query
parameter is accepted and silently ignored.

---

## ElevenLabs (`/elevenlabs`)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/elevenlabs/v1/voices` | List available voices |
| GET | `/elevenlabs/v1/models` | List available models |
| POST | `/elevenlabs/v1/text-to-speech/{voice_id}` | Synthesize speech |

**Auth:** `xi-api-key` header (ignored).

```bash
# List voices
curl -H "xi-api-key: fake" http://localhost:9666/elevenlabs/v1/voices

# Synthesize
curl -X POST \
  -H "xi-api-key: fake" \
  -H "Content-Type: application/json" \
  -d '{"text": "hello world"}' \
  "http://localhost:9666/elevenlabs/v1/text-to-speech/default?output_format=mp3_44100_128" \
  -o out.mp3
```

`output_format` values: `mp3_44100_128`, `pcm_16000`, `ulaw_8000`, etc. Falls back to WAV if pydub absent.

---

## OpenAI TTS (`/openai`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/openai/v1/audio/speech` | Synthesize speech |

**Auth:** `Authorization: Bearer <any>` (ignored).

```bash
curl -X POST \
  -H "Authorization: Bearer fake" \
  -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "hello world", "voice": "alloy", "response_format": "mp3"}' \
  http://localhost:9666/openai/v1/audio/speech \
  -o out.mp3
```

Valid `voice` values: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`.
Valid `model` values: `tts-1`, `tts-1-hd`.
`speed` range: 0.25–4.0.
`input` max length: 4096 characters.

---

## Coqui TTS (`/coqui`)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/coqui/api/tts` | Synthesize speech |

```bash
curl "http://localhost:9666/coqui/api/tts?text=hello+world&speaker_id=voice1&language_id=en-us" \
  -o out.wav
```

Query params: `text` (required), `speaker_id` → `voice=`, `language_id` → `lang=`.

---

## Google Cloud TTS (`/google-tts`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/google-tts/v1/text:synthesize` | Synthesize speech |

**Auth:** `Authorization: Bearer <any>` or `x-goog-api-key` header (ignored).

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"text": "hello world"},
    "voice": {"languageCode": "en-US", "name": "en-US-Standard-A"},
    "audioConfig": {"audioEncoding": "LINEAR16"}
  }' \
  http://localhost:9666/google-tts/v1/text:synthesize
```

Response: `{"audioContent": "<base64-encoded audio>"}`.
`audioEncoding` values: `LINEAR16`, `MP3`, `OGG_OPUS`, `MULAW`, `ALAW`.
Either `input.text` or `input.ssml` must be provided.

---

## Amazon Polly (`/amazon-polly`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/amazon-polly/v1/speech` | Synthesize speech |

**Auth:** `Authorization` header with AWS SigV4 (accepted, ignored).

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"Text": "hello world", "VoiceId": "Joanna", "OutputFormat": "mp3"}' \
  http://localhost:9666/amazon-polly/v1/speech \
  -o out.mp3
```

`OutputFormat` values: `mp3`, `ogg_vorbis`, `pcm`, `json` (json → WAV stub).

---

## Azure Cognitive Services TTS (`/azure-tts`)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/azure-tts/cognitiveservices/v1` | Synthesize from SSML |

**Auth:** `Ocp-Apim-Subscription-Key` header (accepted, ignored).

```bash
curl -X POST \
  -H "Ocp-Apim-Subscription-Key: fake" \
  -H "Content-Type: application/ssml+xml" \
  -H "X-Microsoft-OutputFormat: audio-24khz-48kbitrate-mono-mp3" \
  -d '<speak><voice name="en-US-JennyNeural" xml:lang="en-US">hello</voice></speak>' \
  http://localhost:9666/azure-tts/cognitiveservices/v1 \
  -o out.mp3
```

Body must be valid SSML XML. Voice name and `xml:lang` are extracted via regex and forwarded as `voice=` and `lang=`.

---

## Piper (`/piper`)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/piper/` | Synthesize speech |

```bash
curl "http://localhost:9666/piper/?text=hello+world&voice=voice1" -o out.wav
```

Query params: `text` (required), `voice` (optional).
