# Audio Format Conversion

TTS plugins produce WAV. When a client asks for another container (mp3, ogg, and others), the compat routers convert it with a single helper.

## `convert_audio(wav_path, fmt)`: `ovos_tts_server/audio_utils.py`

```python
def convert_audio(wav_path: str, fmt: str) -> Tuple[bytes, str]:
    ...
```

**Returns:** `(audio_bytes, mime_type)`.

### Format handling

| `fmt` value | Behavior | MIME type |
| :--- | :--- | :--- |
| `"wav"` or `"pcm"` | WAV bytes returned directly (no conversion) | `audio/wav` |
| `"mp3"` | pydub export as MP3 | `audio/mpeg` |
| `"ogg"` | pydub export as OGG | `audio/ogg` |
| `"flac"` | pydub export as FLAC | `audio/flac` |
| `"aac"` | pydub export as AAC | `audio/aac` |
| any other | pydub export, MIME `audio/<fmt>` | `audio/<fmt>` |

The function lower-cases the `fmt` argument before matching.

### `pydub` is optional

`pydub` lives in the `[audio]` extra (`[project.optional-dependencies] audio = ["pydub"]`). Install it to enable non-WAV output:

```bash
pip install "ovos-tts-server[audio]"
```

When `pydub` is absent, any non-WAV request degrades gracefully. The server returns the original WAV bytes with MIME type `audio/wav`. The request still succeeds; the client simply receives WAV instead of the requested container.

### Vendor format strings

Each compat router normalizes its vendor's format identifier to one of the `fmt` values above before calling `convert_audio()`, for example ElevenLabs' `mp3_44100_128` to `mp3`, Google's `LINEAR16` to `wav`, Polly's `ogg_vorbis` to `ogg`. [api-compatibility.md](api-compatibility.md) documents those mappings per vendor.

---
[← Transformers](transformers.md) · [Home](index.md)
