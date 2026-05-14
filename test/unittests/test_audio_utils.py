# Licensed under the Apache License, Version 2.0
"""Unit tests for ovos_tts_server.audio_utils.convert_audio."""
import builtins
import io
import sys
import tempfile
import wave

import pytest

from ovos_tts_server.audio_utils import convert_audio


def _write_silent_wav() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 1600)
    return tmp.name


@pytest.fixture
def wav_path() -> str:
    return _write_silent_wav()


class TestConvertAudio:
    def test_wav_passthrough(self, wav_path):
        data, mime = convert_audio(wav_path, "wav")
        assert mime == "audio/wav"
        assert data.startswith(b"RIFF")

    def test_pcm_passthrough(self, wav_path):
        data, mime = convert_audio(wav_path, "pcm")
        assert mime == "audio/wav"
        assert data.startswith(b"RIFF")

    def test_fmt_is_case_insensitive(self, wav_path):
        data, mime = convert_audio(wav_path, "WAV")
        assert mime == "audio/wav"
        assert data.startswith(b"RIFF")

    def test_falls_back_to_wav_when_pydub_missing(self, wav_path, monkeypatch):
        """When pydub is absent, non-WAV formats return WAV bytes."""
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pydub" or name.startswith("pydub."):
                raise ImportError("pydub not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        # ensure stale module is not cached
        monkeypatch.delitem(sys.modules, "pydub", raising=False)

        data, mime = convert_audio(wav_path, "mp3")
        assert mime == "audio/wav"
        assert data.startswith(b"RIFF")

    def test_uses_pydub_when_available(self, wav_path, monkeypatch):
        """When pydub-like API is available, returns converted bytes + MIME."""
        # Build a fake pydub module
        fake_pydub = type(sys)("pydub")
        captured = {}

        class FakeAudio:
            @classmethod
            def from_wav(cls, path):
                captured["path"] = path
                return cls()

            def export(self, buf, format):
                captured["format"] = format
                buf.write(b"FAKEDATA")

        fake_pydub.AudioSegment = FakeAudio
        monkeypatch.setitem(sys.modules, "pydub", fake_pydub)

        for fmt, expected_mime in [
            ("mp3", "audio/mpeg"),
            ("ogg", "audio/ogg"),
            ("flac", "audio/flac"),
            ("aac", "audio/aac"),
            ("opus", "audio/opus"),  # dynamic fallback
        ]:
            data, mime = convert_audio(wav_path, fmt)
            assert mime == expected_mime
            assert data == b"FAKEDATA"
            assert captured["path"] == wav_path
            assert captured["format"] == ("mp3" if fmt == "mp3" else fmt)
