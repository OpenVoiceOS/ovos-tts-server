from typing import Optional, Tuple, Literal
from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from ovos_plugin_manager.tts import load_tts_plugin
from ovos_config import Configuration

class MaryTTSInput(BaseModel):
    """
    Pydantic model for validating MaryTTS /process API requests.
    Supports both standard MaryTTS params and basic defaults.
    """
    INPUT_TEXT: str = Field(..., description="The text to synthesize")
    INPUT_TYPE: Literal["TEXT", "SSML"] = "TEXT"
    LOCALE: Optional[str] = Field(None, description="Target Locale (e.g. en_US)")
    VOICE: Optional[str] = Field(None, description="Target Voice name")
    OUTPUT_TYPE: str = "AUDIO"
    AUDIO: str = "WAVE_FILE"


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
        List languages supported by the wrapped TTS engine.
        
        Returns:
            list[str]: Engine-reported language codes, or a single-item list containing the wrapper's default language if the engine does not provide available languages.
        """
        return self.engine.available_languages or [self.lang]

    @property
    def voices(self):
        """
        Return the available voices exposed by the wrapped TTS engine.
        
        A list of available voices — each item is typically a dict or a string depending on the engine implementation. Returns an empty list if the wrapped engine does not expose an `available_voices` attribute.
        """
        if hasattr(self.engine, "available_voices"):
            return self.engine.available_voices
        return []

    def synthesize(self, utterance: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Synthesize speech audio from the provided text or SSML.
        
        Parameters:
            utterance (str): Text or SSML to synthesize.
            **kwargs: Plugin-specific synthesis options forwarded to the underlying TTS engine (e.g., lang, voice, format).
        
        Returns:
            tuple: `(audio_path, phonemes)` where `audio_path` is the file path to the generated audio and `phonemes` is the phoneme data produced by the engine, or `None` if not available.
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

    # --- MaryTTS Compatibility Endpoints ---

    @app.get("/locales")
    def mary_locales():
        """
        Provide supported locales in MaryTTS-compatible plain-text format.
        
        Returns:
            A plain-text HTTP response whose body contains supported locale identifiers,
            one per line (newline-separated).
        """
        langs = tts_engine.langs
        # Ensure we return plain text, not JSON
        return Response(content="\n".join(langs), media_type="text/plain")

    @app.get("/voices")
    def mary_voices():
        """
        Provide a MaryTTS-compatible plain-text listing of available voices.
        
        Each line has the format: "<name> <locale> <gender>". The generated name must not contain spaces; the response currently emits a single default voice line based on the server's TTS engine.
        
        Returns:
        	A FastAPI Response with media_type "text/plain" whose body is newline-separated voice entries.
        """
        lines = []

        # plugins don't report specific voices - TODO - add available_voices/models property to TTS plugins
        lines.append(f"default {tts_engine.lang} m {tts_engine.plugin_name}")

        return Response(content="\n".join(lines), media_type="text/plain")

    @app.api_route("/process", methods=["GET", "POST"])
    def mary_process(params: MaryTTSInput = Depends()):
        """
        Handle MaryTTS-compatible /process requests and return the synthesized audio as a WAV FileResponse.
        
        Maps MaryTTS parameters to TTS engine options (LOCALE → lang, VOICE underscores replaced with spaces) and synthesizes INPUT_TEXT via the injected TTS engine.
        
        Parameters:
            params (MaryTTSInput): Validated MaryTTS request parameters injected via Depends(); contains INPUT_TEXT, INPUT_TYPE, LOCALE, VOICE, OUTPUT_TYPE, and AUDIO.
        
        Returns:
            FileResponse: A response serving the synthesized audio as a WAV file.
        """
        # Map MaryTTS specific params to OVOS synthesize params
        synth_kwargs = {}

        if params.LOCALE:
            synth_kwargs["lang"] = params.LOCALE

        if params.VOICE:
            # Revert the space sanitization if the plugin needs real spaces
            # (Though most OVOS plugins map by ID, strict names might differ)
            synth_kwargs["voice"] = params.VOICE.replace("_", " ")

        audio_path, _ = tts_engine.synthesize(params.INPUT_TEXT, **synth_kwargs)
        return FileResponse(audio_path, media_type="audio/wav")

    # --- Legacy OVOS Endpoints ---

    @app.get("/synthesize/{utterance}")
    async def synth_legacy(utterance: str, request: Request) -> FileResponse:
        """
        Produce synthesized audio for an utterance using query parameters from the incoming request.
        
        Parameters:
            utterance (str): Text to synthesize.
            request (Request): Incoming FastAPI request whose query parameters are forwarded to the TTS plugin as synthesis options.
        
        Returns:
            FileResponse: A response serving the generated audio file.
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

    return app


def start_tts_server(tts_plugin: str, cache: bool = False) -> Tuple[FastAPI, TTSEngineWrapper]:
    """
    Create and configure a FastAPI application wired to a TTSEngineWrapper for the specified plugin.
    
    Parameters:
        tts_plugin (str): Name of the TTS plugin to load.
        cache (bool): If True, persist synthesized audio cache across restarts.
    
    Returns:
        Tuple[FastAPI, TTSEngineWrapper]: The configured FastAPI app and the initialized TTS engine wrapper.
    """
    tts_engine = TTSEngineWrapper(plugin_name=tts_plugin, cache=cache)
    app = create_app(tts_engine)
    return app, tts_engine