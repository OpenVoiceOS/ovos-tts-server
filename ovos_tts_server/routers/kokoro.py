# Licensed under the Apache License, Version 2.0
"""Kokoro-compatible TTS endpoint (OpenAI /v1/audio/speech shape)."""
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class KokoroTTSRequest(BaseModel):
    """Request body for Kokoro POST /v1/audio/speech."""

    model: str = Field(
        default="kokoro",
        description="Model identifier forwarded to the underlying OVOS plugin.",
    )
    input: str = Field(..., min_length=1, max_length=4096)
    voice: str = Field(
        default="af_heart",
        description="Voice identifier (e.g. 'af_heart', 'af_bella'). Forwarded to plugin.",
    )
    response_format: str = Field(
        default="mp3",
        description="Output audio format: 'mp3', 'wav', 'flac', 'ogg', 'pcm'.",
    )
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


def make_kokoro_router(engine) -> APIRouter:
    """Create Kokoro-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with Kokoro-compatible /v1/audio/speech endpoint.
    """
    router = APIRouter(prefix="/kokoro", tags=["kokoro"])

    @router.post("/v1/audio/speech")
    def speech(
            request: KokoroTTSRequest,
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (Kokoro-compatible).

        Args:
            request: Kokoro TTS request body.
            authorization: Bearer token (accepted, ignored).

        Returns:
            Audio response in requested format.
        """
        synth_kwargs = {}
        if request.voice and request.voice != "af_heart":
            synth_kwargs["voice"] = request.voice

        audio_path, _ = engine.synthesize(request.input, **synth_kwargs)
        audio_bytes, mime = convert_audio(audio_path, request.response_format)
        return Response(content=audio_bytes, media_type=mime)

    return router
