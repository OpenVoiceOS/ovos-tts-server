# API Compatibility Reference

Audio format conversion is provided by `ovos_tts_server.audio_utils.convert_audio()`.
Install the `[audio]` extra (`pip install "ovos-tts-server[audio]"`) to enable
non-WAV outputs via `pydub`; without it, non-WAV requests fall back to WAV. See
[audio-formats.md](audio-formats.md).

## What you can do

You have code that calls a cloud text-to-speech API, and you want it to speak through your own OVOS TTS plugin instead. Change the base URL in that code to this server. The request, the response and the SDK stay the same. The voice and the language come from the OVOS plugin that the server runs.

Each vendor API has its own URL prefix, so all of them answer at the same time. The server accepts any API key and ignores it. Put authentication in your reverse proxy.

## User stories

Each recipe below was run against `ovos-tts-server --engine ovos-tts-plugin-espeakng`. The output lines are the real output. The audio comes from espeak-ng, so the voice and the sample rate change when you use a different plugin.

### I have code for the OpenAI SDK

Set `base_url` to the `/openai/v1` prefix. `model` and `voice` are accepted and ignored.

```python
from openai import OpenAI

client = OpenAI(api_key="unused", base_url="http://localhost:9666/openai/v1")
audio = client.audio.speech.create(model="tts-1", voice="alloy",
                                   input="Hello from OVOS.", response_format="wav")
open("hello.wav", "wb").write(audio.content)
```

```text
WAV 22050 Hz, 1 ch, 1.28 s
```

The default `response_format` is `mp3`, as in the OpenAI API. `client.audio.speech.with_streaming_response.create(...)` also works. An empty `input` gets a 422 error, as the OpenAI API gives.

### I have an OVOS device that uses the MaryTTS plugin

`ovos-tts-plugin-marytts` reads the voices from `/voices` and then calls `/process`. Set `voice` to a voice that `/voices` lists. The OVOS server lists one voice per plugin voice, and `default` when the plugin lists none.

```json
"tts": {
  "module": "ovos-tts-plugin-marytts",
  "ovos-tts-plugin-marytts": {"url": "http://localhost:9666/marytts", "voice": "default"}
}
```

The plugin was driven with the language tags that OVOS passes:

```text
OK   | en-US | 1.39 s at 22050 Hz
OK   | en-GB | 1.41 s at 22050 Hz
OK   | de-DE | 1.58 s at 22050 Hz
```

Without `voice`, the plugin asks for its own default, `cmu-slt-hsmm`, which is a voice of the upstream MaryTTS server. The plugin then refuses with `unsupported voice 'cmu-slt-hsmm'`. The plugin needs version 0.2.0a6 or later to match `en-US` to the server locale `en_US`.

### I have a client that speaks the MaryTTS HTTP protocol

Send `LOCALE` as a Java locale, as MaryTTS clients do. The server finds the matching language of the plugin. The match ignores case and `_` or `-`, and falls back to the base language: `pt_BR` reaches a plugin that has only `pt`.

```bash
curl -G http://localhost:9666/marytts/process \
  --data-urlencode "INPUT_TEXT=hello world" --data-urlencode "LOCALE=en_US" -o out.wav
curl http://localhost:9666/marytts/voices | head -1
```

```text
default en_US m ovos-tts-plugin-espeakng
```

`/locales` and `/voices` list the plugin languages as Java locales (`en_US`, `pt_BR`, `de`), as an upstream MaryTTS 5.2 server does. A locale that the plugin cannot speak gets a 500 error with the message `the TTS engine produced no audio; GET /locales and GET /voices list what it supports`.

### I have code for the ElevenLabs SDK

Set `base_url` to the `/elevenlabs` prefix. This recipe used `elevenlabs` 2.73.1.

```python
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="unused", base_url="http://localhost:9666/elevenlabs")
print([v.voice_id for v in client.voices.get_all().voices])
audio = b"".join(client.text_to_speech.convert(voice_id="default", model_id="x",
                                               text="Hello from ElevenLabs API."))
open("hello.mp3", "wb").write(audio)
```

```text
['default']
mp3, 1.99 s
```

### I have code for Amazon Polly through boto3

Set `endpoint_url` to the `/amazon-polly` prefix. Any credentials work.

