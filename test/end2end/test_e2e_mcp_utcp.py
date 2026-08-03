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
"""End-to-end tests for ovos-tts-server MCP /mcp and UTCP /utcp endpoints.

Boots the real FastAPI app via start_tts_server with a stub TTSEngineWrapper,
starts uvicorn on a free port in a background thread, and exercises the live
HTTP surface including the UTCP manual's advertised URLs and the MCP
initialize → list_tools → call_tool round-trip.

Run in isolation::

    pytest test/end2end/test_e2e_mcp_utcp.py -v --timeout=30
"""
from __future__ import annotations

import asyncio
import importlib
import socket
import tempfile
import threading
import time
import wave

import httpx
import pytest
import uvicorn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wav_bytes() -> bytes:
    """Return a tiny valid WAV file as bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Stub engine
# ---------------------------------------------------------------------------

class _StubTTSEngine:
    """Minimal TTSEngineWrapper lookalike — no real model required."""

    plugin_name = "stub-tts"
    lang = "en-us"
    langs = ["en-us"]
    voices = []
    engine = None  # accessed via getattr in status endpoint

    def synthesize(self, utterance: str, **kwargs):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)
        return path, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_server(app, health_path: str = "/status") -> tuple:
    """Start uvicorn via asyncio.run in a daemon thread; return (base_url, server, thread)."""
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=asyncio.run, args=(server.serve(),), daemon=True)
    thread.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{port}{health_path}", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        server.should_exit = True
        raise RuntimeError("Server did not start in time")
    return f"http://127.0.0.1:{port}", server, thread


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_server():
    """Boot create_app on a free port (UTCP tests)."""
    from ovos_tts_server import create_app

    stub = _StubTTSEngine()
    app = create_app(stub)
    try:
        base_url, server, thread = _start_server(app)
    except RuntimeError as exc:
        pytest.skip(str(exc))

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def mcp_server():
    """Run MCP as its own Starlette app to avoid sub-app lifespan issues."""
    try:
        from ovos_tts_server.mcp_server import _build_mcp
    except ImportError:
        pytest.skip("mcp extra not installed")

    stub = _StubTTSEngine()
    mcp = _build_mcp(stub)
    mcp_app = mcp.http_app(transport="streamable-http")
    try:
        base_url, server, thread = _start_server(mcp_app, health_path="/mcp")
    except RuntimeError as exc:
        pytest.skip(str(exc))

    yield f"{base_url}/mcp"

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# UTCP end-to-end
# ---------------------------------------------------------------------------

class TestUtcpE2E:
    def test_utcp_200(self, live_server):
        resp = httpx.get(f"{live_server}/utcp", timeout=10)
        assert resp.status_code == 200

    def test_utcp_has_tools(self, live_server):
        data = httpx.get(f"{live_server}/utcp", timeout=10).json()
        assert "tools" in data
        assert len(data["tools"]) >= 1

    def test_utcp_version_present(self, live_server):
        data = httpx.get(f"{live_server}/utcp", timeout=10).json()
        assert "utcp_version" in data

    def test_utcp_synthesize_tool_url_responds(self, live_server):
        """The v2/synthesize URL listed in the UTCP manual must respond."""
        data = httpx.get(f"{live_server}/utcp", timeout=10).json()
        synth_tool = next(
            (t for t in data["tools"] if "synthesize" in t["name"].lower()),
            None,
        )
        assert synth_tool is not None, "No synthesize tool in UTCP manual"
        url = synth_tool["tool_call_template"]["url"]
        resp = httpx.get(url, params={"utterance": "hello"}, timeout=15)
        assert resp.status_code == 200

    def test_utcp_status_tool_url_responds(self, live_server):
        data = httpx.get(f"{live_server}/utcp", timeout=10).json()
        # TTS server names it "tts_status"
        status_tool = next(
            (t for t in data["tools"] if "status" in t["name"]),
            None,
        )
        assert status_tool is not None, f"No status tool in {[t['name'] for t in data['tools']]}"
        url = status_tool["tool_call_template"]["url"]
        resp = httpx.get(url, timeout=10)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# MCP end-to-end
# ---------------------------------------------------------------------------

_mcp_available = importlib.util.find_spec("mcp") is not None
mcp_required = pytest.mark.skipif(
    not _mcp_available,
    reason="mcp package not installed",
)


@mcp_required
class TestMcpE2E:
    """MCP tests use a standalone MCP Starlette app (separate from the main FastAPI app)
    to avoid the Starlette Mount sub-app lifespan limitation."""

    def test_mcp_endpoint_accessible(self, mcp_server):
        resp = httpx.get(mcp_server, timeout=10)
        assert resp.status_code != 404

    def test_mcp_list_tools(self, mcp_server):
        from mcp.client.streamable_http import streamable_http_client
        from mcp import ClientSession

        async def _run():
            async with streamable_http_client(mcp_server) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [t.name for t in result.tools]

        names = asyncio.run(_run())
        assert "synthesize" in names

    def test_mcp_call_synthesize(self, mcp_server):
        """Call the synthesize tool via MCP; expect audio content back."""
        from mcp.client.streamable_http import streamable_http_client
        from mcp import ClientSession

        async def _run():
            async with streamable_http_client(mcp_server) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "synthesize",
                        {"utterance": "hello world", "lang": "en-us"},
                    )
                    return result

        result = asyncio.run(_run())
        assert result is not None
        assert result.content, "Expected non-empty content from synthesize tool"
