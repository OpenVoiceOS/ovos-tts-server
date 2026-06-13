# Licensed under the Apache License, Version 2.0
"""PlayHT-compatible TTS streaming endpoint."""
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class PlayHTTTSRequest(BaseModel):
    """Request body for PlayHT POST /api/v2/tts/stream."""

    text: str = Field(..., min_length=1)
    voice: Optional[str] = Field(
        default=None,
        description="Voice identifier or URL. Forwarded to plugin.",
    )
    output_format: str = Field(
        default="mp3",
        description="Output audio format: 'mp3', 'wav', 'ogg', 'flac', 'mulaw'.",
    )
    quality: Optional[str] = Field(
        default=None,
        description="Quality preset ('draft', 'low', 'medium', 'high', 'premium'). Accepted, ignored.",
    )
    speed: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    sample_rate: Optional[int] = Field(default=None, ge=8000, le=48000)


def make_playht_router(engine) -> APIRouter:
    """Create PlayHT-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with PlayHT-compatible /api/v2/tts/stream endpoint.
    """
    router = APIRouter(prefix="/playht", tags=["playht"])

    @router.post("/api/v2/tts/stream")
    def tts_stream(
            request: PlayHTTTSRequest,
            x_user_id: Optional[str] = Header(default=None, alias="X-USER-ID"),
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (PlayHT-compatible).

        Args:
            request: PlayHT TTS request body.
            x_user_id: PlayHT user ID header (accepted, ignored).
            authorization: Secret API key header (accepted, ignored).

        Returns:
            Audio response in requested format.
        """
        synth_kwargs = {}
        if request.voice:
            synth_kwargs["voice"] = request.voice

        audio_path, _ = engine.synthesize(request.text, **synth_kwargs)

        fmt_map = {
            "mulaw": "wav",
        }
        fmt = fmt_map.get(request.output_format, request.output_format)
        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

    return router
