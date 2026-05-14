from typing import Optional, Tuple
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from ovos_plugin_manager.tts import load_tts_plugin
from ovos_config import Configuration


class TTSEngineWrapper:
    """Wrapper around an OVOS TTS engine for dependency injection."""

    def __init__(self, plugin_name: str, cache: bool = False):
        """
        Create a TTSEngineWrapper by loading and configuring the named TTS plugin.
        
        Parameters:
            plugin_name (str): Name of the TTS plugin to load.
            cache (bool): If True, persist generated audio cache across restarts.
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
        """
        Return the list of languages supported by the wrapped TTS engine.
        
        Returns:
            list[str]: Engine-reported available language codes, or a list containing the wrapper's default language if the engine does not expose available languages.
        """
        return self.engine.available_languages or [self.lang]

    @property
    def voices(self):
        """
        Attempt to retrieve available voices from the plugin.
        Returns a list of dictionaries or strings depending on the plugin.
        """
        if hasattr(self.engine, "available_voices"):
            return self.engine.available_voices
        return []

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Synthesize spoken audio from the given text or SSML.
        
        Parameters:
        	utterance (str): Text or SSML to synthesize.
        	kwargs: Plugin-specific synthesis parameters forwarded to the underlying TTS engine.
        
        Returns:
        	tuple (str, Optional[str]): `(audio_path, phonemes)` where `audio_path` is the file path to the generated audio and `phonemes` is the phoneme data produced by the engine, or `None` if not available.
        """
        utterance = self.engine.validate_ssml(utterance)
        audio, phonemes = self.engine.synth(utterance, **kwargs)
        return audio.path, phonemes


def create_app(tts_engine: TTSEngineWrapper) -> FastAPI:
    """
    Create a FastAPI application wired to the provided TTS engine.
    
    Parameters:
        tts_engine (TTSEngineWrapper): Injected TTS engine used by the app's endpoints.
    
    Returns:
        FastAPI: Configured FastAPI application exposing /status, legacy /synthesize/{utterance}, and /v2/synthesize endpoints.
    """
    app = FastAPI(title="OVOS TTS Server")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.get("/status")
    def status() -> dict:
        """
        Provide current status and configuration details for the injected TTS engine.
        
        Returns:
            dict: A mapping containing:
                - "status": health status string, always "ok".
                - "plugin": plugin name (str).
                - "langs": list of supported language codes (List[str]).
                - "default_lang": default language code (str).
                - "default_model": configured model name or None.
                - "default_voice": configured voice name or None.
        """
        config = getattr(tts_engine.engine, "config", {})
        return {
            "status": "ok",
            "plugin": tts_engine.plugin_name,
            "langs": tts_engine.langs,
            "default_lang": tts_engine.lang,
            "default_model": config.get("model"),
            "default_voice": config.get("voice")
        }

    # --- Legacy OVOS Endpoints ---

    @app.get("/synthesize/{utterance}")
    async def synth_legacy(utterance: str, request: Request) -> FileResponse:
        """
        Generate and return synthesized audio for the given utterance, forwarding query parameters to the TTS plugin.
        
        Parameters:
            request (Request): The incoming FastAPI request whose query parameters are forwarded to the TTS plugin.
        
        Returns:
            FileResponse: A response serving the synthesized audio file.
        """
        audio_path, _ = tts_engine.synthesize(utterance, **request.query_params)
        return FileResponse(audio_path)

    @app.get("/v2/synthesize")
    async def synth_v2(request: Request) -> FileResponse:
        """
        Handle /v2/synthesize requests and return synthesized speech as a file response.
        
        Reads the required "utterance" query parameter and forwards all other query parameters to the TTS plugin as options. If "utterance" is missing, an error dictionary is returned.
        
        Returns:
            FileResponse: A response serving the synthesized audio file.
            dict: If "utterance" is missing, a dictionary with an "error" key describing the problem.
        """
        utterance = request.query_params.get("utterance")
        if not utterance:
            return Response(content='{"error": "Missing utterance"}', status_code=400, media_type="application/json")

        # Pass all plugin-specific options
        plugin_params = dict(request.query_params)
        plugin_params.pop("utterance", None)  # Remove the utterance key
        audio_path, _ = tts_engine.synthesize(utterance, **plugin_params)
        return FileResponse(audio_path)

    from ovos_tts_server.routers.azure_tts import make_azure_tts_router
    app.include_router(make_azure_tts_router(tts_engine))

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