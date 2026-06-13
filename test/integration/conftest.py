"""Shared fixtures for integration tests.

Each integration test runs the compat router(s) behind a real uvicorn
server on a random local port, then drives it with the vendor's official
SDK to prove drop-in compatibility.

Tests skip automatically when the vendor SDK isn't installed; install
them with `pip install -e .[live]`.
"""
import socket
import tempfile
import threading
import time
import wave
from typing import List, Optional, Tuple

import pytest


class FakeEngine:
    """Stand-in for TTSEngineWrapper; produces a valid silent WAV."""

    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 1600)
        return tmp.name, None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_live_server(register):
    """Yield a base URL for a uvicorn server that ran `register(app, engine)`.

    `register` is a callable that takes (FastAPI app, FakeEngine) and mounts
    the compat router under test.
    """
    import uvicorn
    from fastapi import FastAPI

    engine = FakeEngine()
    app = FastAPI()
    register(app, engine)

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for startup (uvicorn sets .started after the lifespan handshake)
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("uvicorn live server failed to start")

    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)
