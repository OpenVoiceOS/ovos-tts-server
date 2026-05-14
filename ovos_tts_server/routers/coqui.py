# Licensed under the Apache License, Version 2.0
"""Coqui TTS-compatible endpoint."""
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response


def make_coqui_router(engine) -> APIRouter:
    """Create Coqui TTS-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with Coqui-compatible /api/tts endpoint.
    """
    router = APIRouter(prefix="/coqui", tags=["coqui"])

    @router.get("/api/tts")
    def coqui_tts(
            text: str = Query(..., min_length=1),
            speaker_id: Optional[str] = Query(default=None, min_length=1),
            language_id: Optional[str] = Query(default=None, min_length=1),
    ) -> Response:
        """Synthesize speech (Coqui-compatible).

        Args:
            text: Text to synthesize (required, non-empty).
            speaker_id: Optional speaker identifier mapped to voice kwarg.
            language_id: Optional language identifier mapped to lang kwarg.

        Returns:
            WAV audio response.
        """
        synth_kwargs = {}
        if speaker_id:
            synth_kwargs["voice"] = speaker_id
        if language_id:
            synth_kwargs["lang"] = language_id

        audio_path, _ = engine.synthesize(text, **synth_kwargs)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        return Response(content=audio_bytes, media_type="audio/wav")

    return router
