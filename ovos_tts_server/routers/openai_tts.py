# Licensed under the Apache License, Version 2.0
"""OpenAI-compatible TTS endpoint."""
from starlette.concurrency import run_in_threadpool
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class OpenAITTSRequest(BaseModel):
    """Request body for OpenAI /v1/audio/speech."""

    model: str = Field(
        default="tts-1",
        description=(
            "Model identifier. OpenAI canonical values include 'tts-1', "
            "'tts-1-hd', 'gpt-4o-mini-tts'. Any string is accepted and "
            "forwarded to the underlying OVOS plugin to interpret."
        ),
    )
    input: str = Field(..., min_length=1, max_length=4096)
    voice: str = Field(
        default="alloy",
        description=(
            "Voice identifier. OpenAI canonical voices (alloy, echo, "
            "fable, onyx, nova, shimmer, ash, ballad, coral, sage, verse) "
            "are accepted, but so is any other string — the OVOS plugin "
            "decides what to do with it."
        ),
    )
    response_format: str = Field(
        default="mp3",
        description=(
            "Output audio format. Common: 'mp3', 'opus', 'aac', 'flac', "
            "'wav', 'pcm'. Unknown values fall back to WAV when pydub "
            "can't encode them."
        ),
    )
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


def make_openai_tts_router(engine) -> APIRouter:
    """Create OpenAI TTS-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with OpenAI-compatible /v1/audio/speech endpoint.
    """
    router = APIRouter(prefix="/openai", tags=["openai-tts"])

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
        audio_path, _ = await run_in_threadpool(engine.synthesize, request.input)
        audio_bytes, mime = convert_audio(audio_path, request.response_format)
        return Response(content=audio_bytes, media_type=mime)

    return router
