# Transformer Pipelines

The server can run OVOS transformer plugins around synthesis. Both hooks
live in the engine wrapper, so **every** surface gets them: native
endpoints, all vendor-compat routers, the websocket streaming routes, MCP
and UTCP.

- **Dialog transformers** rewrite the utterance *text* before synthesis.
- **TTS transformers** post-process the synthesized *audio* before it is
  served. They run on a temp copy — the plugin's audio cache is never
  mutated, so cache hits are never served pre-transformed audio.

## Configuration

Loading is config-gated and opt-in via the standard mycroft.conf sections;
with no config the server behaves exactly as before:

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

Chains run in ascending priority order (OVOS-TRANSFORM §4); an explicit
`"order"` list in a section wins over priorities. See the
[ovos-plugin-manager transformer docs](https://github.com/OpenVoiceOS/ovos-plugin-manager/blob/dev/docs/transformers.md)
for the full contract.

## When to use — and the surprise factor

A dialog transformer on the *server* means the server synthesizes
**different text than the client sent**. From the client's perspective that
is unexpected — a request for "the CPU is at 95 percent" comes back as
audio saying something else. Do it on purpose:

- **Global tone/persona**: enable one dialog transformer here and every
  device, app and vendor-SDK client that synthesizes through this server
  gets the same voice personality, fleet-wide, with zero client changes.
- **Global audio post-processing**: a tts transformer here applies the same
  effect (pitch, speed, loudness normalization) to every response.

If instead the effect should be **per-device** (one speaker needs a boost,
one room needs a different pitch), run the transformer on that device
(ovos-audio or a HiveMind satellite), not here — and never enable the same
plugin on both sides, or it is applied twice.

Note for the caching-inclined: dialog transformation happens *before* the
TTS cache, so the cache keys on the transformed text and stays consistent.
