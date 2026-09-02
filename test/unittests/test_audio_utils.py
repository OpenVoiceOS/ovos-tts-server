# Licensed under the Apache License, Version 2.0
"""Unit tests for ovos_tts_server.audio_utils.convert_audio."""
import builtins
import io
import os
import sys
import tempfile
import wave
from pathlib import Path

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

    def test_accepts_pathlib_path(self, wav_path):
        """The OpenAI speech route hands convert_audio a pathlib.Path; it must not 500."""
        data, mime = convert_audio(Path(wav_path), "wav")
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


def _write_non_riff(suffix: str = ".mp3") -> str:
    """Write a small file whose header is not a RIFF WAV."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(b"ID3\x03\x00\x00\x00\x00\x00\x00not-a-wav-payload")
    tmp.close()
    return tmp.name


class TestEnsureWav:
    def test_wav_returns_same_path_untouched(self, wav_path):
        """A real WAV is passed through without transcoding or temp files."""
        from ovos_tts_server.audio_utils import _ensure_wav

        out_path, is_temp = _ensure_wav(wav_path)
        assert out_path == wav_path
        assert is_temp is False

    def test_non_wav_is_transcoded_to_temp_wav(self, monkeypatch):
        """Non-WAV plugin output is transcoded to a fresh temp WAV via pydub."""
        from ovos_tts_server import audio_utils

        src = _write_non_riff()
        captured = {}

        class FakeAudio:
            @classmethod
            def from_file(cls, path):
                captured["path"] = path
                return cls()

            def export(self, out, format):
                captured["format"] = format
                with wave.open(out, "w") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(b"\x00\x00" * 10)

        fake_pydub = type(sys)("pydub")
        fake_pydub.AudioSegment = FakeAudio
        monkeypatch.setitem(sys.modules, "pydub", fake_pydub)

        out_path, is_temp = audio_utils._ensure_wav(src)
        try:
            assert is_temp is True
            assert out_path != src
            assert captured["path"] == src
            assert captured["format"] == "wav"
            with open(out_path, "rb") as f:
                assert f.read().startswith(b"RIFF")
        finally:
            os.remove(out_path)
            os.remove(src)

    def test_convert_audio_handles_non_wav_source(self, monkeypatch):
        """convert_audio no longer raises on mp3-emitting plugin output."""
        from ovos_tts_server import audio_utils

        src = _write_non_riff()

        class FakeAudio:
            @classmethod
            def from_file(cls, path):
                return cls()

            @classmethod
            def from_wav(cls, path):
                return cls()

            def export(self, out, format):
                if format == "wav":
                    with wave.open(out, "w") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(b"\x00\x00" * 10)
                else:
                    out.write(b"MP3DATA")

        fake_pydub = type(sys)("pydub")
        fake_pydub.AudioSegment = FakeAudio
        monkeypatch.setitem(sys.modules, "pydub", fake_pydub)

        try:
            data, mime = audio_utils.convert_audio(src, "mp3")
            assert mime == "audio/mpeg"
            assert data == b"MP3DATA"
        finally:
            os.remove(src)
