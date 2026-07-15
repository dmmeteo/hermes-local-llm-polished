# Hermes Local LLM Polished STT

A Hermes Agent speech-to-text provider that mirrors the built-in local `faster-whisper` STT provider and adds an optional LLM transcript polishing step.

Provider name:

```yaml
stt:
  provider: local_llm_polished
```

## What it does

```text
audio → local faster-whisper → optional LLM polish → Hermes transcript
```

It is useful when a small local Whisper model is fast enough, but often mangles punctuation, casing, mixed-language text, acronyms, product names, or technical terms.

## Install

Copy the plugin directory into your Hermes profile:

```bash
mkdir -p ~/.hermes/plugins/local-llm-polished
cp -r local-llm-polished/* ~/.hermes/plugins/local-llm-polished/
```

For profile installs:

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

  local:
    model: base
    language: en

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

Restart your Hermes gateway/CLI after changing plugins or STT config.

## Notes

- The built-in `local` provider remains available.
- `local_llm_polished` intentionally uses a separate provider name because Hermes built-in STT provider names cannot be shadowed by plugins.
- If polishing fails, the raw local transcript is returned.
