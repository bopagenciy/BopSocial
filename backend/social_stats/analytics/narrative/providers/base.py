"""
Base class and data classes for Narrative Providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class NarrativeProviderResult:
    raw_response: str
    parsed_json: Dict[str, Any]
    provider_name: str
    model_name: str
    token_usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseNarrativeProvider(ABC):
    """
    Abstract interface for grounded narrative generation.
    Decoupled from direct database access.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name

    @abstractmethod
    def generate(
        self,
        context: Dict[str, Any],
        language: str = "es",
        style: str = "EXECUTIVE",
        **kwargs
    ) -> NarrativeProviderResult:
        """
        Generates structured narrative from allowlisted context.
        """
        pass
