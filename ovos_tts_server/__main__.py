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

import uvicorn

from ovos_tts_server import start_tts_server
from ovos_utils.log import LOG


def main():
    """
    Parse command-line options and start the Text-to-Speech server served by uvicorn.
    
    Recognized command-line options include:
    - --engine: TTS plugin to use
    - --port: TCP port to bind (default 9666)
    - --host: network interface to bind (default "0.0.0.0")
    - --cache: save each synthesis to disk (flag)
    - --lang: default language for the plugin (default "en-us")
    - --title: UI title (default "TTS")
    - --description: UI description (default "Get Text-to-Speech")
    - --info: UI end text
    - --badge: URL of visitor badge
    
    This function initializes the TTS server using the provided options and runs it with uvicorn.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", help="tts plugin to be used")
    parser.add_argument("--port", help="port number",
                        default=9666)
    parser.add_argument("--host", help="host",
                        default="0.0.0.0")
    parser.add_argument("--cache", help="save every synth to disk",
                        action="store_true")
    parser.add_argument("--lang", help="default language supported by plugin",
                        default="en-us")
    parser.add_argument("--title", help="Title for webUI",
                        default="TTS")
    parser.add_argument("--description", help="Text description to print in UI",
                        default="Get Text-to-Speech")
    parser.add_argument("--info", help="Text to display at end of UI",
                        default=None)
    parser.add_argument("--badge", help="URL of visitor badge", default=None)
    args = parser.parse_args()

    server, engine = start_tts_server(args.engine, cache=bool(args.cache))
    LOG.info("Server Started")
    uvicorn.run(server, host=args.host, port=int(args.port))


if __name__ == "__main__":
    main()