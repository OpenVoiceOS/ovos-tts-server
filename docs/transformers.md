# Transformer Pipelines

The server can run OVOS transformer plugins around synthesis. Both hooks live in the engine wrapper, so every surface gets them: native endpoints, all vendor-compat routers, the websocket streaming routes, MCP, and UTCP.

- **Dialog transformers** rewrite the utterance text before synthesis.
- **TTS transformers** post-process the synthesized audio before the server serves it. They run on a temporary copy. The plugin's audio cache is never mutated, so cache hits never serve pre-transformed audio.

## Configuration

Loading is config-gated and opt-in, through the standard mycroft.conf sections. With no config, the server behaves exactly as before:

```json
{
  "dialog_transformers": {
    "ovos-dialog-transformer-openai-plugin": {"rewrite_prompt": "rewrite the text as if you were explaining it to a 5 year old"}
  },
  "tts_transformers": {
    "ovos-tts-transformer-sox-plugin": {"pitch": 300}
  }
}
```

Chains run in ascending priority order (OVOS-TRANSFORM §4). An explicit `"order"` list in a section wins over priorities. See the [ovos-plugin-manager transformer docs](https://github.com/OpenVoiceOS/ovos-plugin-manager/blob/dev/docs/transformers.md) for the full contract.

## When to use a transformer

A dialog transformer on the server means the server synthesizes different text than the client sent. From the client's perspective that is unexpected: a request for "the CPU is at 95 percent" comes back as audio saying something else. Enable one on purpose, for a clear reason:

- **Global tone or persona.** Enable one dialog transformer here and every device, app, and vendor-SDK client that synthesizes through this server gets the same voice personality, fleet-wide, with no client changes.
- **Global audio post-processing.** A tts transformer here applies the same effect (pitch, speed, loudness normalization) to every response.

If the effect should instead apply per device (one speaker needs a boost, one room needs a different pitch), run the transformer on that device (ovos-audio or a HiveMind satellite), not here. Never enable the same plugin on both sides, or the server applies it twice.

Dialog transformation happens before the TTS cache, so the cache keys on the transformed text and stays consistent.

---
[← API Compatibility](api-compatibility.md) · [Home](index.md) · [Audio Formats →](audio-formats.md)
