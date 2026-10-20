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
import base64
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
    base_url, server, thread = _start_server(app)

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def mcp_server():
    """Boot create_app with MCP mounted, as ``ovos-tts-server --mcp`` does."""
    from ovos_tts_server import create_app

    app = create_app(_StubTTSEngine(), enable_mcp=True)
    base_url, server, thread = _start_server(app)

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


    def test_json_synthesis_requires_utterance(self, live_server):
        resp = httpx.get(f"{live_server}/v2/synthesize/json", timeout=10)
        assert resp.status_code == 400
        assert resp.json() == {"error": "Missing utterance"}

    def test_reference_client_calls_every_tool(self, live_server):
        """The reference UTCP client (utcp + utcp-http) must be able to call
        every tool in the manual, and synthesis must return the audio."""
        from utcp.utcp_client import UtcpClient
        from utcp.data.utcp_client_config import UtcpClientConfig

        async def _run():
            config = UtcpClientConfig(manual_call_templates=[{
                "name": "ovos_tts",
                "call_template_type": "http",
                "url": f"{live_server}/utcp",
                "http_method": "GET",
            }])
            client = await UtcpClient.create(config=config)
            tools = await client.config.tool_repository.get_tools()
            results = {}
            for tool in tools:
                args = {"utterance": "hello"} if "utterance" in tool.inputs.required else {}
                results[tool.name] = await client.call_tool(tool.name, args)
            return results

        results = asyncio.run(_run())
        assert results["ovos_tts.tts_status"]["plugin"] == "stub-tts"
        audio = results["ovos_tts.tts_synthesize_v2"]
        assert audio["mime_type"] == "audio/wav"
        assert base64.b64decode(audio["data"]) == _wav_bytes()


# ---------------------------------------------------------------------------
# MCP end-to-end
# ---------------------------------------------------------------------------

class TestMcpE2E:
    """MCP tests call the endpoint that create_app(enable_mcp=True) mounts."""

    def test_mcp_endpoint_accessible(self, mcp_server):
        resp = httpx.get(mcp_server, timeout=10)
        assert resp.status_code != 404

    def test_mcp_list_tools(self, mcp_server):
        from mcp.client.streamable_http import streamable_http_client
        from mcp import ClientSession

        async def _run():
            async with streamable_http_client(mcp_server) as (r, w):
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
            async with streamable_http_client(mcp_server) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return await session.call_tool(
                        "synthesize",
                        {"text": "hello world", "lang": "en-us"},
                    )

        result = asyncio.run(_run())
        assert not result.is_error, result.content
        assert result.structured_content["mime_type"] == "audio/wav"
        assert base64.b64decode(result.structured_content["data"]) == _wav_bytes()

    def test_mcp_synthesize_rejects_empty_text(self, mcp_server):
        from mcp.client.streamable_http import streamable_http_client
        from mcp import ClientSession

        async def _run():
            async with streamable_http_client(mcp_server) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return await session.call_tool("synthesize", {"text": "  "})

        result = asyncio.run(_run())
        assert result.is_error
        assert "'text' must be a non-empty string" in result.content[0].text
