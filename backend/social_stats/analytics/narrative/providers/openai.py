"""
OpenAI Narrative Provider Adapter.
Live calls strictly disabled unless authorized.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from .base import BaseNarrativeProvider, NarrativeProviderResult

logger = logging.getLogger(__name__)


class OpenAINarrativeProvider(BaseNarrativeProvider):
    """
    Adapter for OpenAI models.
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__(model_name=model_name)

    def generate(
        self,
        context: Dict[str, Any],
        language: str = "es",
        style: str = "EXECUTIVE",
        **kwargs
    ) -> NarrativeProviderResult:
        if not getattr(settings, "ENABLE_LIVE_AI_NARRATIVE", False):
            raise RuntimeError("Live OpenAI calls are strictly disabled in this phase.")

        raise NotImplementedError("Live OpenAI execution requires Phase BS-4H.1 authorization.")
