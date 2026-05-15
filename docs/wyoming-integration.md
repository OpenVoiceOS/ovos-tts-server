# Wyoming integration (TTS)

The [Wyoming protocol](https://github.com/rhasspy/wyoming) is Home Assistant's
length-prefixed JSONL framing for STT / TTS / wake-word over raw TCP. It is
**not** an HTTP API and is **not** implemented as a router in this server.

## Why not native?

- Wyoming uses raw TCP framing on port 10200 (TTS) / 10300 (STT), not
  HTTP — it does not fit the FastAPI router model the rest of
  `ovos-tts-server` uses.
- Dedicated bridge servers already exist and are kept in sync with
  upstream Wyoming (which evolves independently of our HTTP compat layer).

## Use the adapter repo

The OVOS-side bridge speaks Wyoming on its native TCP port and forwards
to a backend service — point it at this server's `/v2/synthesize`
endpoint and Home Assistant Voice / Voice PE picks it up transparently.

| Adapter | Repo | Backend it bridges |
| :--- | :--- | :--- |
| Wyoming TTS  | [TigreGotico/wyoming-ovos-tts](https://github.com/TigreGotico/wyoming-ovos-tts) | Any OVOS TTS plugin, or **this server's** `/v2/synthesize` endpoint |

The STT and wake-word counterparts live in:
- [TigreGotico/wyoming-ovos-stt](https://github.com/TigreGotico/wyoming-ovos-stt)
- [TigreGotico/wyoming-ovos-wakeword](https://github.com/TigreGotico/wyoming-ovos-wakeword)

## Typical deployment

```text
  ┌─────────────────────────┐         ┌──────────────────────────┐
  │  Home Assistant Voice   │  TCP    │  wyoming-ovos-tts        │
  │  (wyoming client)       ├────────►│  (port 10200)            │
  └─────────────────────────┘         └────────────┬─────────────┘
                                                   │ HTTP
                                                   ▼
                                       ┌──────────────────────────┐
                                       │  ovos-tts-server         │
                                       │  /v2/synthesize          │
                                       │  (port 9666)             │
                                       └──────────────────────────┘
```

Run both on the same box (or split them across hosts):

```bash
# 1. The TTS engine
ovos-tts-server --engine ovos-tts-plugin-piper --port 9666

# 2. The Wyoming bridge — point it at our HTTP endpoint
wyoming-ovos-tts --uri tcp://0.0.0.0:10200 --tts-url http://localhost:9666
```

Configure HA's Wyoming integration with `tcp://<host>:10200` and the
voice pipeline picks up a normal Wyoming TTS service — no special-casing
for OVOS.
