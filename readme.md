# OpenVoiceOS TTS Server

Turn any OVOS TTS plugin into a micro service!


## Install

`pip install ovos-tts-server`

## Companion plugin

Use in your voice assistant with OpenVoiceOS [companion plugin](https://github.com/OpenVoiceOS/ovos-tts-server-plugin)

## Configuration

the plugin is configured just like if it was running in the assistant, under mycroft.conf

eg
```
 "tts": {
    "module": "ovos-tts-plugin-piper",
    "ovos-tts-plugin-piper": {
      "model": "alan-low"
    }
  }
```

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

eg, to use the [GladosTTS plugin](https://github.com/NeonGeckoCom/neon-tts-plugin-glados) `ovos-tts-server --engine neon-tts-plugin-glados --cache`

then do a get request `http://192.168.1.112:9666/synthesize/hello`


## Docker

you can create easily crete a docker file to serve any plugin

```dockerfile
FROM python:3.7

RUN pip3 install ovos-utils==0.0.15
RUN pip3 install ovos-plugin-manager==0.0.4
RUN pip3 install ovos-tts-server==0.0.1

RUN pip3 install {PLUGIN_HERE}

ENTRYPOINT ovos-tts-server --engine {PLUGIN_HERE} --cache
```

build it
```bash
docker build . -t my_ovos_tts_plugin
```

run it
```bash
docker run -p 8080:9666 my_ovos_tts_plugin
```

use it `http://localhost:8080/synthesize/hello`

Each plugin can provide its own Dockerfile in its repository using ovos-tts-server