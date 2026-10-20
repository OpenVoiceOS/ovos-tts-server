"""DescribeVoices on the /amazon-polly router, with an engine that lists bare languages."""
from typing import List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router


class BareLangEngine:
    """Lists languages without a region, as ovos-tts-plugin-espeakng does."""

    lang: str = "en-us"
    langs: List[str] = ["en-us", "de", "pt"]
    voices: List[str] = ["m1"]


def _voice_ids(**params):
    app = FastAPI()
    app.include_router(make_amazon_polly_router(BareLangEngine()))
    r = TestClient(app).get("/amazon-polly/v1/voices", params=params)
    assert r.status_code == 200
    return [v["Id"] for v in r.json()["Voices"]]


def test_bare_listed_language_matches_regional_request():
    assert _voice_ids(LanguageCode="de-DE", IncludeAdditionalLanguageCodes="true") == ["m1"]
    assert _voice_ids(LanguageCode="pt-PT", IncludeAdditionalLanguageCodes="true") == ["m1"]


def test_bare_listed_language_still_needs_the_additional_flag():
    assert _voice_ids(LanguageCode="de-DE") == []


def test_unlisted_language_and_other_region_do_not_match():
    assert _voice_ids(LanguageCode="fr-FR", IncludeAdditionalLanguageCodes="true") == []
    assert _voice_ids(LanguageCode="en-GB", IncludeAdditionalLanguageCodes="true") == []


def test_language_tags_use_bcp47_case():
    from ovos_tts_server.routers.amazon_polly import _polly_lang

    assert _polly_lang("en-us") == "en-US"
    assert _polly_lang("EN_us") == "en-US"
    assert _polly_lang("sr-latn") == "sr-Latn"
    assert _polly_lang("sr-LATN-rs") == "sr-Latn-RS"
    assert _polly_lang("es-419") == "es-419"
    assert _polly_lang("cmn-cn") == "cmn-CN"
    assert _polly_lang("arb") == "arb"


def test_subtags_after_a_singleton_are_lowercase():
    """RFC 5646 section 2.1.1: subtags after a singleton keep lowercase."""
    from ovos_tts_server.routers.amazon_polly import _polly_lang

    assert _polly_lang("en-ca-x-ca") == "en-CA-x-ca"
    assert _polly_lang("az-latn-x-latn") == "az-Latn-x-latn"
    assert _polly_lang("de-U-CO-phonebk") == "de-u-co-phonebk"
    assert _polly_lang("EN-US-U-CA-GREGORY") == "en-US-u-ca-gregory"


def test_polly_codes_keep_polly_case():
    """Polly lists en-GB-WLS, which is not BCP-47 case; it is echoed as Polly spells it."""
    from ovos_tts_server.routers.amazon_polly import _polly_lang

    assert _polly_lang("en-gb-wls") == "en-GB-WLS"
    assert _polly_lang("EN-GB-WLS") == "en-GB-WLS"
