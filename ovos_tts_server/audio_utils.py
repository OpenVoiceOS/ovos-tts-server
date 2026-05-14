# Licensed under the Apache License, Version 2.0
import os
from typing import Tuple


def convert_audio(wav_path: str, fmt: str) -> Tuple[bytes, str]:
    """Convert WAV file to requested format.

    Args:
        wav_path: Path to source WAV file.
        fmt: Target audio format (e.g. "mp3", "wav", "pcm", "ogg").

    Returns:
        Tuple of (audio_bytes, mime_type). Falls back to WAV on ImportError.
    """
    fmt = fmt.lower()
    with open(wav_path, "rb") as f:
        wav_bytes = f.read()

    if fmt in ("wav", "pcm"):
        return wav_bytes, "audio/wav"

    try:
        from pydub import AudioSegment
        import io
        audio = AudioSegment.from_wav(wav_path)
        buf = io.BytesIO()
        pydub_fmt = "mp3" if fmt == "mp3" else fmt
        audio.export(buf, format=pydub_fmt)
        mime_map = {
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
            "aac": "audio/aac",
        }
        mime = mime_map.get(fmt, f"audio/{fmt}")
        return buf.getvalue(), mime
    except ImportError:
        return wav_bytes, "audio/wav"
