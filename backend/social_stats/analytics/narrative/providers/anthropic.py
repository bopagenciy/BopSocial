"""
Anthropic Claude Narrative Provider Adapter.
Live calls strictly disabled unless authorized.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from .base import BaseNarrativeProvider, NarrativeProviderResult

logger = logging.getLogger(__name__)


class AnthropicNarrativeProvider(BaseNarrativeProvider):
    """
    Adapter for Anthropic Claude models.
    """

    def __init__(self, model_name: str = "claude-haiku-4-5-20251001", **kwargs):
        super().__init__(model_name=model_name)

    def generate(
        self,
        context: Dict[str, Any],
        language: str = "es",
        style: str = "EXECUTIVE",
        **kwargs
    ) -> NarrativeProviderResult:
        if not getattr(settings, "ENABLE_LIVE_AI_NARRATIVE", False):
            raise RuntimeError("Live Anthropic calls are strictly disabled in this phase.")

        # Live implementation placeholder for future authorized phase
        raise NotImplementedError("Live Anthropic execution requires Phase BS-4H.1 authorization.")
