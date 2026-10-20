"""MaryTTS clients send Java locales (en_US); OVOS engines list BCP-47 tags (en-us)."""
import tempfile
import wave
from typing import List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ovos_tts_server.routers.marytts import make_marytts_router


class StrictLangEngine:
    """Engine stub that, like espeak-ng, writes no file for a language it does not know."""

    plugin_name = "strict-tts"
    lang = "en-us"
    langs: List[str] = ["en-us", "en-gb", "en", "pt", "ca-va"]
    voices: List[str] = ["default"]

    def __init__(self):
        self.langs_received: List[str] = []

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        lang = kwargs.get("lang", self.lang)
        self.langs_received.append(lang)
        path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        if lang.lower() not in self.langs:
            return path + ".missing", None
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)
        return path, None


@pytest.fixture
def engine() -> StrictLangEngine:
    return StrictLangEngine()


@pytest.fixture
def client(engine) -> TestClient:
    app = FastAPI()
    app.include_router(make_marytts_router(engine))
    return TestClient(app)


def test_locales_are_listed_as_java_locales(client):
    assert client.get("/marytts/locales").text.splitlines() == ["en_US", "en_GB", "en", "pt", "ca_VA"]


def test_voices_list_java_locales(client):
    lines = client.get("/marytts/voices").text.splitlines()
    assert "default en_US m strict-tts" in lines
    assert all(line.split()[1] != "en-us" for line in lines)


@pytest.mark.parametrize("locale, engine_lang", [
    ("en_US", "en-us"),
    ("en_us", "en-us"),
    ("EN-US", "en-us"),
    ("en_GB", "en-gb"),
    ("en_AU", "en-gb"),  # region the engine lacks: the nearest variant
    ("pt_PT", "pt"),
    ("pt_BR", "pt"),
    ("ca_VA", "ca-va"),
])
def test_process_sends_the_engine_its_own_tag(client, engine, locale, engine_lang):
    r = client.get("/marytts/process", params={"INPUT_TEXT": "hello", "LOCALE": locale})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "audio/wav"
    assert engine.langs_received == [engine_lang]


def test_process_without_audio_names_the_cause(client):
    r = client.get("/marytts/process", params={"INPUT_TEXT": "hello", "LOCALE": "xx_YY"})
    assert r.status_code == 500
    assert "produced no audio" in r.json()["detail"]


def test_locale_round_trips_through_the_listing():
    from ovos_tts_server.routers.marytts import resolve_locale, to_mary_locale
    langs = StrictLangEngine.langs
    assert [resolve_locale(to_mary_locale(lang), langs) for lang in langs] == langs


@pytest.mark.parametrize("locale, engine_lang", [
    ("EN_us", "en-us"),
    ("en-AU", "en-gb"),   # no bare "en" listed: the nearest regional variant
    ("pt", "pt-br"),      # bare language, regional engine tag
    ("pt_PT", "pt-br"),
    ("de_DE", "de"),
])
def test_process_matches_regional_variants(engine, locale, engine_lang):
    engine.langs = ["en-us", "en-gb", "pt-br", "de"]
    app = FastAPI()
    app.include_router(make_marytts_router(engine))
    r = TestClient(app).get("/marytts/process", params={"INPUT_TEXT": "hello", "LOCALE": locale})
    assert r.status_code == 200, r.text
    assert engine.langs_received == [engine_lang]
