# Licensed under the Apache License, Version 2.0
"""Unit tests for the ElevenLabs stream-input WebSocket bridge."""
import base64
import pathlib
import struct
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ovos_tts_server.routers.elevenlabs import (
    DEFAULT_OUTPUT_FORMAT,
    _linear_to_ulaw,
    _parse_output_format,
    _resample_pcm,
    encode_audio,
    make_elevenlabs_router,
)

SRC_RATE = 16000
SRC_FRAMES = 1600


def _write_wav(path: str, rate: int = SRC_RATE, frames: int = SRC_FRAMES,
               channels: int = 1) -> None:
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<h", 1234) * frames * channels)


class FakeEngine:
    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def __init__(self):
        self.calls: List[Tuple[str, dict]] = []

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        self.calls.append((utterance, kwargs))
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        _write_wav(tmp.name)
        return tmp.name, None


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def client(engine):
    app = FastAPI()
    app.include_router(make_elevenlabs_router(engine))
    return TestClient(app)


@pytest.fixture
def wav_path(tmp_path):
    path = str(tmp_path / "src.wav")
    _write_wav(path)
    return path


def _path_synthesize(engine):
    """A synthesize() that returns a pathlib.Path, as real plugins do."""
    def synthesize(utterance: str, **kwargs) -> Tuple[pathlib.Path, Optional[str]]:
        engine.calls.append((utterance, kwargs))
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        _write_wav(tmp.name)
        return pathlib.Path(tmp.name), None
    return synthesize


def _drain(ws) -> Tuple[bytes, List[dict]]:
    """Collect audio until the isFinal frame, returning (audio, frames)."""
    audio = b""
    frames = []
    while True:
        frame = ws.receive_json()
        frames.append(frame)
        if frame["audio"]:
            audio += base64.b64decode(frame["audio"])
        if frame["isFinal"]:
            return audio, frames


# ---------------------------------------------------------------------------
# output_format parsing / encoding
# ---------------------------------------------------------------------------

class TestOutputFormat:
    @pytest.mark.parametrize("fmt,expected", [
        ("pcm_16000", ("pcm", 16000)),
        ("pcm_22050", ("pcm", 22050)),
        ("pcm_24000", ("pcm", 24000)),
        ("pcm_44100", ("pcm", 44100)),
        ("mp3_44100_128", ("mp3", 44100)),
        ("mp3_22050_32", ("mp3", 22050)),
        ("ulaw_8000", ("ulaw", 8000)),
    ])
    def test_parse_known_formats(self, fmt, expected):
        assert _parse_output_format(fmt) == expected

    def test_parse_unknown_format_falls_back_to_default(self):
        assert _parse_output_format("wobble_9") == ("mp3", 44100)

    def test_parse_empty_format_falls_back_to_default(self):
        assert _parse_output_format("") == ("mp3", 44100)

    def test_default_output_format_is_elevenlabs_default(self):
        assert DEFAULT_OUTPUT_FORMAT == "mp3_44100_128"

    def test_pcm_is_headerless(self, wav_path):
        audio, mime = encode_audio(wav_path, "pcm_16000")
        assert not audio.startswith(b"RIFF")
        assert mime == "audio/pcm"
        assert len(audio) == SRC_FRAMES * 2

    def test_pcm_upsampled_to_requested_rate(self, wav_path):
        audio, _ = encode_audio(wav_path, "pcm_24000")
        # 1600 frames at 16 kHz is 0.1s, which is 2400 frames at 24 kHz
        assert len(audio) // 2 == pytest.approx(2400, abs=2)

    def test_pcm_downsampled_to_requested_rate(self, wav_path):
        audio, _ = encode_audio(wav_path, "pcm_8000")
        assert len(audio) // 2 == pytest.approx(800, abs=2)

    def test_pcm_preserves_sample_values(self, wav_path):
        audio, _ = encode_audio(wav_path, "pcm_16000")
        assert struct.unpack("<h", audio[:2])[0] == 1234

    def test_stereo_source_downmixed_to_mono(self, tmp_path):
        path = str(tmp_path / "stereo.wav")
        _write_wav(path, channels=2)
        audio = _resample_pcm(path, SRC_RATE)
        assert len(audio) == SRC_FRAMES * 2
        assert struct.unpack("<h", audio[:2])[0] == 1234

    def test_ulaw_is_one_byte_per_sample(self, wav_path):
        audio, mime = encode_audio(wav_path, "ulaw_8000")
        assert mime == "audio/basic"
        assert len(audio) == pytest.approx(800, abs=2)

    def test_ulaw_encodes_silence_as_0xff(self):
        assert _linear_to_ulaw(struct.pack("<h", 0)) == b"\xff"

    @pytest.mark.parametrize("fmt", ["pcm_24000", "ulaw_8000", "mp3_44100_128"])
    def test_path_object_accepted(self, tmp_path, fmt):
        """Plugins hand back a pathlib.Path, which wave.open() cannot open itself."""
        path = tmp_path / "src.wav"
        _write_wav(str(path))
        audio, _ = encode_audio(path, fmt)
        assert audio

    def test_ulaw_sign_bit_distinguishes_polarity(self):
        positive = _linear_to_ulaw(struct.pack("<h", 8000))[0]
        negative = _linear_to_ulaw(struct.pack("<h", -8000))[0]
        # mu-law stores an inverted sign bit, so negatives clear bit 7
        assert positive & 0x80
        assert not negative & 0x80


