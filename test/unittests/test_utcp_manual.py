# Licensed under the Apache License, Version 2.0
"""Unit tests for the UTCP manual endpoint.

All tests use a FakeEngine so no real OVOS plugin is loaded.
"""
import wave
import tempfile
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ovos_tts_server.utcp_manual import build_utcp_manual, make_utcp_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeEngine:
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
            wf.writeframes(b"\x00\x00" * 100)
        return tmp.name, None


@pytest.fixture(scope="module")
def engine():
    return FakeEngine()


@pytest.fixture(scope="module")
def client(engine):
    app = FastAPI()
    app.include_router(make_utcp_router(engine))
    return TestClient(app)


# ---------------------------------------------------------------------------
# build_utcp_manual unit tests
# ---------------------------------------------------------------------------

class TestBuildUtcpManual:
    BASE = "http://localhost:9666"

    def test_top_level_keys(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        assert "utcp_version" in manual
        assert "manual_version" in manual
        assert "tools" in manual

    def test_utcp_version_format(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        parts = manual["utcp_version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_tools_is_list(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        assert isinstance(manual["tools"], list)
        assert len(manual["tools"]) > 0

    def test_all_tools_have_required_fields(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        for tool in manual["tools"]:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool '{tool['name']}' missing 'description'"
            assert "inputs" in tool, f"Tool '{tool['name']}' missing 'inputs'"
            assert "tool_call_template" in tool, f"Tool '{tool['name']}' missing 'tool_call_template'"

    def test_all_tool_names_unique(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        names = [t["name"] for t in manual["tools"]]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_tool_call_templates_have_url_and_method(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        for tool in manual["tools"]:
            tpl = tool["tool_call_template"]
            assert "url" in tpl, f"Tool '{tool['name']}' template missing 'url'"
            assert "http_method" in tpl, f"Tool '{tool['name']}' template missing 'http_method'"
            assert "call_template_type" in tpl

    def test_base_url_embedded_in_templates(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        for tool in manual["tools"]:
            url = tool["tool_call_template"]["url"]
            assert url.startswith(self.BASE), (
                f"Tool '{tool['name']}' url {url!r} does not start with {self.BASE!r}"
            )

    def test_trailing_slash_stripped_from_base(self, engine):
        manual = build_utcp_manual(engine, self.BASE + "/")
        for tool in manual["tools"]:
            url = tool["tool_call_template"]["url"]
            # The URL should not have a double-slash after the base
            assert "localhost:9666//" not in url

    def test_synthesize_v2_tool_present(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        names = {t["name"] for t in manual["tools"]}
        assert "tts_synthesize_v2" in names

    def test_synthesize_v2_utterance_required(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        tool = next(t for t in manual["tools"] if t["name"] == "tts_synthesize_v2")
        assert "utterance" in tool["inputs"]["required"]

    def test_status_tool_present(self, engine):
        manual = build_utcp_manual(engine, self.BASE)
        names = {t["name"] for t in manual["tools"]}
        assert "tts_status" in names


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestUtcpEndpoint:
    def test_get_utcp_returns_200(self, client):
        resp = client.get("/utcp")
        assert resp.status_code == 200

    def test_response_is_json(self, client):
        resp = client.get("/utcp")
        body = resp.json()
        assert isinstance(body, dict)

    def test_response_has_tools_list(self, client):
        resp = client.get("/utcp")
        body = resp.json()
        assert "tools" in body
        assert isinstance(body["tools"], list)
        assert len(body["tools"]) > 0

    def test_response_has_version_fields(self, client):
        resp = client.get("/utcp")
        body = resp.json()
        assert "utcp_version" in body
        assert "manual_version" in body

    def test_tool_urls_reflect_request_host(self, client):
        resp = client.get("/utcp")
        body = resp.json()
        # TestClient uses http://testserver by default
        for tool in body["tools"]:
            url = tool["tool_call_template"]["url"]
            assert url.startswith("http://testserver"), (
                f"Expected testserver base, got: {url}"
            )
