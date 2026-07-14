# Licensed under the Apache License, Version 2.0
"""Unit tests for the Azure WebSocket synthesis bridge."""
import json
import struct
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeEngine:
    plugin_name: str = "fake-tts"
    lang: str = "en-us"
    langs: List[str] = ["en-us", "de-de"]
    voices: List[str] = ["voice1", "voice2"]

    def __init__(self):
        self.last_call: Optional[Tuple[str, dict]] = None

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        self.last_call = (utterance, kwargs)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 1600)
        return tmp.name, None


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def client(engine):
    from ovos_tts_server.routers.azure_ws import make_azure_ws_router
    app = FastAPI()
    app.include_router(make_azure_ws_router(engine))
    return TestClient(app)


def _text_msg(path: str, request_id: str, body: str,
              content_type: str = "application/json; charset=utf-8") -> str:
    return (
        f"X-RequestId:{request_id}\r\n"
        f"Path:{path}\r\n"
        f"Content-Type:{content_type}\r\n"
        f"X-Timestamp:2026-05-15T00:00:00.000Z\r\n"
        f"\r\n"
        f"{body}"
    )


def _parse_text(msg: str):
    head, _, body = msg.partition("\r\n\r\n")
    headers = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in headers.items()}, body


def _parse_binary(data: bytes):
    hl = struct.unpack(">H", data[:2])[0]
    head = data[2:2 + hl].decode("utf-8")
    headers = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in headers.items()}, data[2 + hl:]


class TestAzureWebSocketBridge:
    SSML = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="en-US"><voice name="voice1">hello world</voice></speak>'
    )

    def test_full_synthesis_turn(self, client, engine):
        request_id = "abc123def456"
        with client.websocket_connect(
            "/azure-tts/cognitiveservices/websocket/v1",
        ) as ws:
            ws.send_text(_text_msg("speech.config", request_id, "{}"))
            ws.send_text(_text_msg(
                "synthesis.context", request_id,
                json.dumps({
                    "synthesis": {
                        "audio": {"outputFormat": "riff-16khz-16bit-mono-pcm"}
                    }
                }),
            ))
            ws.send_text(_text_msg(
                "ssml", request_id, self.SSML,
                content_type="application/ssml+xml",
            ))

            turn_start = ws.receive_text()
            headers, _ = _parse_text(turn_start)
            assert headers["Path"] == "turn.start"
            assert headers["X-RequestId"] == request_id

            response_msg = ws.receive_text()
            headers, _ = _parse_text(response_msg)
            assert headers["Path"] == "response"

            audio_msg = ws.receive_bytes()
            headers, audio = _parse_binary(audio_msg)
            assert headers["Path"] == "audio"
            assert headers["X-RequestId"] == request_id
            # Output format was riff/wav — content should start with RIFF
            assert audio.startswith(b"RIFF")
            assert len(audio) > 16

            turn_end = ws.receive_text()
            headers, _ = _parse_text(turn_end)
            assert headers["Path"] == "turn.end"

        # SSML voice and lang extracted from the body
        assert engine.last_call[0] == "hello world"
        assert engine.last_call[1]["voice"] == "voice1"
        assert engine.last_call[1]["lang"] == "en-US"

    def test_skips_unknown_messages(self, client, engine):
        with client.websocket_connect(
            "/azure-tts/cognitiveservices/websocket/v1",
        ) as ws:
            ws.send_text(_text_msg("something.unknown", "x", "{}"))
            ws.send_text(_text_msg(
                "ssml", "x", "<speak>hi</speak>",
                content_type="application/ssml+xml",
            ))
            # Should still get a full turn for the ssml
            assert _parse_text(ws.receive_text())[0]["Path"] == "turn.start"
            assert _parse_text(ws.receive_text())[0]["Path"] == "response"
            assert _parse_binary(ws.receive_bytes())[0]["Path"] == "audio"
            assert _parse_text(ws.receive_text())[0]["Path"] == "turn.end"

    def test_supports_multiple_turns_per_connection(self, client):
        with client.websocket_connect(
            "/azure-tts/cognitiveservices/websocket/v1",
        ) as ws:
            for i in range(3):
                ws.send_text(_text_msg(
                    "ssml", f"req-{i}",
                    f"<speak>turn {i}</speak>",
                    content_type="application/ssml+xml",
                ))
                assert _parse_text(ws.receive_text())[0]["Path"] == "turn.start"
                assert _parse_text(ws.receive_text())[0]["Path"] == "response"
                hdr, _ = _parse_binary(ws.receive_bytes())
                assert hdr["X-RequestId"] == f"req-{i}"
                assert _parse_text(ws.receive_text())[0]["Path"] == "turn.end"
