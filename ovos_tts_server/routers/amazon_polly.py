# Licensed under the Apache License, Version 2.0
"""Amazon Polly-compatible TTS endpoint."""
from typing import List, Optional

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


class PollyVoice(BaseModel):
    """One entry of a DescribeVoices response (the Polly ``Voice`` type)."""

    Id: str
    Name: str
    LanguageCode: str
    AdditionalLanguageCodes: List[str] = []
    SupportedEngines: List[str] = []


class PollyVoicesResponse(BaseModel):
    """Response body for GET /v1/voices (Amazon Polly DescribeVoices)."""

    Voices: List[PollyVoice]


# OVOS plugins ignore the Polly engine variant, so every voice serves all four.
_POLLY_ENGINES = ["standard", "neural", "long-form", "generative"]


# DescribeVoices "Valid Values" for LanguageCode. en-GB-WLS is not in BCP-47
# case, so Polly's own codes are matched case-insensitively and echoed as listed.
_POLLY_LANGUAGE_CODES = {code.lower(): code for code in (
    "arb", "cmn-CN", "cy-GB", "da-DK", "de-DE", "en-AU", "en-GB", "en-GB-WLS",
    "en-IN", "en-US", "es-ES", "es-MX", "es-US", "fr-CA", "fr-FR", "is-IS",
    "it-IT", "ja-JP", "hi-IN", "ko-KR", "nb-NO", "nl-NL", "pl-PL", "pt-BR",
    "pt-PT", "ro-RO", "ru-RU", "sv-SE", "tr-TR", "en-NZ", "en-ZA", "ca-ES",
    "de-AT", "yue-CN", "ar-AE", "fi-FI", "en-IE", "nl-BE", "fr-BE", "cs-CZ",
    "de-CH", "en-SG",
)}


def _polly_lang(lang: str) -> str:
    """Return a language tag in Polly's spelling, e.g. ``sr-latn-rs`` -> ``sr-Latn-RS``.

    A Polly language code (``en-gb-wls``) comes back as Polly lists it
    (``en-GB-WLS``). Any other tag gets the RFC 5646 section 2.1.1 case:
    lowercase, except a two-letter subtag in uppercase and a four-letter
    subtag in title case when it is not the first subtag and does not follow
    a singleton (``en-ca-x-ca`` -> ``en-CA-x-ca``).
    """
    lang = lang.replace("_", "-")
    if lang.lower() in _POLLY_LANGUAGE_CODES:
        return _POLLY_LANGUAGE_CODES[lang.lower()]
    first, *subtags = lang.lower().split("-")
    cased = [first]
    after_singleton = len(first) == 1
    for tag in subtags:
        if after_singleton:
            cased.append(tag)
        elif len(tag) == 1:
            after_singleton = True
            cased.append(tag)
        elif len(tag) == 2:
            cased.append(tag.upper())
        elif len(tag) == 4:
            cased.append(tag.title())
        else:
            cased.append(tag)
    return "-".join(cased)


def make_amazon_polly_router(engine) -> APIRouter:
    """Create Amazon Polly-compatible router."""
    router = APIRouter(prefix="/amazon-polly", tags=["amazon-polly"])

    _FMT_MAP = {"mp3": "mp3", "ogg_vorbis": "ogg", "pcm": "wav", "json": "mp3"}
    _MIME_MAP = {"mp3": "audio/mpeg", "ogg_vorbis": "audio/ogg", "pcm": "audio/pcm", "json": "audio/mpeg"}

    @router.get("/v1/voices", response_model=PollyVoicesResponse)
    def describe_voices(
            Engine: Optional[str] = None,
            LanguageCode: Optional[str] = None,
            IncludeAdditionalLanguageCodes: bool = False,
            NextToken: Optional[str] = None,
            authorization: Optional[str] = Header(default=None),
    ) -> PollyVoicesResponse:
        """List voices (Amazon Polly DescribeVoices-compatible).

        Every voice of the plugin speaks the plugin's default language, with
        its other languages as additional language codes. A listed language
        without a region matches a request for any region of it. ``Engine`` and
        ``NextToken`` are accepted and ignored: OVOS plugins have no engine
        variants, and the whole list fits in one page.

        Args:
            Engine: Polly engine variant filter (accepted, ignored).
            LanguageCode: Return only voices that speak this language.
            IncludeAdditionalLanguageCodes: Also match voices that speak
                ``LanguageCode`` as an additional language.
            NextToken: Pagination token (accepted, ignored).
            authorization: AWS SigV4 Authorization header (accepted, ignored).

        Returns:
            The plugin's voices, or one ``default`` voice when the plugin
            lists none.
        """
        primary = _polly_lang(engine.lang)
        additional = [_polly_lang(lang) for lang in engine.langs
                      if _polly_lang(lang) != primary]
        voice_ids = [v.get("id", str(v)) if isinstance(v, dict) else str(v)
                     for v in engine.voices] or ["default"]
        voices = [PollyVoice(Id=vid, Name=vid, LanguageCode=primary,
                             AdditionalLanguageCodes=additional,
                             SupportedEngines=_POLLY_ENGINES)
                  for vid in voice_ids]
        if LanguageCode:
            wanted = _polly_lang(LanguageCode)
            # A plugin may list a bare language ("de"), which speaks every
            # regional request for it ("de-DE"). Only a bare listed tag widens
            # the match: a bare requested code such as Polly's "arb" matches
            # only itself.
            matches = {wanted, wanted.split("-")[0]}
            voices = [v for v in voices
                      if v.LanguageCode in matches
                      or (IncludeAdditionalLanguageCodes
                          and matches.intersection(v.AdditionalLanguageCodes))]
        return PollyVoicesResponse(Voices=voices)

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
