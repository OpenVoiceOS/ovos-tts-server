# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from fastapi import FastAPI
from fastapi.responses import FileResponse
from ovos_plugin_manager.tts import load_tts_plugin
from ovos_utils.log import LOG
from ovos_config import Configuration
from starlette.requests import Request


LOG.set_level("ERROR")  # avoid server side logs

TTS = None


def create_app(tts_plugin, has_gradio=False):
    app = FastAPI()

    @app.get("/status")
    def stats(request: Request):
        return {"status": "ok",
                "plugin": tts_plugin,
                "gradio": has_gradio}

    @app.get("/synthesize/{utterance}")
    def synth(utterance: str, request: Request):
        utterance = TTS.validate_ssml(utterance)
        audio, phonemes = TTS.synth(utterance, **request.query_params)
        return FileResponse(audio.path)

    @app.get("/v2/synthesize")
    def synth(request: Request):
        utterance = request.query_params["utterance"]
        utterance = TTS.validate_ssml(utterance)
        audio, phonemes = TTS.synth(utterance, **request.query_params)
        return FileResponse(audio.path)
        
    return app


def start_tts_server(tts_plugin, cache=False, has_gradio=False):
    global TTS

    # load ovos TTS plugin
    engine = load_tts_plugin(tts_plugin)

    config = Configuration().get("tts", {}).get(tts_plugin, {})
    config["persist_cache"] = cache  # this will cache every synth even across reboots
    TTS = engine(config=config)
    TTS.log_timestamps = True  # enable logging

    app = create_app(tts_plugin, has_gradio)
    return app, TTS


