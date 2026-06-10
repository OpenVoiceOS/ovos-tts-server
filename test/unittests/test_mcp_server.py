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

    def test_enable_mcp_default_is_off(self):
        """start_tts_server enable_mcp defaults to False — mount_mcp must not be called."""
        with patch("ovos_tts_server.TTSEngineWrapper") as MockEngine, \
             patch("ovos_tts_server.create_app") as mock_create_app, \
             patch("ovos_tts_server.mcp_server.mount_mcp") as mock_mount:
            MockEngine.return_value = MagicMock()
            mock_create_app.return_value = FastAPI()
            import ovos_tts_server as tts_mod
            tts_mod.start_tts_server("fake-plugin")  # no enable_mcp kwarg
            mock_mount.assert_not_called()


# ---------------------------------------------------------------------------
# mount_mcp ASGI version-fallback chain
# ---------------------------------------------------------------------------

class TestMountMcpFallbackChain:
    """Cover the three arms of the asgi_app / get_asgi_app / direct-mcp fallback."""

    def _make_fake_mcp_with_attrs(self, has_asgi_app: bool, has_get_asgi_app: bool):
        """Return a fake mcp module whose FastMCP exposes selected ASGI methods."""
        class _FakeFastMCP:
            def __init__(self, **kwargs):
                pass

            def tool(self, name=None, description=None):
                def decorator(fn):
                    return fn
                return decorator

            if has_asgi_app:
                def asgi_app(self):
                    async def _app(scope, receive, send):  # pragma: no cover
                        pass
                    return _app

            if has_get_asgi_app:
                def get_asgi_app(self):
                    async def _app(scope, receive, send):  # pragma: no cover
                        pass
                    return _app

        mcp_mod = types.ModuleType("mcp")
        server_mod = types.ModuleType("mcp.server")
        fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
        fastmcp_mod.FastMCP = _FakeFastMCP
        mcp_mod.server = server_mod
        server_mod.fastmcp = fastmcp_mod
        return mcp_mod, server_mod, fastmcp_mod

    def test_get_asgi_app_fallback(self, engine):
        """When only get_asgi_app is present, that arm is taken (lines 130-131)."""
        import importlib
        mcp_mod, server_mod, fastmcp_mod = self._make_fake_mcp_with_attrs(
            has_asgi_app=False, has_get_asgi_app=True
        )
        with patch.dict(sys.modules, {
            "mcp": mcp_mod,
            "mcp.server": server_mod,
            "mcp.server.fastmcp": fastmcp_mod,
        }):
            import ovos_tts_server.mcp_server as mcp_server_mod
            importlib.reload(mcp_server_mod)
            try:
                app = FastAPI()
                mcp_server_mod.mount_mcp(app, engine)
                route_paths = [str(r.path) for r in app.routes]
                assert any("/mcp" in p for p in route_paths)
            finally:
                importlib.reload(mcp_server_mod)

    def test_direct_mcp_fallback(self, engine):
        """When neither asgi_app nor get_asgi_app exist, mcp itself is mounted (lines 132-134)."""
        import importlib
        mcp_mod, server_mod, fastmcp_mod = self._make_fake_mcp_with_attrs(
            has_asgi_app=False, has_get_asgi_app=False
        )
        with patch.dict(sys.modules, {
            "mcp": mcp_mod,
            "mcp.server": server_mod,
            "mcp.server.fastmcp": fastmcp_mod,
        }):
            import ovos_tts_server.mcp_server as mcp_server_mod
            importlib.reload(mcp_server_mod)
            try:
                app = FastAPI()
                mcp_server_mod.mount_mcp(app, engine)
                route_paths = [str(r.path) for r in app.routes]
                assert any("/mcp" in p for p in route_paths)
            finally:
                importlib.reload(mcp_server_mod)

    def test_import_error_no_ovos_utils(self, engine):
        """mount_mcp ImportError handler silently passes when ovos_utils is also missing (lines 143-144)."""
        import importlib
        with patch.dict(sys.modules, {
            "mcp": None,
            "mcp.server": None,
            "mcp.server.fastmcp": None,
            "ovos_utils": None,
            "ovos_utils.log": None,
        }):
            import ovos_tts_server.mcp_server as mcp_server_mod
            importlib.reload(mcp_server_mod)
            try:
                app = FastAPI()
                mcp_server_mod.mount_mcp(app, engine)  # must not raise
                # No routes added — silent no-op
                route_paths = [str(r.path) for r in app.routes]
                assert not any("/mcp" in p for p in route_paths)
            finally:
                importlib.reload(mcp_server_mod)


