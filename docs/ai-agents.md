# Use ovos-tts-server from AI agents (MCP and UTCP)

## What you can do

**MCP (Model Context Protocol).** Start the server with `--mcp` and it serves an MCP endpoint at `/mcp`. An MCP client, such as Claude Code, Claude Desktop, opencode, Mistral Vibe or an OVOS agent, connects to it and calls the `synthesize` tool. The tool returns the audio file encoded in base64, with its MIME type, inside a JSON object. Use MCP when an agent must receive the audio.

**UTCP (Universal Tool Calling Protocol).** Every server publishes a UTCP manual at `GET /utcp`. The manual tells a UTCP client how to call the plain HTTP endpoints of the server. The client then calls them directly, with no wrapper process. Use UTCP when your agent already speaks UTCP or when you do not want to install the MCP extra.

| Endpoint | Available when | Install |
| :--- | :--- | :--- |
| `GET /utcp` | Always | `pip install --pre ovos-tts-server` |
| `/mcp` | The server starts with `--mcp` | `pip install --pre "ovos-tts-server[mcp]"` |

The examples use the default port `9666` and the [espeak-ng](https://github.com/OpenVoiceOS/ovos-tts-plugin-espeakng) plugin. Any OVOS TTS plugin works the same way.

## Let Claude Code speak text

You get a `synthesize` tool inside Claude Code. Claude Code calls it and receives the audio and the path of the audio file on the server machine.

1. Install and start the server with MCP:

   ```bash
   pip install --pre "ovos-tts-server[mcp]" ovos-tts-plugin-espeakng
   ovos-tts-server --engine ovos-tts-plugin-espeakng --mcp
   ```

2. Add the server to Claude Code:

   ```bash
   claude mcp add --transport http ovos-tts http://localhost:9666/mcp
   claude mcp get ovos-tts
   ```

   On success, `claude mcp get` shows:

   ```
   ovos-tts:
     Scope: Local config (private to you in this project)
     Status: ✔ Connected
     Type: http
     URL: http://localhost:9666/mcp
   ```

3. Ask Claude Code to use the tool:

   ```bash
   claude -p 'Call the synthesize tool of the ovos-tts MCP server with the text "Hi." Then reply with only the mime_type and path fields from the result, one per line.' \
     --allowedTools 'mcp__ovos-tts__synthesize'
   ```

   Output:

   ```
   audio/wav
   /tmp/tts/ovos-tts-plugin-espeakng/m1/en-US/7b00b6d52a564b31999eb3de9ce0980b.wav
   ```

The tool result holds the complete audio as base64, and Claude Code reads all of it. Keep the text short: two seconds of speech is about 120 KB of base64.

If `claude mcp get` does not show `Connected`, see [Troubleshooting](#troubleshooting).

## Use the server from Claude Desktop

Claude Desktop starts local MCP servers as processes from `claude_desktop_config.json`. That file does not accept a URL. The `mcp-remote` bridge, which needs Node.js, connects the two.

1. Start the server with `--mcp`, as in [Let Claude Code speak text](#let-claude-code-speak-text).
2. Add this entry to `claude_desktop_config.json`:

   ```json
   {
     "mcpServers": {
       "ovos-tts": {
         "command": "npx",
         "args": ["-y", "mcp-remote", "http://localhost:9666/mcp"]
       }
     }
   }
   ```

3. Quit and restart Claude Desktop. The `ovos-tts` server and its `synthesize` tool show in the connectors menu.

A custom connector in the Claude settings is a different mechanism. Anthropic servers make that connection, so the endpoint must be reachable from the public internet. The server has no authentication, so do not expose it that way. See [Security](#security).

## Let opencode speak text

You get `synthesize` in opencode.

1. Start the server with `--mcp`, as in [Let Claude Code speak text](#let-claude-code-speak-text).
2. Add this entry to `opencode.json` in your project folder:

   ```json
   {
     "$schema": "https://opencode.ai/config.json",
     "mcp": {
       "ovos-tts": {
         "type": "remote",
         "url": "http://localhost:9666/mcp",
         "enabled": true
       }
     }
   }
   ```

3. Check the connection:

   ```console
   $ opencode mcp list
   ┌  MCP Servers
   │
   ●  ✓ ovos-tts connected
   │      http://localhost:9666/mcp
   │
   └  1 server(s)
   ```

## Let Mistral Vibe speak text

You get `synthesize` in Vibe.

1. Start the server with `--mcp`, as in [Let Claude Code speak text](#let-claude-code-speak-text).
2. Add this entry to `~/.vibe/config.toml`:

   ```toml
   [[mcp_servers]]
   name = "ovos-tts"
   transport = "streamable-http"
   url = "http://localhost:9666/mcp"
   ```

   Write the entry in the file. Do not use `vibe mcp add` for this server: that
   command sets OAuth login for an HTTP server, and the server does not use
   OAuth.

3. Start `vibe`. Vibe loads the tools of the server when it starts. It gives
   each tool the server name as a prefix, and it changes each hyphen to `_`:
   `ovos_tts_synthesize`.

## Give an OVOS persona or agent a speech tool

[ovos-tool-adapters](https://github.com/OpenVoiceOS/ovos-tool-adapters) turns an MCP or UTCP server into an OVOS `ToolBox`. Your agent gets the server tools with their real argument schemas.

Install the latest alpha of ovos-tool-adapters (`pip install --pre ovos-tool-adapters`) for both toolboxes.

Start the server with `--mcp` and add this toolbox configuration:

```json
{
  "toolboxes": ["ovos-mcp-toolbox"],
  "ovos-mcp-toolbox": {"transport": "http", "url": "http://localhost:9666/mcp", "timeout": 30}
}
```

The toolbox discovers `['synthesize']`. A call with `{"text": "Hello from an OVOS agent."}` returns content that starts with `{"mime_type":"audio/wav","data":"UklGR...`.

The UTCP toolbox (`ovos-utcp-toolbox`) discovers the tools of the UTCP manual.

## Let a UTCP agent discover the endpoints

Point the agent at `/utcp`. No extra package is needed on the server.

1. Start the server. `--mcp` is not needed:

   ```bash
   ovos-tts-server --engine ovos-tts-plugin-espeakng
   ```

2. Register the manual with your UTCP client. This example uses the reference Python client (`pip install --pre utcp utcp-http`):

   ```python
   import asyncio
   import base64
   from utcp.utcp_client import UtcpClient
   from utcp.data.utcp_client_config import UtcpClientConfig


   async def main():
       config = UtcpClientConfig(manual_call_templates=[{
           "name": "ovos_tts",
           "call_template_type": "http",
           "url": "http://localhost:9666/utcp",
           "http_method": "GET",
       }])
       client = await UtcpClient.create(config=config)
       tools = await client.config.tool_repository.get_tools()
       print([tool.name for tool in tools])
       result = await client.call_tool("ovos_tts.tts_synthesize_v2",
                                       {"utterance": "Hello from a UTCP agent.", "lang": "en-us"})
       with open("hello.wav", "wb") as f:
           f.write(base64.b64decode(result["data"]))
       print(result["mime_type"], "written to hello.wav")

   asyncio.run(main())
   ```

   Output:

   ```
   ['ovos_tts.tts_status', 'ovos_tts.tts_synthesize_v2']
   audio/wav written to hello.wav
   ```

## Call the server from your own MCP client

This script uses the reference Python client (`pip install --pre "mcp>=2"`). It lists the tools, calls `synthesize` and writes the audio to `hello.wav`.

```python
import asyncio
import base64
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client("http://localhost:9666/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])
            result = await session.call_tool("synthesize", {"text": "Hello from the MCP endpoint.", "lang": "en-us"})
            with open("hello.wav", "wb") as f:
                f.write(base64.b64decode(result.structured_content["data"]))
            print(result.structured_content["mime_type"], "written to hello.wav")

asyncio.run(main())
```

Output:

```
['synthesize']
audio/wav written to hello.wav
```

With `mcp` 1.x, the client is `streamablehttp_client`, it yields three values, and the result field is `structuredContent`.

## Reference

### MCP

The endpoint is `http://HOST:9666/mcp` with the streamable HTTP transport. `/mcp` and `/mcp/` both reach it with no redirect. The server has no SSE transport. The FastMCP server name is `ovos-tts`.

**`synthesize`**

| Argument | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `text` | string | Yes | The text to speak. It must contain at least one character that is not a space. |
| `voice` | string | No | A voice name that the loaded plugin knows. |
| `lang` | string | No | A language code, for example `en-us`. |

Result:

```json
{
  "mime_type": "audio/wav",
  "data": "<base64-encoded audio file>",
  "path": "/tmp/tts/ovos-tts-plugin-espeakng/m1/en-US/0e55fc03ac76e0f077c3a879aee9eb39.wav",
  "phonemes": null
}
```

`mime_type` comes from the audio file the plugin writes: `audio/wav` for WAV, `audio/mpeg` for plugins that write MP3. `data` holds the complete audio. `path` is a file on the server disk, so it is useful only to a client on the same machine. `phonemes` is `null` when the plugin does not return phonemes.

When `text` is empty, the call returns an error: `'text' must be a non-empty string`.

### UTCP

`GET /utcp` returns a UTCP manual with `utcp_version` `1.0.0`. `manual_version` is the version of the installed `ovos-tts-server` package. The URLs in the manual come from the request. See [Reverse proxy](#reverse-proxy).

| Tool | HTTP call | Inputs | Output |
| :--- | :--- | :--- | :--- |
| `tts_status` | `GET /status` | None | `{status, plugin, langs, default_lang, default_model, default_voice}` |
| `tts_synthesize_v2` | `GET /v2/synthesize/json` | `utterance` (required), `voice`, `lang` | `{mime_type, phonemes, data}`, with the audio file in `data` as base64 and its MIME type in `mime_type` |

`/v2/synthesize` and `/synthesize/{utterance}` return the audio in the format the plugin writes, such as WAV or MP3, for plain HTTP clients. They are not in the manual, because UTCP HTTP clients read a response that is not JSON as text.

### Python

```python
from ovos_tts_server import create_app, start_tts_server

app, engine = start_tts_server("ovos-tts-plugin-espeakng", enable_mcp=True)
```

`create_app(engine, enable_mcp=True)` does the same for an engine that you load yourself. The agent protocols live in `ovos_tts_server.mcp_server` (`build_mcp`, `mount_mcp`) and `ovos_tts_server.utcp` (`build_utcp_manual`, `make_utcp_router`).

## Deployment

### Docker

The image from the repository `Dockerfile` does not include the `mcp` extra.

1. In `Dockerfile`, add the extra to the install line:

   ```dockerfile
   RUN pip install --no-cache-dir --pre "ovos-tts-server[audio,mcp]" \
                                  ovos-tts-plugin-server
   ```

2. In `docker-compose.yml`, add `--mcp` to `command`:

   ```yaml
       command:
         - "--engine"
         - "ovos-tts-plugin-server"
         - "--host"
         - "0.0.0.0"
         - "--port"
         - "9666"
         - "--mcp"
   ```

3. Build and start the container, then connect to `http://127.0.0.1:8080/mcp` and `http://127.0.0.1:8080/utcp`. The compose file publishes container port `9666` on host port `8080`.

`GET /utcp` needs no change.

### Reverse proxy

The server builds the URLs in the UTCP manual from each request. A client that reads the manual through a proxy gets the proxy URLs only when the proxy sends the correct headers.

- The server takes the host name from the `Host` header. Configure the proxy to forward the original `Host` header. In nginx: `proxy_set_header Host $host;`.
- The server takes the scheme from `X-Forwarded-Proto` only when the request comes from a trusted address. By default, only `127.0.0.1` is trusted. When the proxy runs on a different machine, set the environment variable `FORWARDED_ALLOW_IPS` to the proxy address before you start the server.
- The server ignores `X-Forwarded-Host` and path prefixes. Serve the server at the root of its own host name, not under a sub-path such as `/tts/`.

With `Host: tts.example.org` and `X-Forwarded-Proto: https` from a trusted proxy, the manual lists `https://tts.example.org/status` and `https://tts.example.org/v2/synthesize/json`.

### Security

- No endpoint has authentication. This includes `/mcp` and `/utcp`. Any client that can reach the port can synthesize speech.
- The command line binds to `0.0.0.0` by default, so the server listens on all network interfaces. For agents on the same machine, start the server with `--host 127.0.0.1`.
- The server accepts requests from all browser origins (CORS `*`).
- To serve agents on other machines, put the server behind a reverse proxy that adds authentication and TLS.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `POST /mcp` returns `404 Not Found` | The server started without `--mcp`, or the `mcp` extra is not installed. Without the extra, the log shows `MCP support not available — install with: pip install "ovos-tts-server[mcp]"`. | Install `ovos-tts-server[mcp]` and start with `--mcp`. |
| `GET /mcp/` returns `400` with `Bad Request: Missing session ID` | A plain HTTP client, such as a browser or `curl`, sent the request. MCP needs a session that the client opens with an `initialize` call. | Use an MCP client. |
| `GET /mcp/sse` returns `404` | The server has no SSE transport. | Use the streamable HTTP transport at `/mcp`. |
| The MCP client fails with `ReadError` and the container log shows no request | The client resolved `localhost` to the IPv6 address `::1`, and the container runtime publishes the port on IPv4 only. Rootless Podman does this. | Use `127.0.0.1` in the URL. |
| The UTCP client fails with `UnicodeDecodeError` | The client called an endpoint that returns raw audio (WAV or MP3). | Call `ovos_tts.tts_synthesize_v2`, which returns JSON. |
| The manual shows `localhost` or `http` behind a proxy | The proxy does not forward `Host`, or the proxy address is not trusted for `X-Forwarded-Proto`. | See [Reverse proxy](#reverse-proxy). |
