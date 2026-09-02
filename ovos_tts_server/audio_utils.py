# Licensed under the Apache License, Version 2.0
import os
import subprocess
import tempfile
import wave
from typing import Tuple


def _is_wav(path: str) -> bool:
    """Return True if the file can be opened as a RIFF WAV."""
    try:
        with wave.open(os.fspath(path), "rb"):
            return True
    except (wave.Error, EOFError, OSError):
        return False


def _ensure_wav(path: str) -> Tuple[str, bool]:
    """Return a path to a WAV file, transcoding non-WAV plugin output if needed.

    TTS plugins may declare a non-WAV ``audio_ext`` (e.g. an mp3-only engine),
    in which case synthesis yields audio the WAV/pydub decode path cannot read.
    This transcodes such output to a temporary WAV so downstream conversion works.

    Args:
        path: Path to the synthesized audio file.

    Returns:
        Tuple of (wav_path, is_temp). ``is_temp`` is True when ``wav_path`` is a
        freshly created temporary file the caller is responsible for removing.
    """
    if _is_wav(path):
        return path, False

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        try:
            from pydub import AudioSegment
            AudioSegment.from_file(path).export(tmp.name, format="wav")
        except ImportError:
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", path, tmp.name],
                check=True,
            )
    except Exception:
        os.remove(tmp.name)
        raise
    return tmp.name, True


def convert_audio(wav_path: str, fmt: str) -> Tuple[bytes, str]:
    """Convert a synthesized audio file to the requested format.

    Args:
        wav_path: Path to the synthesized audio file. Non-WAV plugin output is
            transcoded to WAV before decoding.
        fmt: Target audio format (e.g. "mp3", "wav", "pcm", "ogg").

    Returns:
        Tuple of (audio_bytes, mime_type). Falls back to WAV on ImportError.
    """
    fmt = fmt.lower()
    src_path, is_temp = _ensure_wav(wav_path)
    try:
        with open(src_path, "rb") as f:
            wav_bytes = f.read()

        if fmt in ("wav", "pcm"):
            return wav_bytes, "audio/wav"

        try:
            from pydub import AudioSegment
            import io
            audio = AudioSegment.from_wav(src_path)
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
    finally:
        if is_temp:
            os.remove(src_path)
