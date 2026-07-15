# Licensed under the Apache License, Version 2.0
"""Amazon Polly-compatible TTS endpoint."""
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class PollyRequest(BaseModel):
    """Request body for POST /v1/speech (Amazon Polly)."""

    Text: str = Field(..., min_length=1)
    VoiceId: str = Field(
        default="Joanna",
        min_length=1,
        description=(
            "Voice identifier. Polly canonical voices (Joanna, Matthew, "
            "Ivy, ...) are accepted, but so is any string — the OVOS "
            "plugin decides what to do with it."
        ),
    )
    OutputFormat: str = Field(
        default="mp3",
        description=(
            "Output audio format. Polly canonical values: 'mp3', "
            "'ogg_vorbis', 'pcm', 'json'. Any string is accepted; "
            "unknown formats fall back to WAV when pydub can't encode."
        ),
    )
    Engine: Optional[str] = Field(
        default=None,
        description=(
            "Engine variant. Polly canonical: 'standard', 'neural', "
            "'long-form', 'generative'. Forwarded to the OVOS plugin "
            "as-is — any string is allowed."
        ),
    )
    LanguageCode: Optional[str] = Field(default=None, min_length=1)
    TextType: str = Field(
        default="text",
        description="'text' or 'ssml'. Forwarded to the plugin; any value accepted.",
    )
    SampleRate: Optional[str] = None


def make_amazon_polly_router(engine) -> APIRouter:
    """Create Amazon Polly-compatible router."""
    router = APIRouter(prefix="/amazon-polly", tags=["amazon-polly"])

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
