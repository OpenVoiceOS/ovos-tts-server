"""Live test: drive the official PlayHT SDK (``pyht``) against our /playht router.

The router implements PlayHT's ``/api/v4/sdk-auth`` inference-coordinates
handshake, so a stock ``pyht.Client`` works once its coordinates ``api_url`` is
repointed at this server — no monkey-patching of SDK internals. We use the HTTP
protocol with ``auto_connect=False`` so the SDK never contacts play.ht's gRPC
lease/warmup endpoints.
"""
import pytest

pytest.importorskip("pyht")

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.playht import make_playht_router
    app.include_router(make_playht_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


def test_playht_tts_stream(base_url):
    from pyht import Client, TTSOptions
    from pyht.client import Format
    from pyht.inference_coordinates import InferenceCoordinatesOptions

    client = Client(
        user_id="ignored",
        api_key="ignored",
        auto_connect=False,
        advanced=Client.AdvancedOptions(
            inference_coordinates_options=InferenceCoordinatesOptions(
                api_url=f"{base_url}/playht/api/v4",
            ),
        ),
    )
    try:
        opts = TTSOptions(voice="default", format=Format.FORMAT_WAV)
        audio = b"".join(
            client.tts(
                "hello from the live test",
                opts,
                voice_engine="Play3.0-mini",
                protocol="http",
            )
        )
        assert len(audio) > 16
    finally:
        client.close()
