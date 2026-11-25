# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Shared helpers for the AI module.

Public:
    get_claude(api_key=None) -> anthropic.Anthropic | None
    parse_json_response(raw: str) -> dict          # strips markdown fences
    brand_voice_prompt(client) -> str              # voice-only fragment (legacy)
    unified_voice_prompt(client) -> str            # voice + metrics + industry
    rate_limit_check(client, key, limit) -> bool   # cache-backed per-client per-day limit
    HAIKU / SONNET                                 # model id constants
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Model IDs — keep in sync with the rest of the app.
HAIKU  = 'claude-haiku-4-5-20251001'
SONNET = 'claude-sonnet-4-6'   # for richer content tasks


class AIConfigError(RuntimeError):
    """Raised when the configured AI provider is missing credentials/config."""


class AITimeoutError(RuntimeError):
    """Raised when an AI provider call times out."""


class AIProviderError(RuntimeError):
    """Raised when an AI provider call fails."""


def resolve_ai_content_provider() -> str:
    """
    Resolve the active commercial AI text-generation provider.
    Supports 'ollama' and 'anthropic'. Never silently falls back to paid Anthropic
    when 'ollama' is explicitly selected.
    """
    configured = (getattr(settings, 'AI_CONTENT_PROVIDER', '') or '').strip().lower()
    if configured in ('ollama', 'anthropic'):
        return configured
    if getattr(settings, 'ANTHROPIC_API_KEY', ''):
        return 'anthropic'
    return ''


def generate_text_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2048,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    json_mode: bool = False,
) -> str:
    """
    Provider-agnostic text completion helper supporting configurable Ollama
    and Anthropic backends with explicit timeout and error handling.
    """
    provider = resolve_ai_content_provider()
    if not provider:
        raise AIConfigError('AI service is not configured. Contact your administrator.')

    if provider == 'ollama':
        import requests
        from .analytics.narrative.providers.ollama import (
            _clean_ollama_response_text,
            compose_ollama_prompt,
        )

        host = (getattr(settings, 'OLLAMA_HOST', 'http://host.docker.internal:11434') or '').rstrip('/')
        if not host:
            raise AIConfigError('OLLAMA_HOST is not configured.')
        ollama_model = model or getattr(settings, 'OLLAMA_MODEL', 'qwen3.5:9b')
        req_timeout = int(timeout or getattr(settings, 'OLLAMA_TIMEOUT_SECONDS', 90))
        payload: dict[str, Any] = {
            'model': ollama_model,
            'prompt': compose_ollama_prompt(system_prompt, user_prompt),
            'stream': False,
            'think': False,
            'options': {
                'num_ctx': int(getattr(settings, 'OLLAMA_NUM_CTX', 8192)),
                'num_predict': max_tokens,
            },
        }
        if json_mode:
            payload['format'] = 'json'
        try:
            resp = requests.post(f'{host}/api/generate', json=payload, timeout=req_timeout)
        except requests.Timeout as exc:
            raise AITimeoutError(f'Ollama request timed out after {req_timeout}s') from exc
        except requests.RequestException as exc:
            raise AIProviderError('Local Ollama service is unreachable.') from exc

        if resp.status_code != 200:
            raise AIProviderError(f'Ollama returned HTTP {resp.status_code}')
        try:
            data = resp.json()
        except ValueError as exc:
            raise AIProviderError('Ollama returned invalid JSON response.') from exc
        raw = _clean_ollama_response_text(str(data.get('response') or ''))
        if not raw:
            raise AIProviderError('Ollama returned empty response.')
        return raw

    # Anthropic provider
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or ''
    if not api_key:
        raise AIConfigError('ANTHROPIC_API_KEY is not configured.')
    try:
        import anthropic
    except ImportError as exc:
        raise AIConfigError('Anthropic SDK is not installed.') from exc

    req_timeout = int(timeout or 30)
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model or HAIKU,
            max_tokens=max_tokens,
            timeout=req_timeout,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        return (msg.content[0].text or '').strip()
    except anthropic.APITimeoutError as exc:
        raise AITimeoutError(f'Anthropic request timed out after {req_timeout}s') from exc
    except anthropic.APIError as exc:
        raise AIProviderError(f'Anthropic API error: {exc}') from exc


def get_claude(api_key: Optional[str] = None):
    """Lazy-init the Anthropic client. Returns None when SDK or key missing."""
    try:
        import anthropic
    except ImportError:
        logger.debug('anthropic SDK not installed')
        return None
    key = api_key or getattr(settings, 'ANTHROPIC_API_KEY', '') or ''
    if not key:
        return None
    try:
        return anthropic.Anthropic(api_key=key)
    except Exception:
        logger.exception('Failed to init Anthropic client')
        return None


