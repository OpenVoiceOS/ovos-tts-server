# Voice & Language Configuration

This page explains how a TTS request becomes a call to your plugin, and how
voices and languages are resolved.

## Plugin configuration

The plugin is configured exactly as it would be inside an assistant — via
`mycroft.conf`. The server reads the `tts` section at startup:

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

`TTSEngineWrapper` loads the plugin named by `module` (or the `--engine` flag)
and passes its config block to the plugin. The `--cache` flag sets
`persist_cache` so generated audio is kept on disk across requests.

## How voice and language flow to the plugin

Each compat router translates its vendor-specific parameters into `voice=` and
`lang=` keyword arguments, which are forwarded to the plugin:

```
vendor request → router → engine.synthesize(text, voice=..., lang=...) → plugin
```

For example: Coqui's `speaker_id`/`language_id`, Google's `voice.name`/
`voice.languageCode`, Polly's `VoiceId`/`LanguageCode`, and Azure's SSML
`<voice name=…>` / `xml:lang=…` all collapse to the same two kwargs. Parameters a
plugin can't act on (speed, pitch, model id, …) are accepted for
wire-compatibility and ignored. Per-vendor mappings are tabulated in
[api-compatibility.md](api-compatibility.md).

On the native endpoints (`/synthesize/{utterance}`, `/v2/synthesize`), **any**
extra query parameter is forwarded verbatim to the plugin, so plugin-specific
options work without a dedicated mapping.

## `TTSEngineWrapper.synthesize`

```python
TTSEngineWrapper.synthesize(utterance: str, **kwargs) -> Tuple[str, Optional[str]]
```

Validates SSML, calls the plugin, and returns `(wav_path, phonemes_or_None)`.
`kwargs` (typically `voice=` and `lang=`) are forwarded to the plugin. The WAV
file is then passed to [`convert_audio()`](audio-formats.md) when a non-WAV
output format is requested.

Defined in `ovos_tts_server/__init__.py`.

## Languages

`engine.langs` returns the plugin's `available_languages`, or a single-element
list with the wrapper's default language (from config, global `lang`, or `mul`)
when the plugin doesn't report any. It is surfaced by `GET /status`
(`langs` / `default_lang`) and by the ElevenLabs `/v1/models` listing.

## Voices

`engine.voices` is populated from the loaded plugin's `available_voices`
attribute, if present (a list of strings or dicts); otherwise it is empty.
Routers that expose a voices listing (e.g. ElevenLabs `/v1/voices`) read this
list directly and fall back to a single `"default"` entry when the plugin
reports none.
