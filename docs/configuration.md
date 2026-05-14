# Voice & Language Configuration

## How voice and language flow to the plugin

Each compat router translates vendor-specific parameters into `voice=` and `lang=` kwargs passed to `engine.synthesize(utterance, **kwargs)`. The exact mapping is documented alongside each router's PR.

## TTSEngineWrapper.synthesize

`TTSEngineWrapper.synthesize(utterance, voice=None, lang=None, **kwargs) → Tuple[str, Optional[str]]`

Returns `(wav_path, phonemes_or_None)`. The WAV file is then passed to `convert_audio()` if a non-WAV output format is requested.

Defined in `ovos_tts_server/__init__.py`.

## Voices list

`engine.voices` is populated from the loaded plugin (`available_voices` attribute, if present). Routers that expose a `/voices` endpoint read this list directly; routers may fall back to a single `"default"` voice entry if the plugin reports no voices.
