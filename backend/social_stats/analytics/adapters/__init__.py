"""
Analytics Adapters package for Bop Social.
"""
from .base import BaseAnalyticsAdapter, ProviderPayload
from .facebook import FacebookAnalyticsAdapter
from .instagram import InstagramAnalyticsAdapter, has_instagram_insights_capability

__all__ = [
    "BaseAnalyticsAdapter",
    "ProviderPayload",
    "FacebookAnalyticsAdapter",
    "InstagramAnalyticsAdapter",
    "has_instagram_insights_capability",
]
