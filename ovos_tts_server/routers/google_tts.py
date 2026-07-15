# Licensed under the Apache License, Version 2.0
"""Google Cloud TTS-compatible endpoint."""
import base64
from starlette.concurrency import run_in_threadpool
from typing import Optional

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


class GoogleTTSInput(BaseModel):
    """Synthesis input: either plain text or SSML."""

    text: Optional[str] = Field(default=None, min_length=1)
    ssml: Optional[str] = Field(default=None, min_length=1)


class GoogleTTSVoice(BaseModel):
    """Voice selection parameters."""

    languageCode: str = Field(default="en-US", min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)
    ssmlGender: Optional[str] = Field(
        default=None,
        description=(
            "Google canonical values: 'SSML_VOICE_GENDER_UNSPECIFIED', "
            "'MALE', 'FEMALE', 'NEUTRAL'. Any string accepted and "
            "forwarded to the OVOS plugin."
        ),
    )


class GoogleTTSAudioConfig(BaseModel):
    """Audio encoding configuration."""

    audioEncoding: str = Field(
        default="MP3",
        description=(
            "Output audio encoding. Google canonical values: 'MP3', "
            "'LINEAR16', 'OGG_OPUS', 'MULAW', 'ALAW'. Any string accepted; "
            "unknown values fall back to WAV when pydub can't encode."
        ),
    )
    speakingRate: Optional[float] = Field(default=None, ge=0.25, le=4.0)
    pitch: Optional[float] = Field(default=None, ge=-20.0, le=20.0)
    volumeGainDb: Optional[float] = Field(default=None, ge=-96.0, le=16.0)
    sampleRateHertz: Optional[int] = Field(default=None, gt=0)


class GoogleTTSRequest(BaseModel):
    """Request body for POST /v1/text:synthesize."""

    input: GoogleTTSInput
    voice: GoogleTTSVoice = Field(default_factory=GoogleTTSVoice)
    audioConfig: GoogleTTSAudioConfig = Field(default_factory=GoogleTTSAudioConfig)


class GoogleTTSResponse(BaseModel):
    """Response from POST /v1/text:synthesize."""

    audioContent: str  # base64-encoded audio


def make_google_tts_router(engine) -> APIRouter:
    """Create Google Cloud TTS-compatible router."""
    router = APIRouter(prefix="/google-tts", tags=["google-tts"])

    _FMT_MAP = {
        "MP3": "mp3",
        "LINEAR16": "wav",
        "OGG_OPUS": "ogg",
        "MULAW": "wav",
        "ALAW": "wav",
    }

    @router.post("/v1/text:synthesize", response_model=GoogleTTSResponse)
    def synthesize(
            request: GoogleTTSRequest,
            key: Optional[str] = Query(default=None),
            authorization: Optional[str] = Header(default=None),
    ) -> GoogleTTSResponse:
        """Synthesize speech (Google Cloud TTS-compatible).

        Args:
            request: Google TTS request with input text/SSML, voice, and audio config.
            key: API key query param (accepted, ignored).
            authorization: Bearer token (accepted, ignored).

        Returns:
            GoogleTTSResponse with base64-encoded audio.
        """
        utterance = request.input.ssml or request.input.text or ""
        synth_kwargs = {"lang": request.voice.languageCode}
        if request.voice.name:
            synth_kwargs["voice"] = request.voice.name

        fmt = _FMT_MAP.get(request.audioConfig.audioEncoding, "mp3")
        audio_path, _ = await run_in_threadpool(engine.synthesize, utterance, **synth_kwargs)
        audio_bytes, _ = convert_audio(audio_path, fmt)
        return GoogleTTSResponse(audioContent=base64.b64encode(audio_bytes).decode())

    return router
