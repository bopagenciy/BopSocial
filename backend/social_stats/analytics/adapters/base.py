"""
Base Provider Analytics Adapter Interface.
Abstracts raw transport and provider HTTP communication away from normalization logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProviderPayload:
    """
    Standardized carrier for raw provider responses, HTTP rate limit headers,
    and diagnostic warnings/errors.
    """
    raw_data: Dict = field(default_factory=dict)
    rate_limit_headers: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BaseAnalyticsAdapter(ABC):
    """Abstract provider analytics adapter."""

    @abstractmethod
    def fetch_account_metrics(
        self,
        credential,
        since=None,
        until=None,
    ) -> ProviderPayload:
        """Fetch raw account/page-level metrics and insights."""
        raise NotImplementedError

    @abstractmethod
    def fetch_post_metrics(
        self,
        credential,
        limit: int = 25,
        since=None,
        until=None,
    ) -> ProviderPayload:
        """Fetch raw post/media list and per-post metric payloads."""
        raise NotImplementedError

    def fetch_story_metrics(self, credential) -> ProviderPayload:
        """Optional fetch for ephemeral stories."""
        return ProviderPayload()

    def fetch_reel_metrics(self, credential) -> ProviderPayload:
        """Optional fetch for dedicated reel metrics."""
        return ProviderPayload()
