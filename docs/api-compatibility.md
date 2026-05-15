# API Compatibility Reference

`ovos-tts-server` exposes its underlying OVOS TTS plugin behind drop-in
compatibility endpoints for popular cloud TTS APIs. Each vendor lives
under its own URL prefix so multiple compat layers coexist with no path
collisions.

All routers accept any auth token / API key from the client and silently
ignore it — authentication is the responsibility of your reverse proxy.

Audio format conversion is provided by `ovos_tts_server.audio_utils.convert_audio()`.
Install the `[audio]` extra (`pip install ovos-tts-server[audio]`) to enable
non-WAV outputs via `pydub`.

This document currently covers: **Amazon Polly (`/amazon-polly`)**.
Other vendor sections are added by their respective compat-router PRs.

---

## Amazon Polly (`/amazon-polly`)

**Upstream sources**:
- boto3 client: [boto3 Polly `synthesize_speech` docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/polly/client/synthesize_speech.html)
- Service model: [botocore — `data/polly/.../service-2.json`](https://github.com/boto/botocore/blob/develop/botocore/data/polly/2016-06-10/service-2.json)
- API reference: [Amazon Polly SynthesizeSpeech](https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html)


| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/amazon-polly/v1/speech` | Synthesize speech |

**Auth:** `Authorization` header with AWS SigV4 (accepted, ignored).

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"Text": "hello world", "VoiceId": "Joanna", "OutputFormat": "mp3"}' \
  http://localhost:9666/amazon-polly/v1/speech \
  -o out.mp3
```

`OutputFormat` values: `mp3`, `ogg_vorbis`, `pcm`, `json` (json → WAV stub).

---

### Pointing apps at this server

AWS SDKs honour the `AWS_ENDPOINT_URL` env var (and `endpoint_url=` constructor arg) to redirect to a custom host. Point it at `http://localhost:9666/amazon-polly`.

**boto3** ([`amazon-polly`](https://docs.aws.amazon.com/polly/latest/dg/API_SynthesizeSpeech.html)):
```python
import boto3
polly = boto3.client(
    "polly",
    endpoint_url="http://localhost:9666/amazon-polly",
    aws_access_key_id="ignored", aws_secret_access_key="ignored",
    region_name="us-east-1",
)
audio = polly.synthesize_speech(Text="hello", VoiceId="Joanna", OutputFormat="mp3")
open("out.mp3", "wb").write(audio["AudioStream"].read())
```

**Environment variable** (auto-picked by all AWS SDKs):
```bash
export AWS_ENDPOINT_URL=http://localhost:9666/amazon-polly
```

**curl**:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"Text":"hello","VoiceId":"Joanna","OutputFormat":"mp3"}' \
  http://localhost:9666/amazon-polly/v1/speech -o out.mp3
```
