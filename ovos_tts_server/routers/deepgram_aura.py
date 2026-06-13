# Licensed under the Apache License, Version 2.0
"""Deepgram Aura-compatible TTS endpoint."""
from typing import Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class DeepgramSpeakRequest(BaseModel):
    """Request body for Deepgram POST /v1/speak."""

    text: str = Field(..., min_length=1)


def make_deepgram_aura_router(engine) -> APIRouter:
    """Create Deepgram Aura-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with Deepgram Aura-compatible /v1/speak endpoint.
    """
    router = APIRouter(prefix="/deepgram", tags=["deepgram-aura"])

    @router.post("/v1/speak")
    def speak(
            request: DeepgramSpeakRequest,
            model: str = Query(default="aura-asteria-en", description="Deepgram model/voice name."),
            encoding: Optional[str] = Query(default=None, description="Audio encoding (linear16, mulaw, mp3, opus, flac)."),
            sample_rate: Optional[int] = Query(default=None),
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (Deepgram Aura-compatible).

        Args:
            request: Request body containing text to synthesize.
            model: Deepgram model name used as voice hint.
            encoding: Requested audio encoding.
            sample_rate: Requested sample rate (accepted, ignored).
            authorization: Bearer token (accepted, ignored).

        Returns:
            Audio response in requested encoding.
        """
        synth_kwargs = {}
        if model:
            synth_kwargs["voice"] = model

        audio_path, _ = engine.synthesize(request.text, **synth_kwargs)

        fmt_map = {
            "linear16": "wav",
            "mulaw": "wav",
            "mp3": "mp3",
            "opus": "ogg",
            "flac": "flac",
        }
        fmt = fmt_map.get(encoding or "", "wav")
        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

    return router
