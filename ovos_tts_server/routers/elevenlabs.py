# Licensed under the Apache License, Version 2.0
"""ElevenLabs-compatible TTS endpoints."""
from starlette.concurrency import run_in_threadpool
from typing import List, Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ovos_tts_server.audio_utils import convert_audio


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
        fmt = "mp3"
        if output_format.startswith("pcm"):
            fmt = "pcm"
        elif output_format.startswith("ulaw"):
            fmt = "wav"
        elif "_" in output_format:
            fmt = output_format.split("_")[0]

        synth_kwargs = {}
        if voice_id and voice_id != "default":
            synth_kwargs["voice"] = voice_id

        audio_path, _ = await run_in_threadpool(engine.synthesize, request.text, **synth_kwargs)
        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

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
