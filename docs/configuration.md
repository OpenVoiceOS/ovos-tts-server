# Voice & Language Configuration

## How voice and language flow to the plugin

Each compat router translates vendor-specific parameters into `voice=` and `lang=` kwargs
passed to `engine.synthesize(utterance, **kwargs)`.

| Router | Vendor param | Plugin kwarg |
| :--- | :--- | :--- |
| ElevenLabs | `{voice_id}` path param | `voice=voice_id` (skipped if `"default"`) — `routers/elevenlabs.py:128-130` |
| OpenAI TTS | `voice` body field | `voice=voice` — `routers/openai_tts.py` |
| Coqui | `speaker_id` query | `voice=speaker_id`; `language_id` query → `lang=language_id` — `routers/coqui.py` |
| Google TTS | `voice.name` body | `voice=name`; `voice.languageCode` → `lang=languageCode` — `routers/google_tts.py` |
| Amazon Polly | `VoiceId` body | `voice=VoiceId` — `routers/amazon_polly.py` |
| Azure TTS | SSML `name=` attr | `voice=name`; `xml:lang=` attr → `lang=lang` — `routers/azure_tts.py` |
| Piper | `voice` query | `voice=voice` — `routers/piper.py` |

## TTSEngineWrapper.synthesize

`TTSEngineWrapper.synthesize(utterance, voice=None, lang=None, **kwargs) → Tuple[str, Optional[str]]`

Returns `(wav_path, phonemes_or_None)`. The WAV file is then passed to `convert_audio()`.

Defined at `ovos_tts_server/__init__.py`.

## Voices list

`engine.voices` is populated from the loaded plugin. The ElevenLabs `/v1/voices` and
`/v1/models` endpoints read this list directly.

If `engine.voices` is empty, the ElevenLabs router falls back to a single `"default"` voice entry.
