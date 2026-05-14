# Audio Format Conversion

## `convert_audio(wav_path, fmt)` — `audio_utils.py:6`

Converts a WAV file produced by the TTS plugin to the requested output format.

```python
def convert_audio(wav_path: str, fmt: str) -> Tuple[bytes, str]:
    ...
```

**Returns:** `(audio_bytes, mime_type)`

### Format handling

| `fmt` value | Behaviour | MIME type |
| :--- | :--- | :--- |
| `"wav"` or `"pcm"` | WAV bytes returned directly — `audio_utils.py:20-21` | `audio/wav` |
| `"mp3"` | pydub export as MP3 — `audio_utils.py:28` | `audio/mpeg` |
| `"ogg"` | pydub export as OGG | `audio/ogg` |
| `"flac"` | pydub export as FLAC | `audio/flac` |
| `"aac"` | pydub export as AAC | `audio/aac` |
| any other | pydub export, MIME `audio/<fmt>` | dynamic |

### pydub optional dependency

pydub is an optional dependency (`pyproject.toml` `[project.optional-dependencies] audio = ["pydub"]`).

When pydub is **absent**, any non-WAV format falls back to WAV bytes (`audio_utils.py:38-39`):
- The returned MIME type is still `audio/wav`.
- Some compat routers add an `X-Audio-Format: wav` response header to signal the fallback.

### ElevenLabs `output_format` mapping — `routers/elevenlabs.py:119-125`

ElevenLabs uses compound format strings; they are normalised before calling `convert_audio`:

| `output_format` | `fmt` passed to `convert_audio` |
| :--- | :--- |
| `mp3_44100_128` | `mp3` |
| `pcm_16000` | `pcm` |
| `ulaw_8000` | `wav` |
| anything else with `_` | first segment before `_` |
