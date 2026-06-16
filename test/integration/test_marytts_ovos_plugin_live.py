"""Live test: drive `ovos-tts-plugin-marytts` against our /marytts router.

The plugin is a real OVOS TTS plugin that talks to a real MaryTTS HTTP
server. Pointing its `url` config at our compat router proves we're a
genuine drop-in for upstream MaryTTS — voice discovery + synthesis both
have to round-trip through our endpoints exactly as the plugin expects.
"""
import wave

import pytest

from test.integration.conftest import run_live_server


@pytest.fixture(scope="module")
def base_url():
    from ovos_tts_server.routers.marytts import (
        make_marytts_router,
        make_marytts_root_router,
    )

    def register(app, engine):
        app.include_router(make_marytts_router(engine))
        app.include_router(make_marytts_root_router(engine))

    yield from run_live_server(register)


def test_marytts_plugin_voice_discovery(base_url):
    """The plugin GETs /voices at init and parses 'voice lang gender plugin' lines."""
    from ovos_tts_plugin_marytts import MaryTTS

    tts = MaryTTS({"url": f"{base_url}/marytts"})
    # FakeEngine advertises langs=["en-us","de-de"] and voices=["voice1","voice2"]
    # — the plugin should have discovered them.
    assert "voice1" in tts.valid_voices
    assert "voice2" in tts.valid_voices
    assert tts.valid_langs  # at least one supported language


def test_marytts_plugin_synthesizes_via_compat_router(base_url, tmp_path):
    """End-to-end: plugin renders a sentence to a WAV file via our /process."""
    from ovos_tts_plugin_marytts import MaryTTS

    tts = MaryTTS({"url": f"{base_url}/marytts", "voice": "voice1"})
    out_path = tmp_path / "marytts.wav"
    result_path, phonemes = tts.get_tts(
        "hello world",
        str(out_path),
        lang="en-us",
        voice="voice1",
    )
    assert result_path == str(out_path)
    assert out_path.exists()
    # The fake engine writes a real WAV; the plugin shouldn't have mangled it.
    with wave.open(str(out_path)) as wf:
        assert wf.getframerate() == 16000
        assert wf.getnchannels() == 1


def test_marytts_plugin_against_root_aliases(base_url, tmp_path):
    """Legacy MaryTTS clients hardcode bare /process and /voices.

    Our root-alias router covers those — point the plugin at the bare host
    and it should work the same way.
    """
    from ovos_tts_plugin_marytts import MaryTTS

    tts = MaryTTS({"url": base_url, "voice": "voice1"})
    assert "voice1" in tts.valid_voices
    out_path = tmp_path / "marytts_root.wav"
    tts.get_tts("hello", str(out_path), lang="en-us", voice="voice1")
    assert out_path.exists()
