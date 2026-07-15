import os
import shutil
import tempfile
from typing import Optional, Tuple
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from ovos_plugin_manager.transformer_services import (DialogTransformersService,
                                                      TTSTransformersService)
from ovos_plugin_manager.tts import load_tts_plugin
from ovos_config import Configuration


class TTSEngineWrapper:
    """Wrapper around an OVOS TTS engine for dependency injection."""

    def __init__(self, plugin_name: str, cache: bool = False,
                 lang: Optional[str] = None):
        """
        Create a TTSEngineWrapper by loading and configuring the named TTS plugin.

        Parameters:
            plugin_name (str): Name of the TTS plugin to load.
            cache (bool): If True, persist generated audio cache across restarts.
            lang (Optional[str]): Language code that overrides any configured
                language for the plugin. Plugins select their default voice from
                this language when no specific voice is configured. When None,
                the plugin's configured language is used.
        """
        engine = load_tts_plugin(plugin_name)
        config = Configuration().get("tts", {}).get(plugin_name, {})
        config["persist_cache"] = cache
        # An explicit lang takes precedence over the plugin's configured lang
        if lang:
            config["lang"] = lang
        self.engine = engine(config=config)
        self.engine.log_timestamps = True
        self.plugin_name = plugin_name
        self.lang = config.get("lang") or Configuration().get("lang") or "mul"
        # transformer pipelines: config-gated and opt-in, a plugin only
        # loads if named in the mycroft.conf "dialog_transformers" /
        # "tts_transformers" sections
        self.dialog_transformers = DialogTransformersService(
            config=Configuration().get("dialog_transformers") or {})
        self.tts_transformers = TTSTransformersService(
            config=Configuration().get("tts_transformers") or {})

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
        if self.dialog_transformers.plugins:
            utterance, _ = self.dialog_transformers.transform(
                utterance, {"lang": kwargs.get("lang") or self.lang})
        utterance = self.engine.validate_ssml(utterance)
        audio, phonemes = self.engine.synth(utterance, **kwargs)
        audio_path = audio.path
        if self.tts_transformers.plugins:
            audio_path = self._apply_tts_transformers(audio_path)
        return audio_path, phonemes

    def _apply_tts_transformers(self, audio_path: str) -> str:
        """Run the TTS transformer chain on a copy of the synthesized file.

        The engine returns a path into its cache; transforming a copy keeps
        cached audio pristine so later requests are not served already
        transformed (or repeatedly re-transformed) files.
        """
        ext = os.path.splitext(audio_path)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            tmp_path = f.name
        shutil.copy(audio_path, tmp_path)
        transformed, _ = self.tts_transformers.transform(tmp_path)
        return transformed


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

    from ovos_tts_server.routers.elevenlabs import make_elevenlabs_router
    app.include_router(make_elevenlabs_router(tts_engine))

    from ovos_tts_server.routers.openai_tts import make_openai_tts_router
    app.include_router(make_openai_tts_router(tts_engine))

    from ovos_tts_server.routers.coqui import make_coqui_router
    app.include_router(make_coqui_router(tts_engine))

    from ovos_tts_server.routers.google_tts import make_google_tts_router
    app.include_router(make_google_tts_router(tts_engine))

    from ovos_tts_server.routers.amazon_polly import make_amazon_polly_router
    app.include_router(make_amazon_polly_router(tts_engine))

    from ovos_tts_server.routers.azure_tts import make_azure_tts_router
    app.include_router(make_azure_tts_router(tts_engine))

    from ovos_tts_server.routers.marytts import (
        make_marytts_router,
        make_marytts_root_router,
    )
    app.include_router(make_marytts_router(tts_engine))
    # Root aliases for legacy assistive-tech that hardcodes bare MaryTTS paths
    app.include_router(make_marytts_root_router(tts_engine))

    from ovos_tts_server.routers.cartesia import make_cartesia_router
    app.include_router(make_cartesia_router(tts_engine))

    from ovos_tts_server.routers.deepgram_aura import make_deepgram_aura_router
    app.include_router(make_deepgram_aura_router(tts_engine))

    from ovos_tts_server.routers.playht import make_playht_router
    app.include_router(make_playht_router(tts_engine))

    # UTCP manual endpoint (no extra deps required)
    from ovos_tts_server.utcp_manual import make_utcp_router
    app.include_router(make_utcp_router(tts_engine))

    return app


def start_tts_server(
    tts_plugin: str,
    cache: bool = False,
    enable_mcp: bool = False,
    lang: Optional[str] = None,
) -> Tuple[FastAPI, TTSEngineWrapper]:
    """
    Initialize TTS engine and create FastAPI app.

    Args:
        tts_plugin: TTS plugin name to load.
        cache: Whether to persist cached audio across reboots.
        enable_mcp: If True, mount the optional MCP server at ``/mcp``
            (requires ``pip install "ovos-tts-server[mcp]"``).
        lang: Language code that overrides the plugin's configured language,
            driving its default voice selection. When None, the configured
            language is used.

    Returns:
        Tuple of FastAPI app and TTS engine wrapper.
    """
    tts_engine = TTSEngineWrapper(plugin_name=tts_plugin, cache=cache, lang=lang)
    app = create_app(tts_engine)
    if enable_mcp:
        from ovos_tts_server.mcp_server import mount_mcp
        mount_mcp(app, tts_engine)
    return app, tts_engine