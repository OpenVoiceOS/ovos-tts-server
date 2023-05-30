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
from starlette.requests import Request

TTS = None


def create_app(tts_plugin):
    app = FastAPI()

    @app.get("/status")
    def stats(request: Request):
        return {"status": "ok", "plugin": tts_plugin}

    @app.get("/synthesize/{utterance}")
    def synth(utterance: str, request: Request):
        LOG.debug(f"{utterance}|{request.query_params}")
        utterance = TTS.validate_ssml(utterance)
        audio, phonemes = TTS.synth(utterance, **request.query_params)
        return FileResponse(audio.path)

    return app


def start_tts_server(tts_plugin, cache=False):
    global TTS

    # load ovos TTS plugin
    engine = load_tts_plugin(tts_plugin)

    TTS = engine(config={"persist_cache": cache})  # this will cache every synth even across reboots
    TTS.log_timestamps = True  # enable logging

    app = create_app(tts_plugin)
    return app, TTS


