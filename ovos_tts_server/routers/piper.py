# Licensed under the Apache License, Version 2.0
"""Piper TTS HTTP server-compatible endpoint."""
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response


def make_piper_router(engine) -> APIRouter:
    """Create Piper TTS HTTP server-compatible router."""
    router = APIRouter(tags=["piper"])

    @router.get("/")
    def piper_tts(
            text: str = Query(..., min_length=1),
            voice: Optional[str] = Query(default=None, min_length=1),
    ) -> Response:
        """Synthesize speech (Piper HTTP server-compatible).

        Args:
            text: Text to synthesize (required, non-empty).
            voice: Optional voice/model identifier.

        Returns:
            WAV audio response.
        """
        synth_kwargs = {}
        if voice:
            synth_kwargs["voice"] = voice

        audio_path, _ = engine.synthesize(text, **synth_kwargs)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        return Response(content=audio_bytes, media_type="audio/wav")

    return router
