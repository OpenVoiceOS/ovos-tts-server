# Licensed under the Apache License, Version 2.0
"""Unit tests for the optional MCP server module.

The ``mcp`` package is mocked throughout so these tests run without it
being installed.
"""
import base64
import sys
import types
import wave
import tempfile
from typing import List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeEngine:
    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us"]
    voices: List[str] = []

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)
        return tmp.name, None


# ---------------------------------------------------------------------------
# Fake mcp module
# ---------------------------------------------------------------------------

def _make_fake_mcp_module():
    """Build a minimal sys.modules stub for the ``mcp`` package.

    We need ``mcp.server.fastmcp.FastMCP`` to behave like the real thing:
    - accepts ``name`` and ``instructions`` kwargs
    - exposes a ``.tool()`` decorator that registers callables
    - exposes an ``.asgi_app()`` method that returns an ASGI app stub
    """

    registered_tools = {}

    class _FakeFastMCP:
        def __init__(self, name=None, instructions=None, **kwargs):
            self.name = name
            self.instructions = instructions
            self._tools = registered_tools

        def tool(self, name=None, description=None):
            """Decorator that captures the callable under its name."""
            def decorator(fn):
                tool_name = name or fn.__name__
                self._tools[tool_name] = fn
                return fn
            return decorator

        def asgi_app(self):
            """Return a minimal ASGI callable so app.mount() succeeds."""
            async def _asgi(scope, receive, send):  # pragma: no cover
                pass
            return _asgi

    # Build fake module tree
    mcp_mod = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = _FakeFastMCP

    mcp_mod.server = server_mod
    server_mod.fastmcp = fastmcp_mod

    return mcp_mod, server_mod, fastmcp_mod, registered_tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    return FakeEngine()


@pytest.fixture()
def fake_mcp_modules():
    mcp_mod, server_mod, fastmcp_mod, tools = _make_fake_mcp_module()
    with patch.dict(sys.modules, {
        "mcp": mcp_mod,
        "mcp.server": server_mod,
        "mcp.server.fastmcp": fastmcp_mod,
    }):
        # Re-import the module under test so it picks up the fake mcp
        import importlib
        import ovos_tts_server.mcp_server as mcp_server_mod
        importlib.reload(mcp_server_mod)
        yield mcp_server_mod, tools
        # Restore original module state
        importlib.reload(mcp_server_mod)


# ---------------------------------------------------------------------------
# _build_mcp tests
# ---------------------------------------------------------------------------

class TestBuildMcp:
    def test_build_registers_synthesize_tool(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        assert "synthesize" in tools, "Expected 'synthesize' tool to be registered"

    def test_synthesize_returns_expected_keys(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello world")
        assert "mime_type" in result
        assert "data" in result
        assert "path" in result
        assert "phonemes" in result

    def test_synthesize_mime_type_is_wav(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello")
        assert result["mime_type"] == "audio/wav"

    def test_synthesize_data_is_valid_base64(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello")
        decoded = base64.b64decode(result["data"])
        assert len(decoded) > 0

    def test_synthesize_with_voice_param(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello", voice="voice1")
        assert result["mime_type"] == "audio/wav"

    def test_synthesize_with_lang_param(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello", lang="de-de")
        assert result["mime_type"] == "audio/wav"

    def test_synthesize_empty_text_raises(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        with pytest.raises(ValueError, match="non-empty"):
            tools["synthesize"](text="")

    def test_synthesize_whitespace_text_raises(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        with pytest.raises(ValueError, match="non-empty"):
            tools["synthesize"](text="   ")

    def test_build_raises_import_error_when_mcp_missing(self, engine):
        """_build_mcp should raise ImportError when mcp is not installed."""
        with patch.dict(sys.modules, {"mcp": None, "mcp.server": None, "mcp.server.fastmcp": None}):
            import importlib
            import ovos_tts_server.mcp_server as mcp_server_mod
            importlib.reload(mcp_server_mod)
            with pytest.raises(ImportError, match="mcp"):
                mcp_server_mod._build_mcp(engine)
            importlib.reload(mcp_server_mod)


# ---------------------------------------------------------------------------
# mount_mcp tests
# ---------------------------------------------------------------------------

class TestMountMcp:
    def test_mount_mcp_adds_route(self, engine, fake_mcp_modules):
        mcp_server_mod, _ = fake_mcp_modules
        app = FastAPI()
        mcp_server_mod.mount_mcp(app, engine, path="/mcp")
        # After mount, the app should have routes including /mcp
        route_paths = [str(r.path) for r in app.routes]
        assert any("/mcp" in p for p in route_paths), (
            f"Expected /mcp in routes; got: {route_paths}"
        )

    def test_mount_mcp_no_op_when_mcp_missing(self, engine):
        """mount_mcp should not raise when mcp is not installed."""
        with patch.dict(sys.modules, {"mcp": None, "mcp.server": None, "mcp.server.fastmcp": None}):
            import importlib
            import ovos_tts_server.mcp_server as mcp_server_mod
            importlib.reload(mcp_server_mod)
            app = FastAPI()
            # Should not raise
            mcp_server_mod.mount_mcp(app, engine)
            importlib.reload(mcp_server_mod)


# ---------------------------------------------------------------------------
# start_tts_server integration: enable_mcp flag
# ---------------------------------------------------------------------------

class TestStartTtsServerMcpFlag:
    def test_enable_mcp_false_does_not_mount(self):
        """start_tts_server with enable_mcp=False should not call mount_mcp."""
        with patch("ovos_tts_server.TTSEngineWrapper") as MockEngine, \
             patch("ovos_tts_server.create_app") as mock_create_app, \
             patch("ovos_tts_server.mcp_server.mount_mcp") as mock_mount:
            MockEngine.return_value = MagicMock()
            mock_create_app.return_value = FastAPI()
            from ovos_tts_server import start_tts_server
            start_tts_server("fake-plugin", enable_mcp=False)
            mock_mount.assert_not_called()

    def test_enable_mcp_true_calls_mount(self, fake_mcp_modules):
        # start_tts_server does a late import: from ovos_tts_server.mcp_server import mount_mcp
        # Patch it at the source module so the late import picks up the mock.
        with patch("ovos_tts_server.TTSEngineWrapper") as MockEngine, \
             patch("ovos_tts_server.create_app") as mock_create_app, \
             patch("ovos_tts_server.mcp_server.mount_mcp") as mock_mount:
            MockEngine.return_value = MagicMock()
            mock_create_app.return_value = FastAPI()
            import ovos_tts_server as tts_mod
            tts_mod.start_tts_server("fake-plugin", enable_mcp=True)
            mock_mount.assert_called_once()
