# Licensed under the Apache License, Version 2.0
"""Azure Cognitive Services TTS-compatible endpoint."""
import re
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import Response

from ovos_tts_server.audio_utils import convert_audio


def make_azure_tts_router(engine) -> APIRouter:
    """Create Azure Cognitive Services TTS-compatible router."""
    router = APIRouter(prefix="/azure-tts", tags=["azure-tts"])

    def _parse_output_format(fmt_header: Optional[str]) -> str:
        """Map Azure X-Microsoft-OutputFormat header to a format string."""
        if not fmt_header:
            return "mp3"
        h = fmt_header.lower()
        if "mp3" in h:
            return "mp3"
        if "pcm" in h or "wav" in h or "riff" in h:
            return "wav"
        if "ogg" in h or "opus" in h:
            return "ogg"
        if "alaw" in h:
            return "wav"
        return "mp3"

    def _extract_ssml(ssml: str) -> tuple[str, Optional[str], Optional[str]]:
        """Extract text, voice name, and language from SSML body.

        Args:
            ssml: Raw SSML XML string.

        Returns:
            Tuple of (text, voice_name_or_None, lang_or_None).
        """
        voice_match = re.search(r'<voice[^>]*>', ssml, re.IGNORECASE)
        voice_name = None
        lang = None
        if voice_match:
            tag = voice_match.group(0)
            name_m = re.search(r'name=["\']([^"\']+)["\']', tag)
            lang_m = re.search(r'xml:lang=["\']([^"\']+)["\']', tag)
            if name_m:
                voice_name = name_m.group(1)
            if lang_m:
                lang = lang_m.group(1)
        # Strip all XML tags to get plain text
        text = re.sub(r'<[^>]+>', '', ssml).strip()
        return text, voice_name, lang

    @router.post("/cognitiveservices/v1")
    async def azure_tts(
            request: Request,
            x_microsoft_output_format: Optional[str] = Header(default=None, alias="X-Microsoft-OutputFormat"),
            ocp_apim_subscription_key: Optional[str] = Header(default=None, alias="Ocp-Apim-Subscription-Key"),
    ) -> Response:
        """Synthesize speech (Azure Cognitive Services TTS-compatible).

        Accepts SSML body. Parses text and voice from SSML tags.

        Args:
            request: Raw request — body is SSML XML.
            x_microsoft_output_format: Output format header (accepted, mapped to fmt).
            ocp_apim_subscription_key: Subscription key (accepted, ignored).

        Returns:
            Binary audio response in requested format.
        """
        body_bytes = await request.body()
        ssml = body_bytes.decode("utf-8", errors="replace")
        text, voice_name, lang = _extract_ssml(ssml)

        synth_kwargs = {}
        if voice_name:
            synth_kwargs["voice"] = voice_name
        if lang:
            synth_kwargs["lang"] = lang

        fmt = _parse_output_format(x_microsoft_output_format)
        audio_path, _ = engine.synthesize(text or ssml, **synth_kwargs)
        audio_bytes, mime = convert_audio(audio_path, fmt)
        return Response(content=audio_bytes, media_type=mime)

    return router
