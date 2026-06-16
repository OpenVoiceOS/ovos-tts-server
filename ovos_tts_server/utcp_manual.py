# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""UTCP manual builder for ovos-tts-server.

Generates a UTCPManual JSON document (GET /utcp) that describes every
HTTP endpoint exposed by the server.  UTCP-aware agents (e.g. those using
ovos-tool-adapters' UTCPToolBox) can point at ``GET /utcp`` and
automatically discover all synthesis endpoints without any extra wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ovos_tts_server import TTSEngineWrapper

# UTCP protocol version this manual conforms to.
_UTCP_VERSION = "1.0.1"
_MANUAL_VERSION = "1.0.0"


def build_utcp_manual(engine: "TTSEngineWrapper", base_url: str) -> Dict[str, Any]:
    """Return a UTCPManual dict describing all TTS HTTP endpoints.

    Args:
        engine: The live TTSEngineWrapper (used to populate metadata).
        base_url: The public base URL of the server, e.g.
            ``"http://localhost:9666"``.  Trailing slashes are stripped.

    Returns:
        A dict conforming to the UTCP ``UtcpManual`` schema.
    """
    base_url = base_url.rstrip("/")

    tools = [
        # ----------------------------------------------------------------
        # Core synthesize endpoints
        # ----------------------------------------------------------------
        {
            "name": "tts_status",
            "description": (
                "Return current status, supported languages, and configuration "
                "of the running TTS engine."
            ),
            "inputs": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "outputs": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "plugin": {"type": "string"},
                    "langs": {"type": "array", "items": {"type": "string"}},
                    "default_lang": {"type": "string"},
                    "default_model": {"type": ["string", "null"]},
                    "default_voice": {"type": ["string", "null"]},
                },
            },
            "tags": ["tts", "status"],
            "tool_call_template": {
                "call_template_type": "http",
                "url": f"{base_url}/status",
                "http_method": "GET",
            },
        },
        {
            "name": "tts_synthesize_v2",
            "description": (
                "Synthesize speech from text (OVOS v2 endpoint). "
                "Returns a WAV audio file. "
                "Pass 'voice' and/or 'lang' as optional query parameters."
            ),
            "inputs": {
                "type": "object",
                "properties": {
                    "utterance": {
                        "type": "string",
                        "description": "Text to synthesize (required).",
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice identifier (optional).",
                    },
                    "lang": {
                        "type": "string",
                        "description": "BCP-47 language code, e.g. 'en-us' (optional).",
                    },
                },
                "required": ["utterance"],
            },
            "outputs": {
                "type": "string",
                "description": "Raw WAV audio bytes (audio/wav).",
                "format": "binary",
            },
            "tags": ["tts", "synthesize"],
            "tool_call_template": {
                "call_template_type": "http",
                "url": f"{base_url}/v2/synthesize",
                "http_method": "GET",
                "content_type": "application/octet-stream",
            },
        },
        {
            "name": "tts_synthesize_legacy",
            "description": (
                "Synthesize speech from text (OVOS legacy endpoint). "
                "Text is embedded in the URL path. "
                "Returns a WAV audio file."
            ),
            "inputs": {
                "type": "object",
                "properties": {
                    "utterance": {
                        "type": "string",
                        "description": "Text to synthesize (URL path segment).",
                    },
                    "voice": {"type": "string", "description": "Voice identifier (optional)."},
                    "lang": {"type": "string", "description": "Language code (optional)."},
                },
                "required": ["utterance"],
            },
            "outputs": {
                "type": "string",
                "description": "Raw WAV audio bytes (audio/wav).",
                "format": "binary",
            },
            "tags": ["tts", "synthesize", "legacy"],
            "tool_call_template": {
                "call_template_type": "http",
                "url": f"{base_url}/synthesize/{{utterance}}",
                "http_method": "GET",
            },
        },
    ]

    return {
        "utcp_version": _UTCP_VERSION,
        "manual_version": _MANUAL_VERSION,
        "tools": tools,
    }


def make_utcp_router(engine: "TTSEngineWrapper"):
    """Return a FastAPI router that serves GET /utcp.

    The ``base_url`` is resolved at request time from the incoming
    ``Request`` object so the manual works behind any proxy or port.

    Args:
        engine: The live TTSEngineWrapper (used for metadata).

    Returns:
        A ``fastapi.APIRouter`` with a single ``GET /utcp`` route.
    """
    router = APIRouter(tags=["utcp"])

    @router.get("/utcp", summary="UTCP manual — agent tool discovery")
    async def utcp_manual(request: Request) -> JSONResponse:
        """Return a UTCPManual JSON document describing all TTS endpoints.

        UTCP-aware agents can point at this URL to auto-discover every
        synthesis endpoint exposed by this server.
        """
        # Reconstruct the base URL from the incoming request.
        base = str(request.base_url).rstrip("/")
        manual = build_utcp_manual(engine, base)
        return JSONResponse(content=manual)

    return router