```python
import boto3

polly = boto3.client("polly", endpoint_url="http://localhost:9666/amazon-polly",
                     region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
print([v["Id"] for v in polly.describe_voices()["Voices"]])
speech = polly.synthesize_speech(Text="Hello from Polly API.", OutputFormat="mp3", VoiceId="Joanna")
open("hello.mp3", "wb").write(speech["AudioStream"].read())
```

```text
['default']
mp3, 1.64 s
```

## Endpoint status

"Live" means that the vendor client in the table was run against a server with a real OVOS TTS plugin, as in the stories above. "SDK test" means that the repository's integration tests run the client against a server with a stand-in engine. "Not tested" means that no client was run.

| Vendor | Client | Status |
| :--- | :--- | :--- |
| OpenAI | `openai` SDK `audio.speech`, plain and streaming | Live |
| MaryTTS | `ovos-tts-plugin-marytts`, raw HTTP | Live |
| ElevenLabs | `elevenlabs` SDK below 3: `voices.get_all`, `text_to_speech.convert` | Live |
| ElevenLabs | `elevenlabs` SDK 3 | Fails: SDK 3 lists voices with `GET /v2/voices`, which the server does not have |
| Amazon Polly | `boto3` `describe_voices`, `synthesize_speech` | Live |
| Amazon Polly | `ovos-tts-plugin-polly` | SDK test |
| Google Cloud TTS, Azure TTS, Cartesia, Deepgram Aura, PlayHT, Coqui | vendor client or HTTP | SDK test |
| MaryTTS | Home Assistant `marytts` integration | Not tested |

## Reference

### Vendors at a glance