# ---------------------------------------------------------------------------
# synthesize tool: edge cases and output integrity
# ---------------------------------------------------------------------------

class TestSynthesizeEdgeCases:
    def test_very_long_text(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        long_text = "word " * 2000
        result = tools["synthesize"](text=long_text)
        assert result["mime_type"] == "audio/wav"
        decoded = base64.b64decode(result["data"])
        assert len(decoded) > 0

    def test_base64_output_decodes_to_wav_header(self, engine, fake_mcp_modules):
        """Decoded base64 data must start with the RIFF WAV magic bytes."""
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="check wav header")
        decoded = base64.b64decode(result["data"])
        assert decoded[:4] == b"RIFF", (
            f"Expected WAV RIFF header, got: {decoded[:4]!r}"
        )

    def test_unknown_voice_forwarded_to_engine(self, engine, fake_mcp_modules):
        """Passing an unknown voice should not raise — FakeEngine ignores extra kwargs."""
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello", voice="nonexistent-voice")
        assert result["mime_type"] == "audio/wav"

    def test_unknown_lang_forwarded_to_engine(self, engine, fake_mcp_modules):
        """Passing an unknown lang should not raise — FakeEngine ignores extra kwargs."""
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="hello", lang="xx-yy")
        assert result["mime_type"] == "audio/wav"

    def test_phonemes_field_is_none_when_engine_returns_none(self, engine, fake_mcp_modules):
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="phoneme check")
        assert result["phonemes"] is None

    def test_path_field_points_to_existing_file(self, engine, fake_mcp_modules):
        import os
        mcp_server_mod, tools = fake_mcp_modules
        mcp_server_mod._build_mcp(engine)
        result = tools["synthesize"](text="path check")
        assert os.path.isfile(result["path"]), f"Expected file at {result['path']!r}"


# ---------------------------------------------------------------------------
# CLI --mcp flag
# ---------------------------------------------------------------------------

class TestCliMcpFlag:
    def test_mcp_flag_passed_to_start_tts_server(self):
        """Passing --mcp on the CLI should call start_tts_server with enable_mcp=True."""
        import sys
        import importlib
        with patch("ovos_tts_server.start_tts_server") as mock_start, \
             patch("uvicorn.run"):
            mock_start.return_value = (FastAPI(), MagicMock())
            with patch.object(sys, "argv", ["ovos-tts-server", "--engine", "fake", "--mcp"]):
                import ovos_tts_server.__main__ as main_mod
                importlib.reload(main_mod)
                main_mod.main()
            call_kwargs = mock_start.call_args
            # enable_mcp should be True
            assert call_kwargs is not None
            assert call_kwargs.kwargs.get("enable_mcp") is True or \
                   (len(call_kwargs.args) > 1 and call_kwargs.args[2] is True), \
                   f"enable_mcp not True in call: {call_kwargs}"

    def test_no_mcp_flag_passes_false(self):
        """Without --mcp, enable_mcp must be False."""
        import sys
        import importlib
        with patch("ovos_tts_server.start_tts_server") as mock_start, \
             patch("uvicorn.run"):
            mock_start.return_value = (FastAPI(), MagicMock())
            with patch.object(sys, "argv", ["ovos-tts-server", "--engine", "fake"]):
                import ovos_tts_server.__main__ as main_mod
                importlib.reload(main_mod)
                main_mod.main()
            call_kwargs = mock_start.call_args
            assert call_kwargs is not None
            enable_mcp_val = call_kwargs.kwargs.get("enable_mcp", False)
            assert enable_mcp_val is False, f"Expected enable_mcp=False, got {enable_mcp_val}"
