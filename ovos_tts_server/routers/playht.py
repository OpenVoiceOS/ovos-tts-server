# Licensed under the Apache License, Version 2.0
"""PlayHT-compatible TTS endpoints.

Implements enough of PlayHT's HTTP API for the official ``pyht`` SDK to be
used as a drop-in client: the ``/api/v4/sdk-auth`` inference-coordinates
handshake plus the ``/api/v2/tts/stream`` synthesis endpoint. Point a stock
``pyht.Client`` at this server by overriding only its coordinates ``api_url``
(see ``examples/playht_example.py``); no monkey-patching of SDK internals.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from ovos_tts_server.audio_utils import convert_audio


# Voice engines the pyht SDK demands coordinates for (REQUIRED_MODELS).
_PLAYHT_MODELS = ["Play3.0-mini", "PlayDialog", "PlayDialogMultilingual", "PlayDialogArabic"]

# pyht ``output_format`` value -> convert_audio container name.
_FORMAT_MAP = {"raw": "pcm", "mulaw": "wav"}


class PlayHTTTSRequest(BaseModel):
    """Request body for PlayHT ``POST /api/v2/tts/stream``.

    Accepts both the hand-rolled HTTP shape (``text`` as a string) and the
    official ``pyht`` SDK shape (``text`` as a single-element list, plus
    ``voice_engine``/``version`` and assorted generation params we ignore).
    """

    model_config = {"extra": "ignore"}

    text: Union[str, List[str]] = Field(..., description="Text to synthesize.")
    voice: Optional[str] = Field(
        default=None,
        description="Voice identifier or URL. Forwarded to plugin.",
    )
    output_format: str = Field(
        default="mp3",
        description="Output audio format: 'mp3', 'wav', 'ogg', 'flac', 'raw', 'mulaw'.",
    )
    quality: Optional[str] = Field(
        default=None,
        description="Quality preset ('draft', 'low', 'medium', 'high', 'premium'). Accepted, ignored.",
    )
    speed: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    sample_rate: Optional[int] = Field(default=None, ge=8000, le=48000)

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: Union[str, List[str]]) -> Union[str, List[str]]:
        joined = " ".join(v) if isinstance(v, list) else v
        if not joined or not joined.strip():
            raise ValueError("text must not be empty")
        return v


def make_playht_router(engine) -> APIRouter:
    """Create PlayHT-compatible router.

    Args:
        engine: TTSEngineWrapper instance.

    Returns:
        Configured APIRouter with PlayHT-compatible ``/api/v4/sdk-auth`` and
        ``/api/v2/tts/stream`` endpoints.
    """
    router = APIRouter(prefix="/playht", tags=["playht"])

    @router.post("/api/v4/sdk-auth")
    def sdk_auth(
            request: Request,
            x_user_id: Optional[str] = Header(default=None, alias="X-USER-ID"),
            authorization: Optional[str] = Header(default=None),
    ) -> JSONResponse:
        """PlayHT inference-coordinates handshake used by the official pyht SDK.

        Returns coordinates that point the SDK back at this server's
        ``/api/v2/tts/stream`` endpoint, so a stock ``pyht.Client`` can be used
        as a drop-in by overriding only its coordinates ``api_url``.

        Args:
            request: Incoming request, used to derive this server's base URL.
            x_user_id: PlayHT user ID header (accepted, ignored).
            authorization: Bearer API key header (accepted, ignored).

        Returns:
            JSON coordinates document (``expires_at`` + per-model stream URLs).
        """
        base = str(request.base_url).rstrip("/")
        stream_url = f"{base}/playht/api/v2/tts/stream"
        ws_url = stream_url.replace("http", "ws", 1)
        # Far-future expiry, formatted exactly how pyht parses it
        # (datetime.strptime(..., "%Y-%m-%dT%H:%M:%S.%fZ")).
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        coords = {"expires_at": expires_at}
        for model in _PLAYHT_MODELS:
            coords[model] = {
                "http_streaming_url": stream_url,
                "websocket_url": ws_url,
            }
        return JSONResponse(coords)

    @router.post("/api/v2/tts/stream")
    def tts_stream(
            request: PlayHTTTSRequest,
            x_user_id: Optional[str] = Header(default=None, alias="X-USER-ID"),
            authorization: Optional[str] = Header(default=None),
    ) -> Response:
        """Synthesize speech (PlayHT-compatible).

        Args:
            request: PlayHT TTS request body.
            x_user_id: PlayHT user ID header (accepted, ignored).
            authorization: Secret API key header (accepted, ignored).

        Returns:
            Audio response in requested format.
        """
        text = request.text
        if isinstance(text, list):
            text = " ".join(text)

        synth_kwargs = {}
        if request.voice:
            synth_kwargs["voice"] = request.voice

        audio_path, _ = engine.synthesize(text, **synth_kwargs)

        fmt = _FORMAT_MAP.get(request.output_format, request.output_format)
        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

    return router
