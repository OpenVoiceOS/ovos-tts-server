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
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", help="tts plugin to be used")
    parser.add_argument("--port", help="port number",
                        default=9666)
    parser.add_argument("--host", help="host",
                        default="0.0.0.0")
    parser.add_argument("--cache", help="save every synth to disk",
                        action="store_true")
    parser.add_argument("--lang",
                        help="language the plugin serves; selects its default "
                             "voice when no voice is configured. Overrides the "
                             "plugin's configured language.",
                        default=None)
    parser.add_argument(
        "--mcp",
        help="mount MCP server at /mcp (requires ovos-tts-server[mcp])",
        action="store_true",
    )
    args = parser.parse_args()

    server, engine = start_tts_server(args.engine, cache=bool(args.cache),
                                      enable_mcp=bool(args.mcp), lang=args.lang)
    LOG.info("Server Started")
    uvicorn.run(server, host=args.host, port=int(args.port))


if __name__ == "__main__":
    main()
