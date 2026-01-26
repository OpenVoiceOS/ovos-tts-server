from typing import Optional, Tuple
from fastapi import FastAPI, Request, Depends
from fastapi.responses import FileResponse
from ovos_plugin_manager.tts import load_tts_plugin
from ovos_config import Configuration


class TTSEngineWrapper:
    """Wrapper around an OVOS TTS engine for dependency injection."""

    def __init__(self, plugin_name: str, cache: bool = False):
        """
        Initialize TTS engine.

        Args:
            plugin_name: Name of the TTS plugin to load.
            cache: Whether to persist cached audio across reboots.
        """
        engine = load_tts_plugin(plugin_name)
        config = Configuration().get("tts", {}).get(plugin_name, {})
        config["persist_cache"] = cache
        self.engine = engine(config=config)
        self.engine.log_timestamps = True
        self.plugin_name = plugin_name
        self.lang = config.get("lang") or Configuration().get("lang") or "mul"

    @property
    def langs(self):
        return self.engine.available_languages or [self.lang]

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Synthesize audio from text/SSML.

        Args:
            utterance: Text or SSML to synthesize.
            kwargs: Plugin-specific synthesis parameters.

        Returns:
            Tuple of audio file path and phonemes (if any).
        """
        utterance = self.engine.validate_ssml(utterance)
        audio, phonemes = self.engine.synth(utterance, **kwargs)
        return audio.path, phonemes


def create_app(tts_engine: TTSEngineWrapper) -> FastAPI:
    """
    Create FastAPI app with injected TTS engine.

    Args:
        tts_engine: TTSEngineWrapper instance.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(title="OVOS TTS Server")

    @app.get("/status")
    def status() -> dict:
        """Return the status of the TTS engine."""
        config = getattr(tts_engine.engine, "config", {})
        return {
            "status": "ok",
            "plugin": tts_engine.plugin_name,
            "langs": tts_engine.langs,
            "default_lang": tts_engine.lang,
            "default_model": config.get("model"),
            "default_voice": config.get("voice")
        }

    # legacy OVOS endpoints
    @app.get("/synthesize/{utterance}")
    async def synth_legacy(utterance: str, request: Request) -> FileResponse:
        """
        Legacy endpoint for simple TTS synthesis.

        Query parameters are passed directly to the TTS plugin.
        """
        audio_path, _ = tts_engine.synthesize(utterance, **request.query_params)
        return FileResponse(audio_path)

    @app.get("/v2/synthesize")
    async def synth_v2(request: Request) -> FileResponse:
        """
        Modern endpoint for TTS synthesis.

        Expects 'utterance' as a query parameter.
        All other query parameters are passed to the TTS plugin.
        """
        utterance = request.query_params.get("utterance")
        if not utterance:
            return {"error": "Missing 'utterance' query parameter"}

        # Pass all plugin-specific options
        plugin_params = dict(request.query_params)
        plugin_params.pop("utterance", None)  # Remove the utterance key
        audio_path, _ = tts_engine.synthesize(utterance, **plugin_params)
        return FileResponse(audio_path)

    return app


def start_tts_server(tts_plugin: str, cache: bool = False) -> Tuple[FastAPI, TTSEngineWrapper]:
    """
    Initialize TTS engine and create FastAPI app.

    Args:
        tts_plugin: TTS plugin name to load.
        cache: Whether to persist cached audio across reboots.

    Returns:
        Tuple of FastAPI app and TTS engine wrapper.
    """
    tts_engine = TTSEngineWrapper(plugin_name=tts_plugin, cache=cache)
    app = create_app(tts_engine)
    return app, tts_engine
