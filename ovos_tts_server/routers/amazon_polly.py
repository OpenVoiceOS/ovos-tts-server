# Licensed under the Apache License, Version 2.0
"""Amazon Polly-compatible TTS endpoint."""
from typing import Literal, Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class PollyRequest(BaseModel):
    """Request body for POST /v1/speech (Amazon Polly)."""

    Text: str = Field(..., min_length=1)
    VoiceId: str = Field(default="Joanna", min_length=1)
    OutputFormat: Literal["mp3", "ogg_vorbis", "pcm", "json"] = "mp3"
    Engine: Optional[Literal["standard", "neural", "long-form", "generative"]] = None
    LanguageCode: Optional[str] = Field(default=None, min_length=1)
    TextType: Literal["text", "ssml"] = "text"
    SampleRate: Optional[str] = None


def make_amazon_polly_router(engine) -> APIRouter:
    """Create Amazon Polly-compatible router."""
    router = APIRouter(tags=["amazon-polly"])

    _FMT_MAP = {"mp3": "mp3", "ogg_vorbis": "ogg", "pcm": "wav", "json": "mp3"}
    _MIME_MAP = {"mp3": "audio/mpeg", "ogg_vorbis": "audio/ogg", "pcm": "audio/pcm", "json": "audio/mpeg"}

    @router.post("/v1/speech")
    def synthesize_speech(
            request: PollyRequest,
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (Amazon Polly-compatible).

        Args:
            request: Polly synthesis request.
            authorization: AWS SigV4 Authorization header (accepted, ignored).

        Returns:
            Binary audio response in requested format.
        """
        synth_kwargs = {}
        if request.VoiceId:
            synth_kwargs["voice"] = request.VoiceId
        if request.LanguageCode:
            synth_kwargs["lang"] = request.LanguageCode

        fmt = _FMT_MAP.get(request.OutputFormat, "mp3")
        audio_path, _ = engine.synthesize(request.Text, **synth_kwargs)
        audio_bytes, _ = convert_audio(audio_path, fmt)
        mime = _MIME_MAP.get(request.OutputFormat, "audio/mpeg")
        return Response(content=audio_bytes, media_type=mime)

    return router
