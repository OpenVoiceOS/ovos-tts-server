# OpenVoiceOS TTS Server

Turn any OVOS TTS plugin into a micro service!

## Install

`pip install ovos-tts-server`

## Usage

```bash
ovos-tts-server --help
usage: ovos-tts-server [-h] [--engine ENGINE] [--port PORT] [--host HOST] [--cache]

options:
  -h, --help       show this help message and exit
  --engine ENGINE  tts plugin to be used
  --port PORT      port number
  --host HOST      host
  --cache          save every synth to disk
```

eg, to use the GladosTTS plugin `ovos-tts-server --engine neon-tts-plugin-glados --cache`

then do a get request `http://192.168.1.112:9666/synthesize/your text goes here`

## Companion plugin

coming soon - companion plugin to point to a ovos-tts-server instance

## Docker

coming soon - sample docker file

Each plugin can provide its own Dockerfile in its repository using this repository