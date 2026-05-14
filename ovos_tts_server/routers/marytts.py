"""MaryTTS-compatible HTTP endpoints.

Exposes /process, /locales and /voices so apps already speaking MaryTTS can
use any OVOS TTS plugin as a drop-in replacement. Mounted at the root (no
prefix) because the upstream MaryTTS HTTP API uses bare paths.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


class MaryTTSInput(BaseModel):
    """Pydantic model for validating MaryTTS /process API requests."""
    INPUT_TEXT: str = Field(..., description="The text to synthesize")
    INPUT_TYPE: Literal["TEXT", "SSML"] = "TEXT"
    LOCALE: Optional[str] = Field(None, description="Target Locale (e.g. en_US)")
    VOICE: Optional[str] = Field(None, description="Target Voice name")
    OUTPUT_TYPE: str = "AUDIO"
    AUDIO: str = "WAVE_FILE"


def make_marytts_router(engine) -> APIRouter:
    """Build a MaryTTS-compatible router bound to `engine`."""
    router = APIRouter(tags=["MaryTTS"])

    @router.get("/locales")
    def mary_locales() -> Response:
        return Response(content="\n".join(engine.langs), media_type="text/plain")

    @router.get("/voices")
    def mary_voices() -> Response:
        lines = [f"default {engine.lang} m {engine.plugin_name}"]
        return Response(content="\n".join(lines), media_type="text/plain")

    @router.api_route("/process", methods=["GET", "POST"])
    def mary_process(params: MaryTTSInput = Depends()) -> FileResponse:
        synth_kwargs = {}
        if params.LOCALE:
            synth_kwargs["lang"] = params.LOCALE
        if params.VOICE:
            synth_kwargs["voice"] = params.VOICE.replace("_", " ")
        audio_path, _ = engine.synthesize(params.INPUT_TEXT, **synth_kwargs)
        return FileResponse(audio_path, media_type="audio/wav")

    return router
