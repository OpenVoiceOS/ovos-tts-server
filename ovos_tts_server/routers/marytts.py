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
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from ovos_spec_tools.language import closest_lang, standardize_lang
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


def to_mary_locale(tag: str) -> str:
    """Spell a language tag the way MaryTTS does, as a Java locale: en-us -> en_US."""
    return standardize_lang(tag).replace("-", "_")


def resolve_locale(locale: str, langs: List[str]) -> str:
    """Find the engine language a MaryTTS LOCALE asks for.

    The match follows OVOS-INTENT-2 section 2: it ignores case and the
    ``_``/``-`` separator, prefers an exact tag (en over en-us when both are
    listed), and accepts the nearest regional variant (en_AU -> en-gb). A locale
    the engine does not list goes to the engine as a hyphenated tag, for
    engines that do not declare their languages.
    """
    wanted = standardize_lang(locale)
    exact = next((lang for lang in langs if standardize_lang(lang) == wanted), None)
    return exact or closest_lang(locale, langs) or locale.replace("_", "-")


def _register_marytts_routes(router: APIRouter, engine) -> None:
    def engine_langs() -> List[str]:
        return getattr(engine, "langs", None) or [engine.lang]

    @router.get("/locales")
    def mary_locales() -> Response:
        locales = dict.fromkeys(to_mary_locale(lang) for lang in engine_langs())
        return Response(content="\n".join(locales), media_type="text/plain")

    @router.get("/voices")
    def mary_voices() -> Response:
        """Emit one line per voice in MaryTTS's wire format:
            <voice> <lang> <gender> <plugin>
        Real MaryTTS clients (e.g. ovos-tts-plugin-marytts) parse this
        line-by-line to populate their valid_voices / valid_langs sets.
        """
        voices = getattr(engine, "voices", None) or ["default"]
        locales = dict.fromkeys(to_mary_locale(lang) for lang in engine_langs())
        # Pair each voice with each locale so any (voice, locale) combo the
        # plugin tries is in the discovered set.
        lines = [
            f"{voice} {locale} m {engine.plugin_name}"
            for voice in voices for locale in locales
        ]
        return Response(content="\n".join(lines), media_type="text/plain")

    @router.api_route("/process", methods=["GET", "POST"])
    def mary_process(params: MaryTTSInput = Depends()) -> FileResponse:
        synth_kwargs = {}
        if params.LOCALE:
            synth_kwargs["lang"] = resolve_locale(params.LOCALE, engine_langs())
        if params.VOICE:
            synth_kwargs["voice"] = params.VOICE.replace("_", " ")
        try:
            audio_path, _ = engine.synthesize(params.INPUT_TEXT, **synth_kwargs)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"synthesis failed: {exc}",
            ) from exc
        if not os.path.isfile(audio_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="the TTS engine produced no audio; GET /locales and "
                       "GET /voices list what it supports",
            )
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
