FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "ovos-tts-server[audio]" \
                               ovos-tts-plugin-server

ENV XDG_CONFIG_HOME=/config
WORKDIR /app

EXPOSE 9666

ENTRYPOINT ["ovos-tts-server", "--host", "0.0.0.0", "--port", "9666"]
