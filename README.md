# Hermes Local LLM Polished STT

A Hermes Agent STT plugin for people who want **fast, cheap local voice transcription** without the messy transcripts that small Whisper models can produce.

It registers a new speech-to-text provider:

```yaml
stt:
  provider: local_llm_polished
```

## Use case

Small local `faster-whisper` models such as `base` are great for always-on voice messages: they are fast, private, and cheap. But they often mangle:

- mixed-language speech
- punctuation and casing
- acronyms and product names
- developer / technical vocabulary
- commands, file names, and proper nouns

This plugin keeps the local STT path, then runs a short LLM cleanup pass before Hermes acts on the transcript.

```text
voice/audio → local faster-whisper → LLM transcript polish → Hermes agent
```

If the LLM polish step fails, the raw local transcript is returned instead.

## Why not just use a bigger Whisper model?

You can, and sometimes you should. This plugin is for the middle ground:

- keep `tiny` / `base` / `small` local STT for speed and low RAM
- improve readability and technical-term accuracy with a bounded LLM call
- keep the built-in Hermes `local` provider untouched as an easy fallback

## Install

Copy the plugin directory into your Hermes profile:

```bash
mkdir -p ~/.hermes/plugins/local-llm-polished
cp -r local-llm-polished/* ~/.hermes/plugins/local-llm-polished/
```

For a named Hermes profile:

```bash
mkdir -p ~/.hermes/profiles/developer/plugins/local-llm-polished
cp -r local-llm-polished/* ~/.hermes/profiles/developer/plugins/local-llm-polished/
```

Enable it in `config.yaml`:

```yaml
plugins:
  enabled:
    - local-llm-polished

stt:
  enabled: true
  provider: local_llm_polished

  # Keep the normal local provider config as an easy fallback.
  local:
    model: base
    language: en

  # Same basic interface as local, plus a polish block.
  local_llm_polished:
    model: base
    language: en
    polish:
      enabled: true
      provider: default
      model: gpt-5.5
      reasoning_effort: low
      timeout: 60
      prompt: |
        You are a transcript polishing step for a voice-enabled AI assistant.
        You receive raw speech-to-text output from a small, fast local ASR model.
        Produce a cleaner transcript before the assistant acts on it.
        Preserve the user's language, intent, tone, and level of detail.
        Fix only obvious ASR/STT mistakes. Do not answer the user.
        Return only the polished transcript text.
```

Restart Hermes after changing plugin or STT config:

```bash
hermes gateway restart
```

For a named profile:

```bash
hermes -p developer gateway restart
```

## Provider names

- Plugin name: `local-llm-polished`
- STT provider name: `local_llm_polished`
- Display name: `Local LLM Polished STT`

`local_llm_polished` intentionally uses a separate provider name because Hermes built-in STT provider names cannot be shadowed by plugins. Switching back is simple:

```yaml
stt:
  provider: local
```

## Requirements

- Hermes Agent with STT plugin-provider support
- `faster-whisper` available for local STT
- an LLM provider configured in Hermes if `polish.enabled: true`

## License

MIT
