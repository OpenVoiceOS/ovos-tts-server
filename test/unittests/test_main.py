# Licensed under the Apache License, Version 2.0
"""Unit tests for ovos_tts_server.__main__."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from ovos_tts_server import __main__ as cli
from ovos_tts_server.version import __version__


class TestCLI:
    def test_version_is_importable(self):
        assert isinstance(__version__, str)
        assert __version__

    def test_main_starts_uvicorn_with_args(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", [
            "ovos-tts-server",
            "--engine", "fake-plugin",
            "--host", "127.0.0.1",
            "--port", "1234",
            "--cache",
        ])
        with patch("ovos_tts_server.__main__.start_tts_server") as start, \
             patch("ovos_tts_server.__main__.uvicorn") as uv:
            start.return_value = (MagicMock(name="app"), MagicMock(name="engine"))
            cli.main()
            start.assert_called_once_with("fake-plugin", cache=True, enable_mcp=False)
            uv.run.assert_called_once()
            _, kwargs = uv.run.call_args
            assert kwargs["host"] == "127.0.0.1"
            assert kwargs["port"] == 1234

    def test_main_defaults(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["ovos-tts-server", "--engine", "x"])
        with patch("ovos_tts_server.__main__.start_tts_server") as start, \
             patch("ovos_tts_server.__main__.uvicorn") as uv:
            start.return_value = (MagicMock(), MagicMock())
            cli.main()
            _, kwargs = uv.run.call_args
            assert kwargs["host"] == "0.0.0.0"
            assert kwargs["port"] == 9666
            start.assert_called_once_with("x", cache=False, enable_mcp=False)

    def test_help_exits_zero(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["ovos-tts-server", "--help"])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 0
