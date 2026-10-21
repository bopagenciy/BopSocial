"""
Provider Analytics Capability Registry for Bop Social.

Defines the supported, partial, and unsupported capabilities per social platform,
including permission degradation (e.g. Instagram Basic mode without manage_insights).
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class SupportLevel(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class ProviderCapability:
    platform: str
    display_name: str
    overall_support: SupportLevel
    supports_account_metrics: bool
    supports_account_timeseries: bool
    supports_post_metrics: bool
    supports_story_metrics: bool
    supports_reel_metrics: bool
    supports_reach: bool
    supports_impressions: bool
    supports_clicks: bool
    supports_video_metrics: bool
    notes: str
    details: Dict = field(default_factory=dict)


# Base capabilities by platform
PROVIDER_CAPABILITIES: Dict[str, ProviderCapability] = {
    "facebook": ProviderCapability(
        platform="facebook",
        display_name="Facebook Page",
        overall_support=SupportLevel.SUPPORTED,
        supports_account_metrics=True,
        supports_account_timeseries=True,
        supports_post_metrics=True,
        supports_story_metrics=False,  # Organic Page story insights require distinct webhooks / permissions
        supports_reel_metrics=True,
        supports_reach=True,
        supports_impressions=True,
        supports_clicks=True,
        supports_video_metrics=True,
        notes="Full Page and Post insights supported via Meta Graph API v21.0.",
        details={
            "page_counters": True,
            "page_insights": True,
            "post_counters": True,
            "post_insights": True,
        }
    ),
    "instagram": ProviderCapability(
        platform="instagram",
        display_name="Instagram Professional Account",
        overall_support=SupportLevel.SUPPORTED,
        supports_account_metrics=True,
        supports_account_timeseries=True,
        supports_post_metrics=True,
        supports_story_metrics=True,  # Within 24 hours of creation
        supports_reel_metrics=True,
        supports_reach=True,
        supports_impressions=False,  # Single-media impressions deprecated in v18+; use reach
        supports_clicks=True,        # Website clicks on profile
        supports_video_metrics=True, # Reels plays and watch times
        notes="Full insights supported with instagram_manage_insights permission.",
        details={
            "requires_scope": "instagram_manage_insights",
            "media_direct_counters": True,
            "account_timeseries": True,
        }
    ),
    "youtube": ProviderCapability(
        platform="youtube",
        display_name="YouTube Channel",
        overall_support=SupportLevel.PARTIAL,
        supports_account_metrics=True,
        supports_account_timeseries=True,
        supports_post_metrics=True,
        supports_story_metrics=False,
        supports_reel_metrics=True,  # Shorts
        supports_reach=False,        # YouTube uses impressions and views
        supports_impressions=True,
        supports_clicks=False,
        supports_video_metrics=True,
        notes="Partial support: Channel statistics and video analytics via YouTube Analytics API.",
    ),
    "linkedin": ProviderCapability(
        platform="linkedin",
        display_name="LinkedIn Organization",
        overall_support=SupportLevel.PARTIAL,
        supports_account_metrics=True,
        supports_account_timeseries=True,
        supports_post_metrics=True,
        supports_story_metrics=False,
        supports_reel_metrics=False,
        supports_reach=False,
        supports_impressions=True,
        supports_clicks=True,
        supports_video_metrics=True,
        notes="Partial support: Organization followers, impressions, and post engagement.",
    ),
    "google_my_business": ProviderCapability(
        platform="google_my_business",
        display_name="Google Business Profile",
        overall_support=SupportLevel.PARTIAL,
        supports_account_metrics=True,
        supports_account_timeseries=True,
        supports_post_metrics=False,
        supports_story_metrics=False,
        supports_reel_metrics=False,
        supports_reach=False,
        supports_impressions=True,   # Maps & Search impressions
        supports_clicks=True,        # Website, phone, direction clicks
        supports_video_metrics=False,
        notes="Partial support: Profile views, search/maps impressions, calls, directions.",
    ),
    "tiktok": ProviderCapability(
        platform="tiktok",
        display_name="TikTok",
        overall_support=SupportLevel.UNSUPPORTED,
        supports_account_metrics=False,
        supports_account_timeseries=False,
        supports_post_metrics=False,
        supports_story_metrics=False,
        supports_reel_metrics=False,
        supports_reach=False,
        supports_impressions=False,
        supports_clicks=False,
        supports_video_metrics=False,
        notes="Unsupported in BS-4: Planned for future milestone.",
    ),
    "x": ProviderCapability(
        platform="x",
        display_name="X (Twitter)",
        overall_support=SupportLevel.UNSUPPORTED,
        supports_account_metrics=False,
        supports_account_timeseries=False,
        supports_post_metrics=False,
        supports_story_metrics=False,
        supports_reel_metrics=False,
        supports_reach=False,
        supports_impressions=False,
        supports_clicks=False,
        supports_video_metrics=False,
        notes="Unsupported in BS-4: Planned for future milestone.",
    ),
}


def get_provider_capability(platform: str, credential=None) -> ProviderCapability:
    """
    Return provider capability, accounting for permission degradation.
    Specifically: Instagram without instagram_manage_insights drops to basic mode.
    """
    plat = (platform or "").strip().lower()
    base = PROVIDER_CAPABILITIES.get(plat)
    if not base:
        return ProviderCapability(
            platform=plat,
            display_name=plat.capitalize(),
            overall_support=SupportLevel.UNSUPPORTED,
            supports_account_metrics=False,
            supports_account_timeseries=False,
            supports_post_metrics=False,
            supports_story_metrics=False,
            supports_reel_metrics=False,
            supports_reach=False,
            supports_impressions=False,
            supports_clicks=False,
            supports_video_metrics=False,
            notes="Unknown platform.",
        )

    # Check Instagram permission degradation
    if plat == "instagram" and credential is not None:
        has_manage_insights = False
        scopes = getattr(credential, "scope", "") or ""
        scope_list = [s.strip().lower() for s in scopes.replace(",", " ").split() if s.strip()]
        if "instagram_manage_insights" in scope_list:
            has_manage_insights = True

        if not has_manage_insights:
            # Degrade to Instagram Basic Mode
            return ProviderCapability(
                platform="instagram",
                display_name="Instagram (Basic Mode — Limited Permissions)",
                overall_support=SupportLevel.PARTIAL,
                supports_account_metrics=False,      # Account insights unavailable
                supports_account_timeseries=False,   # No account timeseries without scope
                supports_post_metrics=True,          # Direct media counters (likes, comments) available
                supports_story_metrics=False,        # Story insights unavailable
                supports_reel_metrics=False,         # Reel insights unavailable
                supports_reach=False,
                supports_impressions=False,
                supports_clicks=False,
                supports_video_metrics=False,
                notes=(
                    "Degraded capability: 'instagram_manage_insights' scope missing. "
                    "Only direct media counters (likes, comments) are queryable."
                ),
                details={
                    "is_degraded": True,
                    "media_direct_counters": True,
                    "account_timeseries": False,
                }
            )

    return base
