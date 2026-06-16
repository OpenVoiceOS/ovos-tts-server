"""Live test: drive the official Cartesia SDK against our /cartesia router."""
import pytest
from cartesia import Cartesia

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.cartesia import make_cartesia_router
    app.include_router(make_cartesia_router(engine))


@pytest.fixture(scope="module")
def base_url():
    yield from run_live_server(_register)


def test_cartesia_tts_bytes(base_url):
    client = Cartesia(api_key="ignored", base_url=f"{base_url}/cartesia")
    audio = b"".join(client.tts.bytes(
        model_id="sonic-2",
        transcript="hello from the live test",
        voice={"mode": "id", "id": "default"},
        output_format={"container": "wav", "sample_rate": 22050, "encoding": "pcm_s16le"},
    ))
    assert len(audio) > 16
