# Voice & Language Configuration

This page explains how a TTS request becomes a call to your plugin, and how the server resolves voices and languages.

## Plugin configuration

The plugin is configured exactly as it would be inside an assistant, through `mycroft.conf`. The server reads the `tts` section at startup:

```json
{
  "tts": {
    "module": "ovos-tts-plugin-piper",
    "ovos-tts-plugin-piper": {
      "model": "alan-low",
      "lang": "en-us"
    }
  }
}
```

`TTSEngineWrapper` loads the plugin named by `module` (or the `--engine` flag) and passes its config block to the plugin. The `--cache` flag sets `persist_cache` so the server keeps generated audio on disk across requests.

## How voice and language flow to the plugin

Each compat router translates its vendor-specific parameters into `voice=` and `lang=` keyword arguments, which it forwards to the plugin:

```
vendor request → router → engine.synthesize(text, voice=..., lang=...) → plugin
```

For example, Coqui's `speaker_id`/`language_id`, Google's `voice.name`/`voice.languageCode`, Polly's `VoiceId`/`LanguageCode`, and Azure's SSML `<voice name=...>` / `xml:lang=...` all collapse to the same two kwargs. The server accepts parameters a plugin can't act on (speed, pitch, model id, and others) for wire-compatibility and ignores them. [api-compatibility.md](api-compatibility.md) tabulates the per-vendor mappings.

On the native endpoints (`/synthesize/{utterance}`, `/v2/synthesize`), the server forwards any extra query parameter verbatim to the plugin, so plugin-specific options work without a dedicated mapping.

## `TTSEngineWrapper.synthesize`

```python
TTSEngineWrapper.synthesize(utterance: str, **kwargs) -> Tuple[str, Optional[str]]
```

Validates SSML, calls the plugin, and returns `(wav_path, phonemes_or_None)`. It forwards `kwargs` (typically `voice=` and `lang=`) to the plugin. The WAV file then passes to [`convert_audio()`](audio-formats.md) when a request asks for a non-WAV output format.

Defined in `ovos_tts_server/__init__.py`.

## Languages

`engine.langs` returns the plugin's `available_languages`, or a single-element list with the wrapper's default language (from config, global `lang`, or `mul`) when the plugin reports none. `GET /status` (`langs` / `default_lang`) and the ElevenLabs `/v1/models` listing surface this value.

## Voices

`engine.voices` is populated from the loaded plugin's `available_voices` attribute, if present (a list of strings or dicts). Otherwise it is empty. Routers that expose a voices listing (for example ElevenLabs `/v1/voices`) read this list directly and fall back to a single `"default"` entry when the plugin reports none.

---
[Home](index.md) · [API Compatibility →](api-compatibility.md)