# ---------------------------------------------------------------------------
# stream-input WebSocket
# ---------------------------------------------------------------------------

class TestStreamInput:
    def test_bos_text_eos_yields_audio_then_final(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input"
                "?model_id=eleven_monolingual_v1&output_format=pcm_24000") as ws:
            ws.send_json({"text": " ", "voice_settings": {"stability": 0.5}})
            ws.send_json({"text": "hello world"})
            ws.send_json({"text": ""})
            audio, frames = _drain(ws)

        assert audio
        assert frames[-1]["audio"] is None
        assert frames[-1]["isFinal"] is True
        assert engine.calls == [("hello world", {})]

    def test_frames_carry_alignment_keys(self, client):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            _, frames = _drain(ws)

        for frame in frames:
            assert "normalizedAlignment" in frame
            assert "alignment" in frame

    def test_only_final_frame_is_flagged_final(self, client):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            _, frames = _drain(ws)

        assert [f["isFinal"] for f in frames[:-1]] == [None] * (len(frames) - 1)

    def test_text_chunks_are_concatenated_into_one_generation(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hello "})
            ws.send_json({"text": "world"})
            ws.send_json({"text": ""})
            _drain(ws)

        assert engine.calls == [("hello world", {})]

    def test_flush_triggers_generation_before_eos(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "first"})
            ws.send_json({"flush": True})
            first = ws.receive_json()
            assert first["audio"]
            assert first["isFinal"] is None

            ws.send_json({"text": "second"})
            ws.send_json({"text": ""})
            _drain(ws)

        assert [call[0] for call in engine.calls] == ["first", "second"]

    def test_voice_id_passed_to_plugin(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/voice1/stream-input") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            _drain(ws)

        assert engine.calls[0][1] == {"voice": "voice1"}

    def test_language_code_passed_to_plugin(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input"
                "?language_code=de-de") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hallo"})
            ws.send_json({"text": ""})
            _drain(ws)

        assert engine.calls[0][1] == {"lang": "de-de"}

    def test_bos_only_stream_generates_no_audio(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " ", "voice_settings": {"stability": 0.5}})
            ws.send_json({"text": ""})
            audio, frames = _drain(ws)

        assert audio == b""
        assert frames == [{
            "audio": None,
            "isFinal": True,
            "normalizedAlignment": None,
            "alignment": None,
        }]
        assert engine.calls == []

    def test_api_key_header_accepted_and_ignored(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input",
                headers={"xi-api-key": "fake-key"}) as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            audio, _ = _drain(ws)

        assert audio

    def test_api_key_in_bos_message_accepted_and_ignored(self, client, engine):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input") as ws:
            ws.send_json({"text": " ", "xi_api_key": "fake-key"})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            audio, _ = _drain(ws)

        assert audio
        assert engine.calls == [("hi", {})]

    def test_pcm_output_matches_requested_rate(self, client):
        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input"
                "?output_format=pcm_24000") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            audio, _ = _drain(ws)

        assert not audio.startswith(b"RIFF")
        assert len(audio) // 2 == pytest.approx(2400, abs=2)

    def test_path_returning_plugin_streams(self, engine, monkeypatch):
        """Plugins that return a pathlib.Path synthesize over the socket."""
        monkeypatch.setattr(engine, "synthesize", _path_synthesize(engine))
        app = FastAPI()
        app.include_router(make_elevenlabs_router(engine))

        with TestClient(app).websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input"
                "?output_format=pcm_24000") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "hi"})
            ws.send_json({"text": ""})
            audio, _ = _drain(ws)

        assert not audio.startswith(b"RIFF")
        assert len(audio) // 2 == pytest.approx(2400, abs=2)

    def test_large_audio_split_across_frames(self, client, engine, monkeypatch):
        def long_synth(utterance, **kwargs):
            engine.calls.append((utterance, kwargs))
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            _write_wav(tmp.name, frames=SRC_RATE * 3)
            return tmp.name, None

        monkeypatch.setattr(engine, "synthesize", long_synth)

        with client.websocket_connect(
                "/elevenlabs/v1/text-to-speech/default/stream-input"
                "?output_format=pcm_16000") as ws:
            ws.send_json({"text": " "})
            ws.send_json({"text": "a long utterance"})
            ws.send_json({"text": ""})
            audio, frames = _drain(ws)

        assert len(frames) > 2
        assert len(audio) == SRC_RATE * 3 * 2


# ---------------------------------------------------------------------------
# HTTP surface, driven by a plugin that returns a pathlib.Path
# ---------------------------------------------------------------------------

class TestPathReturningPlugin:
    @pytest.fixture
    def client(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "synthesize", _path_synthesize(engine))
        app = FastAPI()
        app.include_router(make_elevenlabs_router(engine))
        return TestClient(app)

    @pytest.mark.parametrize("fmt", ["pcm_24000", "ulaw_8000", "mp3_44100_128"])
    def test_synthesize_returns_audio(self, client, fmt):
        resp = client.post(
            f"/elevenlabs/v1/text-to-speech/default?output_format={fmt}",
            json={"text": "hello world"},
        )
        assert resp.status_code == 200
        assert resp.content

    def test_pcm_is_headerless_and_resampled(self, client):
        resp = client.post(
            "/elevenlabs/v1/text-to-speech/default?output_format=pcm_24000",
            json={"text": "hello world"},
        )
        assert not resp.content.startswith(b"RIFF")
        assert len(resp.content) // 2 == pytest.approx(2400, abs=2)
