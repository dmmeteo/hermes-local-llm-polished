"""Local LLM Polished STT provider for Hermes.

Registers ``local_llm_polished`` as a speech-to-text provider. It mirrors the
built-in ``local`` faster-whisper provider (model/language config), then
optionally sends the raw transcript through a bounded LLM polish step before
returning it to Hermes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from agent.transcription_provider import TranscriptionProvider

logger = logging.getLogger(__name__)

PROVIDER_NAME = "local_llm_polished"

DEFAULT_PROMPT = """You are a transcript polishing step for a voice-enabled AI assistant.
You receive raw speech-to-text output from a small, fast local ASR model.
Produce a cleaner transcript before the assistant acts on it.
Detect the user's language automatically and preserve it. Do not translate.
Preserve the user's intent, tone, informality, and level of detail.
Fix only obvious ASR/STT mistakes: broken words, punctuation, spacing, casing, homophones, and misrecognized names, acronyms, commands, or technical terms.
When the transcript mixes languages, keep that mix and restore likely borrowed words or proper nouns in their conventional spelling.
Use surrounding context inside the transcript to infer likely corrections, but do not invent new requests, facts, names, options, or details.
Do not answer the user. Do not explain your changes. Return only the polished transcript text."""


def _cfg_get(config: Dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = config
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _load_stt_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
    except Exception:
        return {}
    stt = cfg.get("stt") if isinstance(cfg, dict) else None
    return stt if isinstance(stt, dict) else {}


class LocalLlmPolishedProvider(TranscriptionProvider):
    @property
    def name(self) -> str:
        return PROVIDER_NAME

    @property
    def display_name(self) -> str:
        return "Local LLM Polished STT"

    def list_models(self):
        return [
            {"id": "tiny", "display": "faster-whisper tiny"},
            {"id": "base", "display": "faster-whisper base"},
            {"id": "small", "display": "faster-whisper small"},
            {"id": "medium", "display": "faster-whisper medium"},
            {"id": "large-v3", "display": "faster-whisper large-v3"},
            {"id": "large-v3-turbo", "display": "faster-whisper large-v3-turbo"},
        ]

    def default_model(self) -> Optional[str]:
        return "base"

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": self.display_name,
            "badge": "local+LLM",
            "tag": "Local faster-whisper plus optional LLM transcript polishing",
            "env_vars": [],
        }

    def _provider_config(self, stt_config: Dict[str, Any]) -> Dict[str, Any]:
        cfg = stt_config.get(PROVIDER_NAME)
        return cfg if isinstance(cfg, dict) else {}

    def _effective_model(self, model: Optional[str], provider_cfg: Dict[str, Any], stt_config: Dict[str, Any]) -> str:
        configured = model or provider_cfg.get("model") or _cfg_get(stt_config, "local", "model") or self.default_model()
        try:
            from tools.transcription_tools import _normalize_local_model

            return _normalize_local_model(configured)
        except Exception:
            return str(configured or "base")

    def _effective_language(self, language: Optional[str], provider_cfg: Dict[str, Any], stt_config: Dict[str, Any]) -> Optional[str]:
        configured = language or provider_cfg.get("language") or _cfg_get(stt_config, "local", "language")
        try:
            from tools.transcription_tools import _normalize_stt_language

            return _normalize_stt_language(configured)
        except Exception:
            return str(configured).strip() if configured else None

    def _transcribe_local(self, file_path: str, model_name: str, language: Optional[str]) -> Dict[str, Any]:
        try:
            # Reuse Hermes' local faster-whisper implementation so behavior stays
            # close to the built-in local provider. If Hermes later starts passing
            # language into this private helper, the fallback path below remains safe.
            from tools.transcription_tools import _transcribe_local

            result = _transcribe_local(file_path, model_name)
        except Exception as exc:
            logger.warning("local_llm_polished local transcription failed: %s", exc)
            return {
                "success": False,
                "transcript": "",
                "provider": PROVIDER_NAME,
                "error": f"Local transcription failed: {exc}",
            }

        if isinstance(result, dict):
            result = dict(result)
            result.setdefault("provider", PROVIDER_NAME)
            # Preserve compatibility if the built-in reports provider='local', but
            # mark this provider as the one that serviced the Hermes request.
            result["provider"] = PROVIDER_NAME
            return result
        return {
            "success": False,
            "transcript": "",
            "provider": PROVIDER_NAME,
            "error": "Local transcription returned an invalid result.",
        }

    def _polish_enabled(self, polish_cfg: Dict[str, Any]) -> bool:
        enabled = polish_cfg.get("enabled", True)
        if isinstance(enabled, bool):
            return enabled
        return str(enabled).strip().lower() not in {"0", "false", "no", "off"}

    def _polish(self, transcript: str, polish_cfg: Dict[str, Any]) -> str:
        raw = (transcript or "").strip()
        if not raw or not self._polish_enabled(polish_cfg):
            return transcript

        provider = polish_cfg.get("provider") or None
        if provider == "default":
            provider = "main"
        model = polish_cfg.get("model") or None
        timeout = polish_cfg.get("timeout", 60)
        try:
            timeout = float(timeout)
        except Exception:
            timeout = 60.0

        prompt = str(polish_cfg.get("prompt") or "").strip() or DEFAULT_PROMPT
        effort = str(polish_cfg.get("reasoning_effort") or "low").strip().lower()
        extra_body = dict(polish_cfg.get("extra_body") or {})
        if effort:
            extra_body.setdefault("reasoning", {"enabled": True, "effort": effort})

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Polish this transcript only:\n\n" + raw},
        ]

        try:
            from agent.auxiliary_client import call_llm

            started = time.monotonic()
            response = call_llm(
                task="stt_polish",
                provider=provider,
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=None,
                timeout=timeout,
                extra_body=extra_body,
            )
            polished = (response.choices[0].message.content or "").strip()
            if polished:
                logger.info("local_llm_polished polished transcript in %.2fs", time.monotonic() - started)
                return polished
        except Exception as exc:
            logger.warning("local_llm_polished polish failed; keeping raw transcript: %s", exc)
        return transcript

    def transcribe(
        self,
        file_path: str,
        *,
        model: Optional[str] = None,
        language: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        stt_config = _load_stt_config()
        provider_cfg = self._provider_config(stt_config)
        model_name = self._effective_model(model, provider_cfg, stt_config)
        lang = self._effective_language(language, provider_cfg, stt_config)

        result = self._transcribe_local(file_path, model_name, lang)
        if not result.get("success"):
            return result

        raw = result.get("transcript") or ""
        polish_cfg = provider_cfg.get("polish")
        if not isinstance(polish_cfg, dict):
            # Back-compat with the earlier prototype config name.
            polish_cfg = provider_cfg.get("repair")
        if not isinstance(polish_cfg, dict):
            polish_cfg = {}
        result["transcript"] = self._polish(raw, polish_cfg)
        result["provider"] = PROVIDER_NAME
        if lang:
            result.setdefault("language", lang)
        return result


def register(ctx):
    ctx.register_transcription_provider(LocalLlmPolishedProvider())
