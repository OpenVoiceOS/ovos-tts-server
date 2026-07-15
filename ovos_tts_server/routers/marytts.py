"""MaryTTS-compatible HTTP endpoints.

Exposes /process, /locales and /voices so apps already speaking MaryTTS can
use any OVOS TTS plugin as a drop-in replacement.

Two routers are exposed:
- `make_marytts_router(engine)` mounts under `/marytts` — consistent with
  every other compat router so multiple compat layers can coexist.
- `make_marytts_root_router(engine)` mounts the same handlers at the root
  (no prefix) for legacy assistive tech (Orca, NVDA bridges, screen-reader
  TTS adaptors, Home Assistant's `marytts` integration) that hardcode the
  bare upstream paths and can't be reconfigured to a sub-path.

Both routers expose identical behaviour; register either or both.
"""
from starlette.concurrency import run_in_threadpool
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


class MaryTTSInput(BaseModel):
    """Pydantic model for validating MaryTTS /process API requests."""
    INPUT_TEXT: str = Field(..., description="The text to synthesize")
    INPUT_TYPE: str = Field(
        default="TEXT",
        description=(
            "MaryTTS canonical values: 'TEXT' or 'SSML'. Accepted and "
            "echoed for protocol compatibility; the OVOS plugin handles "
            "SSML detection itself if it supports it."
        ),
    )
    LOCALE: Optional[str] = Field(None, description="Target Locale (e.g. en_US)")
    VOICE: Optional[str] = Field(None, description="Target Voice name")
    OUTPUT_TYPE: str = "AUDIO"
    AUDIO: str = "WAVE_FILE"


def _register_marytts_routes(router: APIRouter, engine) -> None:
    @router.get("/locales")
    def mary_locales() -> Response:
        langs = getattr(engine, "langs", None) or [engine.lang]
        return Response(content="\n".join(langs), media_type="text/plain")

    @router.get("/voices")
    def mary_voices() -> Response:
        """Emit one line per voice in MaryTTS's wire format:
            <voice> <lang> <gender> <plugin>
        Real MaryTTS clients (e.g. ovos-tts-plugin-marytts) parse this
        line-by-line to populate their valid_voices / valid_langs sets.
        """
        voices = getattr(engine, "voices", None) or ["default"]
        langs = getattr(engine, "langs", None) or [engine.lang]
        # Pair each voice with each lang so any (voice, lang) combo the
        # plugin tries is in the discovered set.
        lines = [
            f"{voice} {lang} m {engine.plugin_name}"
            for voice in voices for lang in langs
        ]
        return Response(content="\n".join(lines), media_type="text/plain")

    @router.api_route("/process", methods=["GET", "POST"])
    def mary_process(params: MaryTTSInput = Depends()) -> FileResponse:
        synth_kwargs = {}
        if params.LOCALE:
            synth_kwargs["lang"] = params.LOCALE
        if params.VOICE:
            synth_kwargs["voice"] = params.VOICE.replace("_", " ")
        try:
            audio_path, _ = await run_in_threadpool(engine.synthesize, params.INPUT_TEXT, **synth_kwargs)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"synthesis failed: {exc}",
            ) from exc
        return FileResponse(audio_path, media_type="audio/wav")


def make_marytts_router(engine) -> APIRouter:
    """MaryTTS-compatible router mounted under /marytts."""
    router = APIRouter(prefix="/marytts", tags=["marytts"])
    _register_marytts_routes(router, engine)
    return router


def make_marytts_root_router(engine) -> APIRouter:
    """MaryTTS-compatible router mounted at the root.

    Use this for legacy assistive-tech clients that hardcode bare upstream
    paths (`/process`, `/voices`, `/locales`) and cannot be pointed at a
    sub-path.
    """
    router = APIRouter(tags=["marytts (root alias)"])
    _register_marytts_routes(router, engine)
    return router
