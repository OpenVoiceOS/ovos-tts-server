# Voice Pihole (TTS)

A single network-layer interception recipe per cloud TTS vendor so that
**unmodified consumer apps stop calling cloud services** and land on your
`ovos-tts-server` box instead. No client SDK changes, no API key swaps,
no app-config edits — just DNS + a TLS-terminating reverse proxy.

The pattern across every vendor is the same:

1. **DNS interception.** Pin the vendor's hostname to your server's IP
   via `/etc/hosts` (single host) or your LAN's DNS (Pi-hole / Unbound /
   dnsmasq / pfSense / OPNsense).
2. **TLS termination.** Run nginx (or Caddy / HAProxy / Envoy) on `443`
   for the vendor's hostname, holding a cert your clients trust.
3. **Path rewrite.** Map the vendor's upstream path to our internal
   prefix so the rest of FastAPI's routing works.
4. **CA trust.** Either sign the proxy cert with a CA the client already
   trusts (corporate PKI, mkcert root) or push the CA into the client's
   trust store (`REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, system trust).

This document holds the consolidated config. Each per-vendor section in
[`api-compatibility.md`](api-compatibility.md) cross-references it.

> :warning: **Intercepting a hostname catches *every* request to it.** If
> the vendor host is shared with other features (e.g. OpenAI chat on
> `api.openai.com`), the nginx block must forward unrelated paths back to
> the upstream or 404 them explicitly. The examples below do this.

---

## Common nginx prelude

Every server block below assumes this `map` directive is in your
`nginx.conf` (or in a `conf.d/*.conf` snippet loaded into `http {}`):

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
```

It's needed any time a WS upgrade is forwarded.

---

## Cert + CA trust setup

For each hostname you intercept you need an X.509 cert with the vendor's
hostname in the SAN list. Two common approaches:

### A) Internal CA (production)

1. Generate an internal CA (e.g. via `step-ca`, `cfssl`, or `openssl`).
2. Install the CA cert in the client device's trust store (corporate
   MDM, dotfiles, system keychain, `update-ca-certificates`).
3. Issue per-hostname leaf certs from this CA.

### B) mkcert (lab / dev)

```bash
brew install mkcert  # or apt / scoop / cargo
mkcert -install
mkcert api.elevenlabs.io api.openai.com '*.googleapis.com' \
       polly.us-east-1.amazonaws.com \
       '*.tts.speech.microsoft.com'
```

mkcert installs its CA into the system trust automatically.

---

## Per-vendor nginx blocks

### ElevenLabs (`api.elevenlabs.io`)

```nginx
server {
    listen 443 ssl;
    server_name api.elevenlabs.io;
    ssl_certificate     /etc/ssl/private/api.elevenlabs.io.crt;
    ssl_certificate_key /etc/ssl/private/api.elevenlabs.io.key;

    location /v1/text-to-speech/ {
        proxy_pass         http://127.0.0.1:9666/elevenlabs/v1/text-to-speech/;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
    location /v1/voices {
        proxy_pass         http://127.0.0.1:9666/elevenlabs/v1/voices;
        proxy_set_header   Host $host;
    }
    location / { return 404; }
}
```

### OpenAI TTS (`api.openai.com`)

```nginx
server {
    listen 443 ssl;
    server_name api.openai.com;
    ssl_certificate     /etc/ssl/private/api.openai.com.crt;
    ssl_certificate_key /etc/ssl/private/api.openai.com.key;

    # Audio endpoints → /openai/v1/audio/*
    location /v1/audio/speech {
        proxy_pass         http://127.0.0.1:9666/openai/v1/audio/speech;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
    # Apps often probe /v1/models at startup; benign stub
    location /v1/models {
        return 200 '{"data":[]}';
        add_header Content-Type application/json;
    }
    location / { return 404; }
}
```

### Google Cloud TTS (`texttospeech.googleapis.com`)

```nginx
server {
    listen 443 ssl;
    server_name texttospeech.googleapis.com;
    ssl_certificate     /etc/ssl/private/texttospeech.googleapis.com.crt;
    ssl_certificate_key /etc/ssl/private/texttospeech.googleapis.com.key;

    location /v1/text:synthesize {
        proxy_pass         http://127.0.0.1:9666/google-tts/v1/text:synthesize;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
    location /v1/voices {
        proxy_pass         http://127.0.0.1:9666/google-tts/v1/voices;
        proxy_set_header   Host $host;
    }
    location / { return 404; }
}
```

### Amazon Polly (`polly.<region>.amazonaws.com`)

```nginx
server {
    listen 443 ssl;
    server_name ~^polly\.[a-z0-9-]+\.amazonaws\.com$;
    ssl_certificate     /etc/ssl/private/polly.amazonaws.com.crt;
    ssl_certificate_key /etc/ssl/private/polly.amazonaws.com.key;

    location /v1/speech {
        proxy_pass         http://127.0.0.1:9666/amazon-polly/v1/speech;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
    location /v1/voices {
        proxy_pass         http://127.0.0.1:9666/amazon-polly/v1/voices;
        proxy_set_header   Host $host;
    }
    location / { return 404; }
}
```

### Microsoft Azure TTS (`<region>.tts.speech.microsoft.com`, REST + WS)

```nginx
server {
    listen 443 ssl;
    server_name ~^[a-z0-9]+\.tts\.speech\.microsoft\.com$;
    ssl_certificate     /etc/ssl/private/tts.speech.microsoft.com.crt;
    ssl_certificate_key /etc/ssl/private/tts.speech.microsoft.com.key;

    # REST synth
    location /cognitiveservices/v1 {
        proxy_pass         http://127.0.0.1:9666/azure-tts/cognitiveservices/v1;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
    # WebSocket synth (Microsoft proprietary framing)
    location /cognitiveservices/websocket/v1 {
        proxy_pass         http://127.0.0.1:9666/azure-tts/cognitiveservices/websocket/v1;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection $connection_upgrade;
        proxy_set_header   Host $host;
        proxy_read_timeout 300s;
        proxy_buffering    off;
    }
    # Voices list
    location /cognitiveservices/voices/list {
        proxy_pass         http://127.0.0.1:9666/azure-tts/cognitiveservices/voices/list;
        proxy_set_header   Host $host;
    }
    location / { return 404; }
}
```

---

## Self-hosted TTS server replacement

For self-hosted protocols (Coqui, Piper, MaryTTS) the canonical move is
to **replace the running server on the same bind port**. Stop the old
process, start `ovos-tts-server` on the same port, clients keep working.

### Coqui TTS server (`coqui-ai/TTS` reference)

Coqui's bundled HTTP server defaults to `http://localhost:5002/api/tts`.
Run `ovos-tts-server --port 5002` and apps drop in unchanged. If you
prefer a separate port, add nginx:

```nginx
server {
    listen 5002;
    server_name _;

    location /api/tts {
        proxy_pass         http://127.0.0.1:9666/coqui/api/tts;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
}
```

### Piper HTTP server

Piper's HTTP server typically binds on `5000` or `8000`. Same pattern —
replace the bind port or add a path-preserving nginx:

```nginx
server {
    listen 5000;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:9666/piper/;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
}
```

### MaryTTS

MaryTTS clients typically post to `http://marytts:59125/process`. Our
`/marytts` router also exposes root aliases (`/process`, `/voices`,
`/version`) so legacy clients with hardcoded bare paths work. The DNS
move alone is enough:

```text
# /etc/hosts on the client (or LAN DNS)
192.168.1.50    marytts
```

If MaryTTS clients hit a hostname directly:

```nginx
server {
    listen 59125;
    server_name marytts;

    location / {
        proxy_pass         http://127.0.0.1:9666/marytts/;
        proxy_set_header   Host $host;
        proxy_buffering    off;
    }
}
```

---

## Putting it together

A complete "voice pihole" deployment is:

```
┌──────────────────────────────┐
│   Pi-hole / Unbound / pfSense│   1) DNS rewrites for all the hosts above
│   (LAN-wide DNS)             │
└──────────────┬───────────────┘
               │ resolves api.openai.com etc. → 192.168.1.50
               ▼
┌──────────────────────────────┐
│   nginx (192.168.1.50:443)   │   2) TLS termination + path rewrite
│   - one server{} per vendor  │   3) cert from a CA trusted on clients
└──────────────┬───────────────┘
               │ proxies to 127.0.0.1:9666/<vendor-prefix>/...
               ▼
┌──────────────────────────────┐
│   ovos-tts-server            │   4) compat router for each vendor
│   :9666 (HTTP)               │      → OVOS TTS plugin (the actual synth)
└──────────────────────────────┘
```

Once the DNS rewrite + TLS cert + reverse proxy are in place, **every**
consumer app on the LAN that uses any of the above APIs is automatically
served by your local OVOS TTS plugin — no client-side change required.
