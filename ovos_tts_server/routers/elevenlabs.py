# Licensed under the Apache License, Version 2.0
"""ElevenLabs-compatible TTS endpoints.

Covers both surfaces real ElevenLabs clients use:

* the HTTP API (`/v1/voices`, `/v1/models`, `/v1/text-to-speech/{voice_id}`)
* the WebSocket streaming API
  (`/v1/text-to-speech/{voice_id}/stream-input`)

WebSocket ``stream-input`` protocol
===================================

The client connects with the voice in the path and the synthesis options in
the query string (``model_id``, ``output_format``, ``language_code``,
``sync_alignment``, ...), then speaks JSON text frames:

1. BOS — ``{"text": " ", "voice_settings": {...}, "generation_config": {...}}``
   opens the stream. Its text payload is a single space and carries no content.
2. Content — ``{"text": "Hello there "}``, repeated. Text accumulates until a
   generation is triggered.
3. ``{"flush": true}`` (or ``{"text": "some text", "flush": true}``) forces the
   buffered text to be generated immediately.
4. EOS — ``{"text": ""}`` closes the stream: whatever is buffered is generated
   and the connection terminates.

The server answers with JSON frames carrying base64 audio:

    {"audio": "<base64>", "isFinal": null,
     "normalizedAlignment": null, "alignment": null}

and terminates the stream with a frame that has no audio and ``isFinal`` true.

Authentication is via the ``xi-api-key`` header or an ``xi_api_key`` field in
the BOS message; both are accepted and ignored, since a self-hosted server
has no keys to check.

Reference: https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input
"""
from __future__ import annotations

import array
import base64
import os
import sys
import wave
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio

#: Plugins return either a str or a pathlib.Path from synthesize().
AudioPath = Union[str, "os.PathLike[str]"]

#: Audio bytes handed to the client in a single WebSocket frame.
AUDIO_CHUNK_SIZE = 8192

#: ElevenLabs' own default when no output_format is given.
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def _parse_output_format(output_format: str) -> Tuple[str, int]:
    """Split an ElevenLabs output_format string into (container, sample_rate).

    Args:
        output_format: e.g. "pcm_24000", "mp3_44100_128", "ulaw_8000".

    Returns:
        Tuple of container name and sample rate in Hz. Unparseable formats fall
        back to the ElevenLabs default (mp3 at 44100 Hz).
    """
    parts = (output_format or "").lower().split("_")
    container = parts[0] if parts and parts[0] else "mp3"
    rate = 44100
    if len(parts) > 1 and parts[1].isdigit():
        rate = int(parts[1])
    if container not in ("pcm", "mp3", "ulaw", "opus", "ogg", "flac", "wav"):
        return "mp3", 44100
    return container, rate


