# Licensed under the Apache License, Version 2.0
"""Unit tests for TTSEngineWrapper and start_tts_server.

The wrapper instantiates a real OVOS TTS plugin in __init__, so we patch
load_tts_plugin and Configuration to keep the test hermetic.
"""
from unittest.mock import MagicMock, patch

from ovos_tts_server import TTSEngineWrapper, start_tts_server


def _patched_wrapper(plugin_name="fake-tts", cache=False, config_overrides=None,
                     lang=None, global_lang=None):
    """Create a TTSEngineWrapper with load_tts_plugin / Configuration mocked."""
    fake_plugin_cls = MagicMock()
    fake_engine = MagicMock()
    fake_plugin_cls.return_value = fake_engine
    fake_engine.available_languages = ["en-us", "de-de"]
    fake_engine.available_voices = ["v1", "v2"]
    fake_engine.config = {"model": "m", "voice": "v"}

    audio = MagicMock()
    audio.path = "/tmp/fake.wav"
    fake_engine.synth.return_value = (audio, "fake phonemes")
    fake_engine.validate_ssml.side_effect = lambda x: x

    cfg_dict = {"tts": {plugin_name: config_overrides or {}}}
    if global_lang is not None:
        cfg_dict["lang"] = global_lang
    cfg = MagicMock()
    cfg.get.side_effect = lambda k, d=None: cfg_dict.get(k, d)

    with patch("ovos_tts_server.load_tts_plugin", return_value=fake_plugin_cls), \
         patch("ovos_tts_server.Configuration", return_value=cfg):
        wrapper = TTSEngineWrapper(plugin_name=plugin_name, cache=cache, lang=lang)
    return wrapper, fake_engine, fake_plugin_cls


def _plugin_config(fake_plugin_cls):
    """Return the config dict the plugin was instantiated with."""
    _, kwargs = fake_plugin_cls.call_args
    return kwargs["config"]


class TestTTSEngineWrapper:
    def test_initializes_with_plugin(self):
        wrapper, engine, _ = _patched_wrapper()
        assert wrapper.plugin_name == "fake-tts"
        assert wrapper.engine is engine
        assert engine.log_timestamps is True

    def test_lang_falls_back_to_mul_when_no_config(self):
        wrapper, _, _ = _patched_wrapper(config_overrides={})
        assert wrapper.lang == "mul"

    def test_lang_from_plugin_config(self):
        wrapper, _, _ = _patched_wrapper(config_overrides={"lang": "pt-pt"})
        assert wrapper.lang == "pt-pt"

    def test_explicit_lang_reaches_plugin_and_wrapper(self):
        wrapper, _, plugin_cls = _patched_wrapper(lang="ar")
        assert wrapper.lang == "ar"
        assert _plugin_config(plugin_cls)["lang"] == "ar"

    def test_explicit_lang_overrides_configured_lang(self):
        wrapper, _, plugin_cls = _patched_wrapper(
            lang="ar", config_overrides={"lang": "pt-pt"})
        assert wrapper.lang == "ar"
        assert _plugin_config(plugin_cls)["lang"] == "ar"

    def test_configured_lang_kept_when_no_explicit_lang(self):
        wrapper, _, plugin_cls = _patched_wrapper(
            lang=None, config_overrides={"lang": "ar"})
        assert wrapper.lang == "ar"
        assert _plugin_config(plugin_cls)["lang"] == "ar"

    def test_explicit_lang_overrides_global_lang(self):
        wrapper, _, plugin_cls = _patched_wrapper(lang="ar", global_lang="pt-pt")
        assert wrapper.lang == "ar"
        assert _plugin_config(plugin_cls)["lang"] == "ar"

    def test_global_lang_used_when_no_explicit_or_plugin_lang(self):
        wrapper, _, plugin_cls = _patched_wrapper(
            lang=None, config_overrides={}, global_lang="pt-pt")
        assert wrapper.lang == "pt-pt"
        # nothing forced onto the plugin config when no explicit lang is given
        assert "lang" not in _plugin_config(plugin_cls)

    def test_no_lang_anywhere_falls_back_to_mul(self):
        wrapper, _, plugin_cls = _patched_wrapper(lang=None, config_overrides={})
        assert wrapper.lang == "mul"
        assert "lang" not in _plugin_config(plugin_cls)

    def test_cache_flag_passed_to_plugin_config(self):
        with patch("ovos_tts_server.load_tts_plugin") as load, \
             patch("ovos_tts_server.Configuration") as Cfg:
            load.return_value = MagicMock()
            Cfg.return_value.get.side_effect = lambda k, d=None: (
                {"foo": {}} if k == "tts" else d
            )
            TTSEngineWrapper(plugin_name="foo", cache=True)
            # the plugin class is called with config=...
            _, kwargs = load.return_value.call_args
            assert kwargs["config"]["persist_cache"] is True

    def test_langs_uses_engine_available_languages(self):
        wrapper, _, _ = _patched_wrapper()
        assert wrapper.langs == ["en-us", "de-de"]

    def test_langs_falls_back_to_self_lang(self):
        wrapper, engine, _ = _patched_wrapper()
        engine.available_languages = None
        assert wrapper.langs == [wrapper.lang]

    def test_voices_uses_available_voices(self):
        wrapper, _, _ = _patched_wrapper()
        assert wrapper.voices == ["v1", "v2"]

    def test_voices_empty_when_attr_missing(self):
        wrapper, engine, _ = _patched_wrapper()
        del engine.available_voices
        assert wrapper.voices == []

    def test_synthesize_returns_path_and_phonemes(self):
        wrapper, engine, _ = _patched_wrapper()
        path, phonemes = wrapper.synthesize("hello", voice="v1")
        assert path == "/tmp/fake.wav"
        assert phonemes == "fake phonemes"
        engine.validate_ssml.assert_called_once_with("hello")
        engine.synth.assert_called_once_with("hello", voice="v1")


class TestStartTTSServer:
    def test_returns_app_and_engine(self):
        with patch("ovos_tts_server.load_tts_plugin") as load, \
             patch("ovos_tts_server.Configuration") as Cfg:
            load.return_value = MagicMock()
            Cfg.return_value.get.side_effect = lambda k, d=None: (
                {"foo": {}} if k == "tts" else d
            )
            app, engine = start_tts_server("foo", cache=False)
            assert app is not None
            assert isinstance(engine, TTSEngineWrapper)
