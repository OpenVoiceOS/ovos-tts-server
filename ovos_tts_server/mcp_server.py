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
"""Optional MCP server for ovos-tts-server.

Exposes a ``synthesize`` tool via the Model Context Protocol (FastMCP).
The MCP server is mounted on the existing FastAPI app at ``/mcp`` using
streamable HTTP transport (SSE-compatible).

Install the extra dependency to enable:

    pip install "ovos-tts-server[mcp]"

Then mount it onto your app before passing it to uvicorn:

    from ovos_tts_server.mcp_server import mount_mcp
    app, engine = start_tts_server(plugin_name)
    mount_mcp(app, engine)
"""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fastapi import FastAPI
    from ovos_tts_server import TTSEngineWrapper


def _build_mcp(engine: "TTSEngineWrapper"):
    """Build and return a FastMCP instance wired to *engine*.

    Raises ImportError if the ``mcp`` package is not installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "MCP support requires the 'mcp' package: "
            "pip install \"ovos-tts-server[mcp]\""
        ) from exc

    mcp = FastMCP(
        name="ovos-tts-server",
        instructions=(
            "Synthesize speech using the OVOS TTS server. "
            "Call the 'synthesize' tool with the text you want spoken."
        ),
    )

    @mcp.tool(
        name="synthesize",
        description=(
            "Convert text to speech using the configured OVOS TTS engine. "
            "Returns base64-encoded WAV audio with MIME type audio/wav."
        ),
    )
    def synthesize(
        text: str,
        voice: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> dict:
        """Synthesize *text* and return the audio as a base64 artifact.

        Args:
            text: The text to synthesize (required, non-empty).
            voice: Optional voice/speaker identifier supported by the engine.
            lang: Optional BCP-47 language code (e.g. ``"en-us"``).

        Returns:
            A dict with keys:
            - ``mime_type``: always ``"audio/wav"``
            - ``data``: base64-encoded WAV bytes
            - ``path``: absolute path to the temporary WAV file on the server
            - ``phonemes``: phoneme string returned by the engine, or null
        """
        if not text or not text.strip():
            raise ValueError("'text' must be a non-empty string")

        kwargs = {}
        if voice:
            kwargs["voice"] = voice
        if lang:
            kwargs["lang"] = lang

        audio_path, phonemes = engine.synthesize(text, **kwargs)

        with open(audio_path, "rb") as fh:
            audio_bytes = fh.read()

        return {
            "mime_type": "audio/wav",
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "path": str(audio_path),
            "phonemes": phonemes,
        }

    return mcp


def mount_mcp(app: "FastAPI", engine: "TTSEngineWrapper", path: str = "/mcp") -> None:
    """Mount the FastMCP ASGI app onto *app* at *path*.

    This is a no-op (with a logged warning) when the ``mcp`` package is not
    installed, so servers that omit the ``[mcp]`` extra still start cleanly.

    Args:
        app: The FastAPI application to mount onto.
        engine: The live TTSEngineWrapper used for synthesis.
        path: URL prefix for the MCP server (default ``"/mcp"``).
    """
    try:
        mcp = _build_mcp(engine)
        # FastMCP exposes an ASGI app via .asgi_app() or .get_asgi_app()
        # depending on the mcp version; try both.
        if hasattr(mcp, "asgi_app"):
            asgi = mcp.asgi_app()
        elif hasattr(mcp, "get_asgi_app"):
            asgi = mcp.get_asgi_app()
        else:
            # Fallback: FastMCP itself may be ASGI-compatible directly
            asgi = mcp
        app.mount(path, asgi)
    except ImportError:
        try:
            from ovos_utils.log import LOG
            LOG.warning(
                "ovos-tts-server: MCP support not available — "
                "install with: pip install \"ovos-tts-server[mcp]\""
            )
        except ImportError:
            pass