def _read_samples(wav_path: AudioPath) -> Tuple[array.array, int]:
    """Read a WAV file as mono 16-bit samples.

    Args:
        wav_path: Path to source WAV file.

    Returns:
        Tuple of (samples, source_sample_rate). Multi-channel input is
        downmixed by averaging, 8-bit input is scaled up to 16-bit.
    """
    # wave.open() only opens str paths; anything else it treats as a file object
    with wave.open(os.fspath(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        src_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if width == 1:
        # 8-bit WAV samples are unsigned
        samples = array.array("h", ((b - 128) << 8 for b in frames))
    elif width == 2:
        samples = array.array("h")
        samples.frombytes(frames)
        if sys.byteorder == "big":
            samples.byteswap()
    else:
        step = width
        samples = array.array("h", (
            int.from_bytes(frames[i + step - 2:i + step], "little", signed=True)
            for i in range(0, len(frames) - step + 1, step)
        ))

    if channels > 1:
        mono = array.array("h", (
            sum(samples[i:i + channels]) // channels
            for i in range(0, len(samples) - channels + 1, channels)
        ))
        samples = mono
    return samples, src_rate


def _resample_pcm(wav_path: AudioPath, sample_rate: int) -> bytes:
    """Read a WAV file as headerless mono 16-bit little-endian PCM.

    Args:
        wav_path: Path to source WAV file.
        sample_rate: Target sample rate in Hz.

    Returns:
        Raw PCM frames at the requested sample rate.
    """
    samples, src_rate = _read_samples(wav_path)

    if src_rate != sample_rate and samples:
        ratio = src_rate / sample_rate
        n_out = max(1, int(len(samples) / ratio))
        last = len(samples) - 1
        resampled = array.array("h")
        for i in range(n_out):
            pos = i * ratio
            left = int(pos)
            right = min(left + 1, last)
            frac = pos - left
            value = samples[left] + (samples[right] - samples[left]) * frac
            resampled.append(int(round(value)))
        samples = resampled

    if sys.byteorder == "big":
        samples = array.array("h", samples)
        samples.byteswap()
    return samples.tobytes()


def _linear_to_ulaw(pcm: bytes) -> bytes:
    """Encode 16-bit little-endian PCM as 8-bit G.711 mu-law.

    Args:
        pcm: Raw 16-bit little-endian mono PCM frames.

    Returns:
        Mu-law encoded bytes, one per input sample.
    """
    bias = 0x84
    clip = 32635
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()

    out = bytearray()
    for sample in samples:
        sign = 0x80 if sample < 0 else 0x00
        magnitude = min(abs(sample), clip) + bias
        exponent = 7
        mask = 0x4000
        while exponent > 0 and not magnitude & mask:
            exponent -= 1
            mask >>= 1
        mantissa = (magnitude >> (exponent + 3)) & 0x0F
        out.append(~(sign | (exponent << 4) | mantissa) & 0xFF)
    return bytes(out)


def encode_audio(wav_path: AudioPath, output_format: str) -> Tuple[bytes, str]:
    """Encode a synthesized WAV file into an ElevenLabs output_format.

    Args:
        wav_path: Path to source WAV file.
        output_format: ElevenLabs output_format string.

    Returns:
        Tuple of (audio_bytes, mime_type).
    """
    wav_path = os.fspath(wav_path)
    container, rate = _parse_output_format(output_format)
    if container == "pcm":
        return _resample_pcm(wav_path, rate), "audio/pcm"
    if container == "ulaw":
        pcm = _resample_pcm(wav_path, rate)
        return _linear_to_ulaw(pcm), "audio/basic"
    if container == "opus":
        # Opus is carried in an Ogg container by ElevenLabs
        return convert_audio(wav_path, "ogg")
    return convert_audio(wav_path, container)


def _synth_kwargs(voice_id: str) -> Dict[str, str]:
    """Map a requested voice_id to plugin synthesize() kwargs.

    Args:
        voice_id: Voice identifier from the request path.

    Returns:
        Kwargs for engine.synthesize(); the plugin default is used for
        the reserved "default" voice.
    """
    if voice_id and voice_id != "default":
        return {"voice": voice_id}
    return {}


def _audio_frame(audio_b64: Optional[str], is_final: bool = False) -> Dict[str, Any]:
    """Build a stream-input server frame.

    Args:
        audio_b64: Base64 audio payload, or None for the terminating frame.
        is_final: True on the frame that terminates the stream.

    Returns:
        JSON-serializable frame in ElevenLabs' stream-input shape.
    """
    return {
        "audio": audio_b64,
        "isFinal": True if is_final else None,
        "normalizedAlignment": None,
        "alignment": None,
    }


class ElevenLabsVoice(BaseModel):
    """ElevenLabs voice descriptor."""

    voice_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class ElevenLabsVoicesResponse(BaseModel):
    """Response for GET /v1/voices."""

    voices: List[ElevenLabsVoice]


class ElevenLabsVoiceSettings(BaseModel):
    """Optional voice settings in ElevenLabs TTS request."""

    stability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    similarity_boost: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    style: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_speaker_boost: Optional[bool] = None


class ElevenLabsTTSRequest(BaseModel):
    """Request body for POST /v1/text-to-speech/{voice_id}."""

    text: str = Field(..., min_length=1)
    model_id: Optional[str] = Field(default="eleven_monolingual_v1", min_length=1)
    voice_settings: Optional[ElevenLabsVoiceSettings] = None


class ElevenLabsLanguage(BaseModel):
    """Language entry in an ElevenLabs model descriptor."""

    language_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)


class ElevenLabsModel(BaseModel):
    """Model descriptor returned by GET /v1/models."""

    model_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str
    languages: List[ElevenLabsLanguage]
    can_be_finetuned: bool
    can_do_text_to_speech: bool
    can_do_voice_conversion: bool
    can_use_style: bool
    can_use_speaker_boost: bool
    serves_pro_voices: bool
    token_cost_factor: float = Field(..., ge=0.0)
    requires_alpha_access: bool
    max_characters_request_free_user: int = Field(..., ge=0)
    max_characters_request_subscribed_user: int = Field(..., ge=0)


def make_elevenlabs_router(engine) -> APIRouter:
    """Create ElevenLabs-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with ElevenLabs-compatible endpoints.
    """
    router = APIRouter(prefix="/elevenlabs", tags=["elevenlabs"])

    @router.get("/v1/voices", response_model=ElevenLabsVoicesResponse)
    def list_voices(
            xi_api_key: Optional[str] = Header(default=None, alias="xi-api-key"),
    ) -> ElevenLabsVoicesResponse:
        """List available voices (ElevenLabs-compatible).

        Returns:
            ElevenLabsVoicesResponse: Available voices mapped from plugin.
        """
        raw = engine.voices
        if raw:
            voices = [
                ElevenLabsVoice(
                    voice_id=str(v) if not isinstance(v, dict) else v.get("id", str(v)),
                    name=str(v) if not isinstance(v, dict) else v.get("name", str(v)),
                )
                for v in raw
            ]
        else:
            voices = [ElevenLabsVoice(voice_id="default", name="default")]
        return ElevenLabsVoicesResponse(voices=voices)

    @router.post("/v1/text-to-speech/{voice_id}")
    def tts_elevenlabs(
            voice_id: str,
            request: ElevenLabsTTSRequest,
            output_format: str = Query(default="mp3_44100_128", alias="output_format"),
            xi_api_key: Optional[str] = Header(default=None, alias="xi-api-key"),
    ) -> Response:
        """Synthesize speech (ElevenLabs-compatible).

        Args:
            voice_id: Voice identifier passed as voice kwarg to plugin.
            request: TTS request body with text and optional settings.
            output_format: ElevenLabs output_format string (e.g. "mp3_44100_128").
            xi_api_key: API key header (accepted, ignored).

        Returns:
            Audio response in requested format.
        """
        audio_path, _ = engine.synthesize(request.text, **_synth_kwargs(voice_id))
        audio_bytes, mime = encode_audio(audio_path, output_format)
        return Response(content=audio_bytes, media_type=mime)

    @router.websocket("/v1/text-to-speech/{voice_id}/stream-input")
    async def tts_stream_input(
            websocket: WebSocket,
            voice_id: str,
            output_format: str = Query(default=DEFAULT_OUTPUT_FORMAT),
            language_code: Optional[str] = Query(default=None),
    ) -> None:
        """Stream synthesized speech over the ElevenLabs stream-input protocol.

        Args:
            websocket: Client connection.
            voice_id: Voice identifier passed as voice kwarg to plugin.
            output_format: ElevenLabs output_format string (e.g. "pcm_24000").
            language_code: Optional language passed as lang kwarg to plugin.
        """
        await websocket.accept()

        synth_kwargs = _synth_kwargs(voice_id)
        if language_code:
            synth_kwargs["lang"] = language_code

        buffer: List[str] = []

        async def generate() -> None:
            """Synthesize the buffered text and stream it back as audio frames."""
            text = "".join(buffer).strip()
            buffer.clear()
            if not text:
                return
            audio_path, _ = engine.synthesize(text, **synth_kwargs)
            audio_bytes, _mime = encode_audio(audio_path, output_format)
            for start in range(0, len(audio_bytes), AUDIO_CHUNK_SIZE):
                chunk = audio_bytes[start:start + AUDIO_CHUNK_SIZE]
                await websocket.send_json(_audio_frame(
                    base64.b64encode(chunk).decode("utf-8")
                ))

        try:
            while True:
                message: Dict[str, Any] = await websocket.receive_json()

                text = message.get("text")
                if text:
                    buffer.append(text)

                if message.get("flush"):
                    await generate()
                    continue

                if text == "":
                    # End of stream: flush whatever is buffered, then terminate
                    await generate()
                    await websocket.send_json(_audio_frame(None, is_final=True))
                    await websocket.close()
                    return
        except WebSocketDisconnect:
            return
        except Exception:
            # Closing cleanly is more useful than a 1011 to the client
            try:
                await websocket.close()
            except Exception:
                pass

    @router.get("/v1/models", response_model=List[ElevenLabsModel])
    def list_models(
            xi_api_key: Optional[str] = Header(default=None, alias="xi-api-key"),
    ) -> List[ElevenLabsModel]:
        """List available models (ElevenLabs-compatible).

        Returns:
            List of ElevenLabsModel descriptors for the loaded plugin.
        """
        return [
            ElevenLabsModel(
                model_id=engine.plugin_name,
                name=engine.plugin_name,
                description="OVOS TTS Plugin",
                languages=[
                    ElevenLabsLanguage(language_id=lang, name=lang) for lang in engine.langs
                ],
                can_be_finetuned=False,
                can_do_text_to_speech=True,
                can_do_voice_conversion=False,
                can_use_style=False,
                can_use_speaker_boost=False,
                serves_pro_voices=False,
                token_cost_factor=1.0,
                requires_alpha_access=False,
                max_characters_request_free_user=10000,
                max_characters_request_subscribed_user=10000,
            )
        ]

    return router
