# Licensed under the Apache License, Version 2.0
"""Cartesia Sonic-compatible TTS endpoint."""
from starlette.concurrency import run_in_threadpool
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class CartesiaOutputFormat(BaseModel):
    """Output format descriptor for Cartesia requests."""

    container: str = Field(default="wav", description="Audio container: 'wav', 'mp3', 'raw'.")
    encoding: Optional[str] = Field(default=None, description="PCM encoding, e.g. 'pcm_f32le'.")
    sample_rate: Optional[int] = Field(default=None, ge=8000, le=48000)


class CartesiaTTSRequest(BaseModel):
    """Request body for Cartesia POST /tts/bytes."""

    model_id: str = Field(
        default="sonic-english",
        description="Cartesia model identifier, e.g. 'sonic-english', 'sonic-multilingual'.",
    )
    transcript: str = Field(..., min_length=1)
    voice: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Voice descriptor. May contain 'id' or 'embedding'. Forwarded to plugin.",
    )
    output_format: CartesiaOutputFormat = Field(default_factory=CartesiaOutputFormat)


def make_cartesia_router(engine) -> APIRouter:
    """Create Cartesia-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with Cartesia-compatible /tts/bytes endpoint.
    """
    router = APIRouter(prefix="/cartesia", tags=["cartesia"])

    @router.post("/tts/bytes")
    def tts_bytes(
            request: CartesiaTTSRequest,
            x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
            cartesia_version: Optional[str] = Header(default=None, alias="Cartesia-Version"),
    ) -> Response:
        """Synthesize speech (Cartesia-compatible).

        Args:
            request: Cartesia TTS request body.
            x_api_key: API key header (accepted, ignored).
            cartesia_version: API version header (accepted, ignored).

        Returns:
            Audio response in requested container format.
        """
        synth_kwargs = {}
        if request.voice and isinstance(request.voice, dict):
            voice_id = request.voice.get("id")
            if voice_id:
                synth_kwargs["voice"] = voice_id

        audio_path, _ = await run_in_threadpool(engine.synthesize, request.transcript, **synth_kwargs)

        fmt = request.output_format.container
        if fmt == "raw":
            fmt = "pcm"

        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

    return router