def parse_json_response(raw: str) -> Any:
    """
    Parse a Claude response that *should* be JSON. Handles markdown code
    fences (```json ... ```) and plain ``` wrappers. Raises ValueError when
    the body isn't parseable.
    """
    s = (raw or '').strip()
    if s.startswith('```'):
        # Drop the opening fence (with or without language tag)
        first_nl = s.find('\n')
        if first_nl == -1:
            s = s[3:]
        else:
            s = s[first_nl + 1:]
        if s.endswith('```'):
            s = s[:-3].strip()
    return json.loads(s)


def brand_voice_prompt(client) -> str:
    """
    Render a short prompt fragment describing the client's brand voice. Empty
    string when no profile exists or training hasn't finished. Injected into
    system prompts of every content-generation task.

    extended to include preferred_words, target_audience,
    prohibited_topics, emoji_usage, hashtag_style.
    """
    try:
        bv = getattr(client, 'brand_voice', None)
        if not bv:
            return ''
        # Skip injection when training hasn't finished — avoids confusing
        # the model with a partial / stale profile mid-training.
        status = getattr(bv, 'training_status', 'pending') or 'pending'
        if status not in ('ready', ''):  # '' = legacy profiles trained before status field
            return ''

        bits = []
        if bv.voice_summary:
            bits.append(f'Voice summary: {bv.voice_summary}')
        if bv.tone_descriptors:
            bits.append(f'Preferred tones: {", ".join(bv.tone_descriptors)}')
        if bv.style_rules:
            bits.append(f'Style rules: {"; ".join(bv.style_rules)}')

        if getattr(bv, 'preferred_words', None):
            bits.append(f'Vocabulary to favour: {", ".join(bv.preferred_words)}')
        if bv.forbidden_words:
            bits.append(f'Avoid: {", ".join(bv.forbidden_words)}')
        if getattr(bv, 'target_audience', ''):
            bits.append(f'Target audience: {bv.target_audience}')
        if getattr(bv, 'prohibited_topics', None):
            bits.append(f'Topics to avoid entirely: {", ".join(bv.prohibited_topics)}')
        if getattr(bv, 'emoji_usage', '') and bv.emoji_usage != 'moderate':
            bits.append(f'Emoji usage: {bv.emoji_usage}')
        if getattr(bv, 'hashtag_style', ''):
            bits.append(f'Hashtag style: {bv.hashtag_style}')

        return '\n'.join(bits) if bits else ''
    except Exception:
        return ''


def unified_voice_prompt(client) -> str:
    """— superset of `brand_voice_prompt(client)`.

    Returns a multi-section prompt fragment combining:
      • Workspace anchor (company name + industry) — always present when
        client is set, even for fresh workspaces with no metrics
      • Brand voice training output (the original brand_voice_prompt content)
      • Recent performance summary (last 30d engagement vs prior 30d)
      • Industry context (tracked competitor names)

    Backed by `ai.AIContextProvider`. **Drop-in safe replacement** for callers
    that previously fed `brand_voice_prompt(client)` straight into a system
    prompt: the return shape is identical (a string), but the unified
    fragment is a strict superset of the legacy output. Callers that gate
    on `if bv:` will fire that gate more often than before, which is the
    desired effect.

    Returns '' only when client is None / falsy. With any client, the
    workspace anchor renders so the fragment is never empty.

    Defensive against failures inside the provider's bucket builders
    (each one wraps its own except clause); a broken metrics query,
    missing competitor table, etc. won't break the AI request — falls
    back to the legacy `brand_voice_prompt(client)` on hard failure.

    Lazy-imports `AIContextProvider` so this helper stays usable from
    modules that ai/ might import (avoids circular imports).
    """
    if not client:
        return ''
    try:
        from .ai.context import AIContextProvider
        return AIContextProvider(client=client).as_prompt_fragment() or ''
    except Exception:
        # Defence in depth — never break an AI call because the unified
        # provider had a bad day. Fall back to the voice-only fragment
        # which has its own try/except around the model lookup.
        try:
            return brand_voice_prompt(client)
        except Exception:
            return ''


def rate_limit_check(client_id, key: str, limit: int) -> bool:
    """
    Cache-backed per-client per-day counter.
    Returns True when within the limit (and increments). False when exceeded.
    """
    today = timezone.now().date().isoformat()
    cache_key = f'ai:ratelimit:{client_id}:{key}:{today}'
    count = cache.get(cache_key) or 0
    if count >= limit:
        return False
    cache.set(cache_key, count + 1, timeout=60 * 60 * 26)  # 26h TTL > 24h
    return True


def cache_key_for(prefix: str, payload: dict) -> str:
    """Stable cache key for memoizing identical AI inputs (1h TTL by convention)."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f'{prefix}:{hashlib.sha256(raw.encode()).hexdigest()}'
