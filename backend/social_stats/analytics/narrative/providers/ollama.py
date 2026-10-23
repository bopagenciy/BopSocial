"""
Ollama Local Narrative Provider Adapter.
Dispatches requests to local Ollama instance with timeout and structured JSON response parsing.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from social_stats.ai_helpers import parse_json_response
from ..prompts import build_user_prompt, get_system_prompt
from ..schemas import EXECUTIVE_NARRATIVE_JSON_SCHEMA
from .base import BaseNarrativeProvider, NarrativeProviderResult

logger = logging.getLogger(__name__)


def _clean_ollama_response_text(raw_text: str) -> str:
    """Strips thinking tags or outer markdown wrappers from model output."""
    s = (raw_text or "").strip()
    # Strip <think>...</think> tags if model emits reasoning tokens
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()
    return s


class OllamaNarrativeProvider(BaseNarrativeProvider):
    """
    Adapter for local Ollama models.
    """

    def __init__(
        self,
        model_name: str = "qwen3.5:9b",
        host: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name)
        configured_host = host or getattr(
            settings,
            "OLLAMA_HOST",
            "http://host.docker.internal:11434",
        )
        self.host = (configured_host or "http://host.docker.internal:11434").rstrip("/")
        self.mock_mode = kwargs.get("mock_mode")
        self.timeout = getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 90)

    def generate(
        self,
        context: Dict[str, Any],
        language: str = "es",
        style: str = "EXECUTIVE",
        **kwargs
    ) -> NarrativeProviderResult:
        if not getattr(settings, "ENABLE_LIVE_AI_NARRATIVE", False):
            raise RuntimeError("Live Ollama calls are strictly disabled in this environment.")

        system_prompt = get_system_prompt(language=language, style=style)
        user_prompt = build_user_prompt(context=context)

        payload = {
            "model": self.model_name or "qwen3.5:9b",
            "system": system_prompt,
            "prompt": user_prompt,
            "format": EXECUTIVE_NARRATIVE_JSON_SCHEMA,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.0,
            },
        }

        url = f"{self.host}/api/generate"
        logger.info("Dispatching live Ollama generation to %s [model=%s]", url, payload["model"])

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.exceptions.Timeout as e:
            logger.error("Ollama request timed out after %ds: %s", self.timeout, e)
            raise RuntimeError(f"Ollama request timed out after {self.timeout}s: {e}")
        except requests.exceptions.RequestException as e:
            logger.error("Ollama HTTP connection failed: %s", e)
            raise RuntimeError(f"Ollama HTTP connection failed: {e}")

        if resp.status_code != 200:
            logger.error("Ollama returned non-200 status %d: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        try:
            data = resp.json()
        except Exception as e:
            logger.error("Failed to decode Ollama response JSON: %s", e)
            raise RuntimeError(f"Failed to decode Ollama response JSON: {e}")

        thinking_val = data.get("thinking")
        thinking_present = bool(thinking_val and str(thinking_val).strip())

        raw_response_text = data.get("response")
        if raw_response_text is None or not str(raw_response_text).strip():
            logger.error(
                "Ollama response contained missing or empty 'response' field (thinking_present=%s)",
                thinking_present,
            )
            raise RuntimeError(
                f"EMPTY_FINAL_RESPONSE: Ollama returned empty response content (thinking_present={thinking_present})."
            )

        cleaned_text = _clean_ollama_response_text(str(raw_response_text))
        if not cleaned_text or not cleaned_text.strip():
            logger.error(
                "Ollama response content was empty after stripping reasoning tags (thinking_present=%s)",
                thinking_present,
            )
            raise RuntimeError(
                f"EMPTY_FINAL_RESPONSE: Ollama response content is empty after stripping reasoning tags (thinking_present={thinking_present})."
            )

        try:
            parsed_json = parse_json_response(cleaned_text)
        except Exception as e:
            logger.error("Failed to parse narrative JSON from Ollama output: %s", e)
            raise RuntimeError(f"Malformed JSON in Ollama narrative response: {e}")

        if not isinstance(parsed_json, dict):
            raise RuntimeError(f"Ollama narrative root must be a JSON object, got {type(parsed_json).__name__}")

        input_tokens = data.get("prompt_eval_count") or 0
        output_tokens = data.get("eval_count") or 0
        token_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

        metadata = {
            "done": data.get("done", True),
            "done_reason": data.get("done_reason", "stop"),
            "model": data.get("model", self.model_name or "qwen3.5:9b"),
            "total_duration_ns": data.get("total_duration", 0),
            "load_duration_ns": data.get("load_duration", 0),
            "eval_duration_ns": data.get("eval_duration", 0),
            "thinking_present": thinking_present,
        }

        return NarrativeProviderResult(
            raw_response=cleaned_text,
            parsed_json=parsed_json,
            provider_name="ollama",
            model_name=self.model_name or "qwen3.5:9b",
            token_usage=token_usage,
            metadata=metadata,
        )
