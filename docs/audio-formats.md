# Audio Format Conversion

## `convert_audio(wav_path, fmt)` — `audio_utils.py`

Converts a WAV file produced by the TTS plugin to the requested output format.

```python
def convert_audio(wav_path: str, fmt: str) -> Tuple[bytes, str]:
    ...
```

**Returns:** `(audio_bytes, mime_type)`

### Format handling

| `fmt` value | Behaviour | MIME type |
| :--- | :--- | :--- |
| `"wav"` or `"pcm"` | WAV bytes returned directly | `audio/wav` |
| `"mp3"` | pydub export as MP3 | `audio/mpeg` |
| `"ogg"` | pydub export as OGG | `audio/ogg` |
| `"flac"` | pydub export as FLAC | `audio/flac` |
| `"aac"` | pydub export as AAC | `audio/aac` |
| any other | pydub export, MIME `audio/<fmt>` | dynamic |

### pydub optional dependency

pydub is an optional dependency (`pyproject.toml` `[project.optional-dependencies] audio = ["pydub"]`).

When pydub is **absent**, any non-WAV format falls back to WAV bytes:
- The returned MIME type is still `audio/wav`.
- Routers that consume this helper may add an `X-Audio-Format: wav` response header to signal the fallback.

Vendor-specific format-string normalisation (e.g. compound output_format strings) is documented alongside the router that uses it.