| Vendor | Prefix | Endpoint(s) | Response |
| :--- | :--- | :--- | :--- |
| [ElevenLabs](#elevenlabs-elevenlabs) | `/elevenlabs` | `GET /v1/voices`, `GET /v1/models`, `POST /v1/text-to-speech/{voice_id}`, `WS /v1/text-to-speech/{voice_id}/stream-input` | binary audio / JSON |
| [OpenAI](#openai-openai) | `/openai` | `POST /v1/audio/speech` | binary audio |
| [Coqui](#coqui-coqui) | `/coqui` | `GET /api/tts` | binary WAV |
| [Google Cloud TTS](#google-cloud-tts-google-tts) | `/google-tts` | `POST /v1/text:synthesize` | JSON (base64 audio) |
| [Amazon Polly](#amazon-polly-amazon-polly) | `/amazon-polly` | `POST /v1/speech`, `GET /v1/voices` | binary audio, voice list JSON |
| [Azure TTS](#azure-tts-azure-tts) | `/azure-tts` | `POST /cognitiveservices/v1` | binary audio |
| [MaryTTS](#marytts-marytts) | `/marytts` | `GET/POST /process`, `GET /voices`, `GET /locales` (+ root aliases) | binary WAV / text |
| [Cartesia](#cartesia-cartesia) | `/cartesia` | `POST /tts/bytes` | binary audio |
| [Deepgram Aura](#deepgram-aura-deepgram) | `/deepgram` | `POST /v1/speak?model=...` | binary audio |
| [PlayHT](#playht-playht) | `/playht` | `POST /api/v2/tts/stream`, `POST /api/v4/sdk-auth` | binary audio |

> **Kokoro / kokoro-fastapi** is OpenAI-compatible and needs no dedicated
> router, point any OpenAI-compatible client at the `/openai` prefix
> (`/openai/v1/audio/speech`).

Examples below assume the server runs at `http://localhost:9666`.

---

### ElevenLabs (`/elevenlabs`)

**Upstream:** [elevenlabs/elevenlabs-python](https://github.com/elevenlabs/elevenlabs-python) ·
[API reference](https://elevenlabs.io/docs/api-reference/text-to-speech) ·
[Node SDK](https://github.com/elevenlabs/elevenlabs-js)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/elevenlabs/v1/voices` | List voices from the plugin |
| GET | `/elevenlabs/v1/models` | List models (one entry: the plugin) |
| POST | `/elevenlabs/v1/text-to-speech/{voice_id}` | Synthesize speech |

**Auth:** `xi-api-key` header (accepted, ignored).

The `voice_id` may span several path segments, so voices named after a
HuggingFace repo id (`OpenVoiceOS/phoonnx_ar_dii_espeak`) can be addressed
directly. Pass the id exactly as `GET /v1/voices` reports it.

**Synthesis request:** path `voice_id` (use `default` for the plugin default),
query `output_format` (default `mp3_44100_128`), JSON body:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `text` | str (required) | Text to synthesize |
| `model_id` | str | Accepted, not forwarded |
| `voice_settings` | object | `stability`, `similarity_boost`, `style`, `use_speaker_boost`, accepted, not forwarded |

`output_format` selects both container and sample rate: `pcm_*` → headerless
mono 16-bit little-endian PCM resampled to the requested rate (`pcm_16000`,
`pcm_22050`, `pcm_24000`, `pcm_44100`, ...), `ulaw_8000` → G.711 mu-law,
`opus_*` → Ogg, otherwise the leading token (`mp3_44100_128` → `mp3`).
Compressed containers fall back to WAV if pydub is absent.

```bash
# List voices
curl -H "xi-api-key: x" http://localhost:9666/elevenlabs/v1/voices

# Synthesize
curl -X POST -H "xi-api-key: x" -H "Content-Type: application/json" \
  -d '{"text": "hello world"}' \
  "http://localhost:9666/elevenlabs/v1/text-to-speech/default?output_format=mp3_44100_128" \
  -o out.mp3
```

**Point the SDK at this server:**

```python
from elevenlabs.client import ElevenLabs
client = ElevenLabs(api_key="ignored", base_url="http://localhost:9666/elevenlabs")
```

```js
// @elevenlabs/elevenlabs-js
new ElevenLabsClient({ apiKey: "ignored", baseUrl: "http://localhost:9666/elevenlabs" });
```

#### WebSocket streaming (`stream-input`)

| Method | Path | Description |
| :--- | :--- | :--- |
| WS | `/elevenlabs/v1/text-to-speech/{voice_id}/stream-input` | Stream synthesized speech |

Registered by default, alongside the HTTP endpoints. Query parameters:
`output_format` (default `mp3_44100_128`, parsed as above), `language_code`
(→ `lang=`); other ElevenLabs options (`model_id`, `inactivity_timeout`, ...) are
accepted and ignored. Auth is the `xi-api-key` header or an `xi_api_key` field
in the first message, both accepted, ignored.

Client → server (JSON text frames):

1. `{"text": " ", "voice_settings": {...}, "generation_config": {...}}`, begin
   the stream.
2. `{"text": "hello world "}`, content, repeated; text accumulates.
3. `{"flush": true}`, generate the buffered text immediately.
4. `{"text": ""}`, end of stream: the buffer is generated and the socket closes.

Server → client (JSON text frames):

```json
{"audio": "<base64>", "isFinal": null, "normalizedAlignment": null, "alignment": null}
```

Audio is delivered in one or more frames, terminated by a frame with no audio
and `"isFinal": true`. Alignment fields are always null: the plugin API exposes
no character timings.

**Point the SDK at this server:** `client.text_to_speech.convert_realtime()` uses
this endpoint. Its realtime client derives the WebSocket URL from `base_url=` but
forces the `wss` scheme, so it cannot reach a plaintext server. Either put a TLS
terminator in front of ovos-tts-server (then `base_url="https://..."` works
untouched), or keep `ws` for `http` base URLs:

```python
import urllib.parse
from elevenlabs import VoiceSettings, realtime_tts
from elevenlabs.client import ElevenLabs

_orig_init = realtime_tts.RealtimeTextToSpeechClient.__init__

def _init(self, *, client_wrapper):
    _orig_init(self, client_wrapper=client_wrapper)
    parsed = urllib.parse.urlparse(client_wrapper.get_base_url())
    scheme = "ws" if parsed.scheme == "http" else "wss"
    self._ws_base_url = parsed._replace(scheme=scheme).geturl()

realtime_tts.RealtimeTextToSpeechClient.__init__ = _init

client = ElevenLabs(api_key="ignored", base_url="http://localhost:9666/elevenlabs")
for chunk in client.text_to_speech.convert_realtime(
        voice_id="default",
        text=iter(["hello world"]),
        output_format="pcm_24000",
        # the SDK unconditionally serializes voice_settings into its BOS frame
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8)):
    ...
```

Runnable version: [`examples/elevenlabs_ws_example.py`](../examples/elevenlabs_ws_example.py).
Clients that speak `ws://` directly (`websockets`, `websocket-client`, the JS SDK
with a `ws://` base) need no patching.

---

### OpenAI (`/openai`)

**Upstream:** [openai-python](https://github.com/openai/openai-python) ·
[Audio/speech reference](https://platform.openai.com/docs/api-reference/audio/createSpeech)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/openai/v1/audio/speech` | Synthesize speech |

**Auth:** `Authorization: Bearer ...` header (accepted, ignored).

JSON body:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `input` | str (required) | Text to synthesize (≤ 4096 chars) |
| `model` | str | Default `tts-1`, accepted, not forwarded |
| `voice` | str | Default `alloy`, accepted, not forwarded |
| `response_format` | str | Default `mp3`; maps to the output container |
| `speed` | float | `0.25`–`4.0`, accepted, not forwarded |

```bash
curl -X POST -H "Authorization: Bearer sk-ignored" -H "Content-Type: application/json" \
  -d '{"model": "tts-1", "input": "hello world", "voice": "alloy", "response_format": "wav"}' \
  "http://localhost:9666/openai/v1/audio/speech" -o out.wav
```

**Point the SDK at this server** (also works for kokoro-fastapi clients):

```python
from openai import OpenAI
client = OpenAI(api_key="ignored", base_url="http://localhost:9666/openai/v1")
client.audio.speech.create(model="tts-1", voice="alloy", input="hello world")
```

---

### Coqui (`/coqui`)

**Upstream:** [coqui-ai/TTS](https://github.com/coqui-ai/TTS) `server` API.

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/coqui/api/tts` | Synthesize speech (returns WAV) |

Query parameters:

| Name | Type | Notes |
| :--- | :--- | :--- |
| `text` | str (required) | Text to synthesize |
| `speaker_id` | str | Mapped to `voice=` |
| `language_id` | str | Mapped to `lang=` |

Always returns `audio/wav` (no format conversion).

```bash
curl "http://localhost:9666/coqui/api/tts?text=hello%20world&language_id=en" -o out.wav
```

---

### Google Cloud TTS (`/google-tts`)

**Upstream:** [google-cloud-texttospeech](https://github.com/googleapis/google-cloud-python) ·
[REST reference](https://cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/google-tts/v1/text:synthesize` | Synthesize speech |

**Auth:** `key` query param or `Authorization` header (accepted, ignored).

JSON body (Google `SynthesizeSpeech` shape):

| Field | Notes |
| :--- | :--- |
| `input.text` / `input.ssml` | Text or SSML to synthesize (`ssml` wins) |
| `voice.languageCode` | Default `en-US`, mapped to `lang=` |
| `voice.name` | Mapped to `voice=` |
| `voice.ssmlGender` | Accepted, not forwarded |
| `audioConfig.audioEncoding` | `MP3`→mp3, `LINEAR16`→wav, `OGG_OPUS`→ogg, `MULAW`/`ALAW`→wav |
| `audioConfig.speakingRate` / `pitch` / `volumeGainDb` / `sampleRateHertz` | Accepted, not forwarded |

Response is JSON with the audio as base64 in `audioContent` (matching Google's API):

```json
{ "audioContent": "<base64-encoded audio>" }
```

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"input": {"text": "hello world"},
       "voice": {"languageCode": "en-US"},
       "audioConfig": {"audioEncoding": "MP3"}}' \
  "http://localhost:9666/google-tts/v1/text:synthesize"
```

> The official `google-cloud-texttospeech` SDK defaults to gRPC over TLS and
> can't be repointed at a plaintext local server; use the REST endpoint above
> directly (any HTTP client) or a TLS-terminating reverse proxy.

---

### Amazon Polly (`/amazon-polly`)

**Upstream:** [boto3 Polly](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/polly.html) ·
[SynthesizeSpeech API](https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html) ·
[DescribeVoices API](https://docs.aws.amazon.com/polly/latest/dg/API_DescribeVoices.html)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/amazon-polly/v1/speech` | Synthesize speech |
| GET | `/amazon-polly/v1/voices` | List voices (`DescribeVoices`) |

**Auth:** AWS SigV4 `Authorization` header (accepted, ignored).

JSON body (Polly `SynthesizeSpeech` shape):

| Field | Type | Notes |
| :--- | :--- | :--- |
| `Text` | str (required) | Text to synthesize |
| `VoiceId` | str | Default `Joanna`, mapped to `voice=` |
| `OutputFormat` | str | `mp3`→mp3, `ogg_vorbis`→ogg, `pcm`→wav, `json`→mp3 |
| `LanguageCode` | str | Mapped to `lang=` |
| `Engine` / `TextType` / `SampleRate` |, | Accepted, not forwarded |

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"Text": "hello world", "VoiceId": "Joanna", "OutputFormat": "mp3"}' \
  "http://localhost:9666/amazon-polly/v1/speech" -o out.mp3
```

`GET /v1/voices` returns the plugin's voices in the Polly `Voice` shape. If the plugin lists no voices, it returns one voice with the ID `default`. Each voice has the plugin's default language as `LanguageCode` and the plugin's other languages as `AdditionalLanguageCodes`. `LanguageCode` filters the list. A language the plugin lists without a region, such as `de`, matches a request for any region of it, such as `de-DE`. `IncludeAdditionalLanguageCodes=true` also matches the additional languages. `Engine` and `NextToken` are accepted and ignored.

ovos-tts-plugin-polly checks the voice against `DescribeVoices`. It rejects a per-call voice that is not listed. A configured voice that is not listed, such as `Joanna`, falls back to the first listed voice. Clients that send `VoiceId` without a check, such as boto3 `synthesize_speech`, can use any name.

---

### Azure TTS (`/azure-tts`)

**Upstream:** [azure-cognitiveservices-speech](https://pypi.org/project/azure-cognitiveservices-speech/) ·
[REST reference](https://learn.microsoft.com/azure/ai-services/speech-service/rest-text-to-speech)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/azure-tts/cognitiveservices/v1` | Synthesize speech from SSML |

**Auth:** `Ocp-Apim-Subscription-Key` header (accepted, ignored).

The request body is raw **SSML**. The router extracts the voice from
`<voice name="...">` (→ `voice=`) and the language from `xml:lang="..."` (→ `lang=`),
then synthesizes the stripped text. The output container is chosen from the
`X-Microsoft-OutputFormat` header: values containing `mp3` → mp3,
`pcm`/`wav`/`riff` → wav, `ogg`/`opus` → ogg (default mp3).

```bash
curl -X POST \
  -H "Ocp-Apim-Subscription-Key: ignored" \
  -H "Content-Type: application/ssml+xml" \
  -H "X-Microsoft-OutputFormat: audio-16khz-128kbitrate-mono-mp3" \
  -d '<speak version="1.0" xml:lang="en-US"><voice name="en-US-JennyNeural">hello world</voice></speak>' \
  "http://localhost:9666/azure-tts/cognitiveservices/v1" -o out.mp3
```

#### WebSocket bridge (optional)

`ovos_tts_server.routers.azure_ws.make_azure_ws_router()` provides a WebSocket
endpoint (`/azure-tts/cognitiveservices/websocket/v1`) compatible with the Azure
Speech SDK's `speak_text_async()` / `speak_ssml_async()` calls. It is **not**
registered by default, include it in your own app if you need it:

```python
from ovos_tts_server import start_tts_server
from ovos_tts_server.routers.azure_ws import make_azure_ws_router

app, engine = start_tts_server("ovos-tts-plugin-piper")
app.include_router(make_azure_ws_router(engine))
```

---

### MaryTTS (`/marytts`)

Exposes the classic [MaryTTS](http://mary.dfki.de/) HTTP endpoints so apps that
already speak MaryTTS, notably **accessibility / assistive tech** and Home
Assistant's `marytts` integration, can swap in OVOS without code changes. There
is no canonical Python SDK; clients hand-roll HTTP.

**Upstream:** [marytts/marytts `MaryHttpServer.java`](https://github.com/marytts/marytts/blob/master/marytts-runtime/src/main/java/marytts/server/http/MaryHttpServer.java) ·
[`InfoRequestHandler.java`](https://github.com/marytts/marytts/blob/master/marytts-runtime/src/main/java/marytts/server/http/InfoRequestHandler.java) (defines `/process`, `/voices`, `/locales`) ·
[Home Assistant client](https://github.com/home-assistant/core/blob/dev/homeassistant/components/marytts/tts.py)

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/marytts/locales` | Newline-separated supported locales, as Java locales (`en_US`) |
| GET | `/marytts/voices` | Newline-separated voices (`name locale gender plugin`) |
| GET/POST | `/marytts/process` | Synthesize, returns `audio/wav` |

**Root-path aliases.** MaryTTS predates modern API gateways and is widely used by
assistive software that hardcodes bare paths, so the same three endpoints are
**also exposed at the server root** (`/locales`, `/voices`, `/process`) for
drop-in compatibility. Prefer the `/marytts/...` paths in new code.

`/marytts/process` parameters:

| Name | Type | Notes |
| :--- | :--- | :--- |
| `INPUT_TEXT` | str (required) | Text or SSML to synthesize |
| `INPUT_TYPE` | `TEXT` \| `SSML` | Default `TEXT` |
| `LOCALE` | str | Java locale (`en_US`), matched to a plugin language; see the MaryTTS stories |
| `VOICE` | str | Underscores → spaces, mapped to `voice=` |
| `OUTPUT_TYPE` / `AUDIO` | str | Accepted, ignored (always `AUDIO` / `WAVE_FILE`) |

```bash
curl http://localhost:9666/marytts/locales
curl http://localhost:9666/marytts/voices

curl -G http://localhost:9666/marytts/process \
  --data-urlencode "INPUT_TEXT=hello world" \
  --data-urlencode "LOCALE=en_US" \
  -o out.wav
```

**Home Assistant** (`configuration.yaml`), the built-in integration hardcodes
the bare paths, so point it straight at the server; the root-alias router handles
`/process`, `/voices`, `/locales`:

```yaml
tts:
  - platform: marytts
    host: localhost
    port: 9666
```

---

### Cartesia (`/cartesia`)

**Upstream:** [cartesia-ai/cartesia-python](https://github.com/cartesia-ai/cartesia-python) ·
[API reference](https://docs.cartesia.ai/)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/cartesia/tts/bytes` | Synthesize speech |

**Auth:** `X-API-Key` / `Cartesia-Version` headers (accepted, ignored).

JSON body:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `transcript` | str (required) | Text to synthesize |
| `model_id` | str | Default `sonic-english`, accepted, not forwarded |
| `voice` | object | `id` is mapped to `voice=`, other keys ignored |
| `output_format` | object | `container` selects the output: `wav`, `mp3`, or `raw` (→ PCM/WAV) |

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"model_id": "sonic-english", "transcript": "hello world",
       "output_format": {"container": "wav"}}' \
  "http://localhost:9666/cartesia/tts/bytes" -o out.wav
```

**Point the SDK at this server:**

```python
from cartesia import Cartesia
client = Cartesia(api_key="ignored", base_url="http://localhost:9666/cartesia")
audio = b"".join(client.tts.bytes(
    model_id="sonic-2",
    transcript="hello world",
    voice={"mode": "id", "id": "default"},
    output_format={"container": "wav", "sample_rate": 22050, "encoding": "pcm_s16le"},
))
```

---

### Deepgram Aura (`/deepgram`)

**Upstream:** [deepgram/deepgram-python-sdk](https://github.com/deepgram/deepgram-python-sdk) ·
[Aura TTS reference](https://developers.deepgram.com/reference/text-to-speech-api/speak)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/deepgram/v1/speak` | Synthesize speech |

**Auth:** `Authorization` header (accepted, ignored).

The model is a query parameter and the text is a JSON body:

| Parameter | In | Notes |
| :--- | :--- | :--- |
| `model` | query | Default `aura-asteria-en`, mapped to `voice=` |
| `encoding` | query | `linear16`/`mulaw`→wav, `mp3`→mp3, `opus`→ogg, `flac`→flac |
| `sample_rate` | query | Accepted, not forwarded |
| `text` | body | Required text to synthesize (`{"text": "..."}`) |

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "hello world"}' \
  "http://localhost:9666/deepgram/v1/speak?model=aura-asteria-en&encoding=linear16" -o out.wav
```

**Point the SDK at this server** via a custom base URL:

```python
from deepgram import DeepgramClient, DeepgramClientOptions, SpeakOptions
opts = DeepgramClientOptions(api_key="ignored", url="http://localhost:9666/deepgram")
client = DeepgramClient("ignored", opts)
client.speak.rest.v("1").save("out.wav", {"text": "hello world"},
                              SpeakOptions(model="aura-asteria-en", encoding="linear16"))
```

---

### PlayHT (`/playht`)

**Upstream:** [playht/pyht](https://github.com/playht/pyht) ·
[API reference](https://docs.play.ht/reference/api-getting-started)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/playht/api/v2/tts/stream` | Synthesize speech |
| POST | `/playht/api/v4/sdk-auth` | Inference-coordinates handshake for the `pyht` SDK |

**Auth:** `Authorization` / `X-USER-ID` headers (accepted, ignored).

`/api/v2/tts/stream` body:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `text` | str **or** list[str] | Text to synthesize (the SDK sends a single-element list) |
| `voice` | str | Mapped to `voice=` |
| `output_format` | str | `mp3`/`wav`/`ogg`/`flac`, `raw`→PCM, `mulaw`→wav |
| `quality` / `speed` / `sample_rate` |, | Accepted, not forwarded |

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "hello world", "voice": "default", "output_format": "wav"}' \
  "http://localhost:9666/playht/api/v2/tts/stream" -o out.wav
```

#### Using the official `pyht` SDK

`pyht`'s HTTP path first calls `{api_url}/sdk-auth` to fetch "inference
coordinates" (per-model streaming URLs), then POSTs to the returned URL. The
`/api/v4/sdk-auth` endpoint implements that handshake and points the SDK back at
this server, so a stock `pyht.Client` works by overriding only its coordinates
`api_url`. Use the HTTP protocol with `auto_connect=False` so the SDK never
contacts play.ht's gRPC lease/warmup endpoints:

```python
from pyht import Client, TTSOptions
from pyht.client import Format
from pyht.inference_coordinates import InferenceCoordinatesOptions

client = Client(
    user_id="ignored",
    api_key="ignored",
    auto_connect=False,
    advanced=Client.AdvancedOptions(
        inference_coordinates_options=InferenceCoordinatesOptions(
            api_url="http://localhost:9666/playht/api/v4",
        ),
    ),
)
opts = TTSOptions(voice="default", format=Format.FORMAT_WAV)
audio = b"".join(client.tts("hello world", opts, voice_engine="Play3.0-mini", protocol="http"))
client.close()
```

---

### How parameters reach the plugin

Every router boils its vendor-specific request down to two optional kwargs,
`voice=` and `lang=`, passed to `engine.synthesize(text, **kwargs)`. Parameters
a plugin can't act on (speed, pitch, model id, voice settings, ...) are accepted
for wire-compatibility and ignored. See [configuration.md](configuration.md) for
the full flow.


## Deployment

The server listens on port 9666 by default. Put it behind a reverse proxy that checks the API key, because the server itself accepts any key.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| A non-WAV `response_format` returns WAV | The `audio` extra is not installed | `pip install "ovos-tts-server[audio]"` |
| `ovos-tts-plugin-marytts` says `unsupported voice` | The configured voice is not in `/voices` | Set `voice` to a name from `GET /marytts/voices` |
| `ovos-tts-plugin-marytts` says `unsupported language 'en-US'` | Plugin version before 0.2.0a6 | Upgrade the plugin |
| MaryTTS `/process` answers 500 `produced no audio` | The plugin cannot speak `LOCALE` | Use a locale from `GET /marytts/locales` |
| ElevenLabs SDK 3 fails to list voices | SDK 3 calls `GET /v2/voices` | Use the SDK below 3, or call `text_to_speech.convert` with a known `voice_id` |
| The `/voices` gender column is `m` for every voice | OVOS plugins do not report a gender | None; MaryTTS clients that use the column get `m` |

---
[← Configuration](configuration.md) · [Home](index.md) · [Transformers →](transformers.md)
