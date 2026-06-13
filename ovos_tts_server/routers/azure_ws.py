# Licensed under the Apache License, Version 2.0
"""Azure Cognitive Services Speech — WebSocket synthesis bridge.

This implements enough of Microsoft's proprietary WebSocket TTS protocol
for the official `azure-cognitiveservices-speech` SDK's
`SpeechSynthesizer.speak_text_async()` / `speak_ssml_async()` calls to
work against this server.

Wire protocol summary
=====================

Each WebSocket message has HTTP-like headers separated from the body by
a blank line (`\\r\\n\\r\\n`):

    X-RequestId: <hex32>
    Path: <message-type>
    Content-Type: <mime>
    X-Timestamp: <iso8601>

    <body>

Text frames are sent as the raw string above. Binary frames are prefixed
with a big-endian uint16 giving the header-section byte length:

    <2 bytes: header_length>
    <header_length bytes: text headers (no body)>
    <remaining bytes: binary payload>

Synthesis flow (client → server → client):

    1. client → `speech.config` (JSON; ignored beyond logging)
    2. client → `synthesis.context` (JSON; includes audio output format)
    3. client → `ssml` (SSML body to synthesize)
    4. server → `turn.start` (JSON `{"context": {...}}`)
    5. server → `response` (JSON ack)
    6. server → `audio` (binary; WAV/MP3 bytes, possibly chunked)
    7. server → `turn.end` (empty JSON)

References:
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/websockets
- https://github.com/Azure-Samples/cognitive-services-speech-sdk
"""
from __future__ import annotations

import datetime
import json
import re
import struct
import uuid
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ovos_tts_server.audio_utils import convert_audio


# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_message(raw: str | bytes) -> Tuple[Dict[str, str], str | bytes]:
    """Split a Microsoft WS message into (headers, body)."""
    if isinstance(raw, bytes):
        header_len = struct.unpack(">H", raw[:2])[0]
        head = raw[2:2 + header_len].decode("utf-8", errors="replace")
        body = raw[2 + header_len:]
    else:
        head, _, body = raw.partition("\r\n\r\n")
    headers: Dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip()] = v.strip()
    return headers, body


def _build_text(path: str, request_id: str, body: str,
                content_type: str = "application/json; charset=utf-8") -> str:
    return (
        f"X-RequestId:{request_id}\r\n"
        f"Path:{path}\r\n"
        f"Content-Type:{content_type}\r\n"
        f"X-Timestamp:{_now_iso()}\r\n"
        f"\r\n"
        f"{body}"
    )


def _build_binary(path: str, request_id: str, payload: bytes,
                  content_type: str = "audio/x-wav") -> bytes:
    headers = (
        f"X-RequestId:{request_id}\r\n"
        f"Path:{path}\r\n"
        f"Content-Type:{content_type}\r\n"
        f"X-Timestamp:{_now_iso()}\r\n"
    ).encode("utf-8")
    return struct.pack(">H", len(headers)) + headers + payload


# ---------------------------------------------------------------------------
# SSML extraction
# ---------------------------------------------------------------------------

_VOICE_NAME_RE = re.compile(r'<voice[^>]*\bname\s*=\s*["\']([^"\']+)["\']', re.I)
_LANG_RE = re.compile(r'\bxml:lang\s*=\s*["\']([^"\']+)["\']', re.I)
_PLAINTEXT_RE = re.compile(r"<[^>]+>")


def _extract_synth_args(ssml: str) -> Tuple[str, Dict[str, str]]:
    """Return (utterance, kwargs) suitable for engine.synthesize()."""
    kwargs: Dict[str, str] = {}
    if (m := _VOICE_NAME_RE.search(ssml)):
        kwargs["voice"] = m.group(1)
    if (m := _LANG_RE.search(ssml)):
        kwargs["lang"] = m.group(1)
    utterance = _PLAINTEXT_RE.sub("", ssml).strip()
    return utterance, kwargs


def _format_from_context(ctx_json: str) -> str:
    """Map synthesis.context audio.outputFormat to audio_utils fmt."""
    try:
        ctx = json.loads(ctx_json)
    except Exception:
        return "wav"
    fmt = (
        ctx.get("synthesis", {})
           .get("audio", {})
           .get("outputFormat")
        or ""
    ).lower()
    if "mp3" in fmt:
        return "mp3"
    if "ogg" in fmt or "opus" in fmt:
        return "ogg"
    return "wav"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def make_azure_ws_router(engine) -> APIRouter:
    """Create an Azure Cognitive Services WebSocket synthesis bridge.

    Mounts at the prefixed path /azure-tts/cognitiveservices/websocket/v1
    so it coexists with the REST router on the same server.
    """
    router = APIRouter(prefix="/azure-tts", tags=["azure-ws"])

    @router.websocket("/cognitiveservices/websocket/v1")
    async def azure_synthesis(websocket: WebSocket) -> None:
        await websocket.accept()
        output_format = "wav"
        # Each connection may carry several turns; one ssml -> one audio response
        try:
            while True:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    return

                if (text := msg.get("text")) is not None:
                    headers, body = _parse_message(text)
                elif (data := msg.get("bytes")) is not None:
                    headers, body = _parse_message(data)
                else:
                    continue

                path = headers.get("Path", "").lower()
                request_id = headers.get("X-RequestId", uuid.uuid4().hex)

                if path == "speech.config":
                    # ack — Microsoft's server doesn't reply to speech.config,
                    # but tolerating its arrival keeps the SDK happy.
                    continue

                if path == "synthesis.context":
                    output_format = _format_from_context(str(body))
                    continue

                if path == "ssml":
                    ssml = str(body)
                    utterance, synth_kwargs = _extract_synth_args(ssml)
                    wav_path, _ = engine.synthesize(utterance, **synth_kwargs)
                    audio_bytes, mime = convert_audio(wav_path, output_format)

                    # turn.start
                    await websocket.send_text(_build_text(
                        "turn.start", request_id,
                        json.dumps({"context": {"serviceTag": "ovos-tts-server"}}),
                    ))
                    # response (per protocol, signals synthesis started)
                    await websocket.send_text(_build_text(
                        "response", request_id,
                        json.dumps({"audio": {"type": "inline"}}),
                    ))
                    # audio frame(s) — single chunk is sufficient for the SDK
                    await websocket.send_bytes(_build_binary(
                        "audio", request_id, audio_bytes, content_type=mime,
                    ))
                    # turn.end terminates this synthesis
                    await websocket.send_text(_build_text(
                        "turn.end", request_id, "{}",
                    ))
                    continue

                # Unknown path — ignore
        except WebSocketDisconnect:
            return
        except Exception:
            # Closing cleanly is more useful than a 1011 to the client
            try:
                await websocket.close()
            except Exception:
                pass

    return router
