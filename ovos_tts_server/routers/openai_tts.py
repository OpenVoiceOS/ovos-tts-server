# Licensed under the Apache License, Version 2.0
"""OpenAI-compatible TTS endpoint."""
from typing import Literal, Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class OpenAITTSRequest(BaseModel):
    """Request body for OpenAI /v1/audio/speech."""

    model: Literal["tts-1", "tts-1-hd"] = "tts-1"
    input: str = Field(..., min_length=1, max_length=4096)
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy"
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


def make_openai_tts_router(engine) -> APIRouter:
    """Create OpenAI TTS-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with OpenAI-compatible /v1/audio/speech endpoint.
    """
    router = APIRouter(tags=["openai-tts"])

    @router.post("/v1/audio/speech")
    def speech(
            request: OpenAITTSRequest,
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (OpenAI-compatible).

        Args:
            request: OpenAI TTS request body.
            authorization: Bearer token (accepted, ignored).

        Returns:
            Audio response in requested format.
        """
        # All OpenAI voice names map to plugin default — voice kwarg intentionally omitted
        audio_path, _ = engine.synthesize(request.input)
        audio_bytes, mime = convert_audio(audio_path, request.response_format)
        return Response(content=audio_bytes, media_type=mime)

    return router
