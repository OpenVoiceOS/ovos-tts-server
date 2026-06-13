"""Live test for the /playht router.

PlayHT's official ``pyht`` SDK is gRPC-first and connects to play.ht's own hosts;
it cannot be repointed at an HTTP test server (the examples/ script shows the
documented monkey-patch users apply). The router itself is plain HTTP, so this
test exercises the documented ``POST /api/v2/tts/stream`` flow over httpx.
"""
import httpx

from test.integration.conftest import run_live_server


def _register(app, engine):
    from ovos_tts_server.routers.playht import make_playht_router
    app.include_router(make_playht_router(engine))


def test_playht_stream():
    gen = run_live_server(_register)
    base_url = next(gen)
    try:
        resp = httpx.post(
            f"{base_url}/playht/api/v2/tts/stream",
            json={"text": "hello from the live test", "voice": "default", "output_format": "wav"},
            headers={"Authorization": "Bearer ignored", "X-User-ID": "ignored"},
            timeout=30,
        )
        assert resp.status_code == 200
        assert len(resp.content) > 16
    finally:
        gen.close()
