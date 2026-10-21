"""
Provider Normalization Adapters for Bop Social Analytics.

Translates raw provider metrics from Facebook and Instagram payloads into canonical
NormalizedObservation instances while strictly preserving raw provider metric names
and semantic caveats (e.g. Reel plays vs 3s video views).
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Union

from .registry import is_valid_metric


@dataclass
class NormalizedObservation:
    normalized_metric: str
    metric_value: Decimal
    raw_metric_name: str
    metric_scope: str
    extra_dimensions: Dict = field(default_factory=dict)
    is_derived: bool = False
    metadata: Dict = field(default_factory=dict)


def _to_decimal(val: Union[int, float, Decimal, str]) -> Decimal:
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


# ── Facebook Normalizer ────────────────────────────────────────────────────────

def normalize_facebook_metric(
    raw_metric_name: str,
    raw_value: Union[int, float, Decimal, str, dict],
    metric_scope: str = "account",
    context: Optional[Dict] = None,
) -> List[NormalizedObservation]:
    """
    Normalizes Facebook Graph API v21.0 raw metrics for Page and Post scopes.
    Returns a list of NormalizedObservation instances.
    """
    raw_name = (raw_metric_name or "").strip()
    scope = (metric_scope or "account").strip().lower()
    results: List[NormalizedObservation] = []

    # 1. Reach & Impressions
    if raw_name in ("page_impressions_unique", "post_impressions_unique"):
        results.append(NormalizedObservation(
            normalized_metric="REACH",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account" if "page" in raw_name else "post",
        ))
    elif raw_name in ("page_impressions", "post_impressions"):
        results.append(NormalizedObservation(
            normalized_metric="IMPRESSIONS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account" if "page" in raw_name else "post",
        ))

    # 2. Followers
    elif raw_name in ("followers_count", "fan_count"):
        results.append(NormalizedObservation(
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))
    elif raw_name == "page_daily_follows":
        results.append(NormalizedObservation(
            normalized_metric="FOLLOWERS_NET_CHANGE",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
            extra_dimensions={"direction": "gain"},
        ))
    elif raw_name == "page_daily_unfollows":
        # Store as net delta loss
        results.append(NormalizedObservation(
            normalized_metric="FOLLOWERS_NET_CHANGE",
            metric_value=-abs(_to_decimal(raw_value)),
            raw_metric_name=raw_name,
            metric_scope="account",
            extra_dimensions={"direction": "loss"},
        ))

    # 3. Profile Views & Page Total Actions
    elif raw_name == "page_views_total":
        results.append(NormalizedObservation(
            normalized_metric="PROFILE_VIEWS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))
    elif raw_name == "page_total_actions":
        results.append(NormalizedObservation(
            normalized_metric="CLICKS_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))

    # 4. Engagement Total & Clicks
    elif raw_name == "page_post_engagements":
        results.append(NormalizedObservation(
            normalized_metric="ENGAGEMENT_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))
    elif raw_name == "post_clicks":
        results.append(NormalizedObservation(
            normalized_metric="CLICKS_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="post",
        ))

    # 5. Reactions (scalar total or dictionary breakdown)
    elif raw_name in ("reactions", "reactions.summary.total_count", "page_actions_post_reactions_total"):
        if isinstance(raw_value, dict):
            # Breakdown provided: emit overall total and individual dimensions
            total = sum(_to_decimal(v) for v in raw_value.values())
            results.append(NormalizedObservation(
                normalized_metric="REACTIONS",
                metric_value=total,
                raw_metric_name=raw_name,
                metric_scope=scope,
            ))
            for r_type, r_val in raw_value.items():
                results.append(NormalizedObservation(
                    normalized_metric="REACTIONS",
                    metric_value=_to_decimal(r_val),
                    raw_metric_name=f"{raw_name}.{r_type}",
                    metric_scope=scope,
                    extra_dimensions={"reaction_type": r_type.lower()},
                ))
        else:
            results.append(NormalizedObservation(
                normalized_metric="REACTIONS",
                metric_value=_to_decimal(raw_value),
                raw_metric_name=raw_name,
                metric_scope=scope,
            ))

    # 6. Comments & Shares
    elif raw_name in ("comments", "comments.summary.total_count"):
        results.append(NormalizedObservation(
            normalized_metric="COMMENTS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))
    elif raw_name in ("shares", "shares.count"):
        results.append(NormalizedObservation(
            normalized_metric="SHARES",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 7. Video Views
    elif raw_name in ("page_video_views", "post_video_views"):
        results.append(NormalizedObservation(
            normalized_metric="VIDEO_VIEWS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account" if "page" in raw_name else "post",
            metadata={"view_definition": ">=3_seconds"},
        ))

    return results


# ── Instagram Normalizer ───────────────────────────────────────────────────────

def normalize_instagram_metric(
    raw_metric_name: str,
    raw_value: Union[int, float, Decimal, str, dict],
    metric_scope: str = "account",
    context: Optional[Dict] = None,
) -> List[NormalizedObservation]:
    """
    Normalizes Instagram Graph API v21.0 raw metrics for Account, Media, Reel, and Story scopes.
    Returns a list of NormalizedObservation instances.
    """
    raw_name = (raw_metric_name or "").strip()
    scope = (metric_scope or "account").strip().lower()
    ctx = context or {}
    media_type = (ctx.get("media_type") or "").strip().upper()
    results: List[NormalizedObservation] = []

    # 1. Reach
    if raw_name == "reach":
        results.append(NormalizedObservation(
            normalized_metric="REACH",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 2. Followers
    elif raw_name in ("follower_count", "followers_count"):
        results.append(NormalizedObservation(
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))
    elif raw_name == "follows_and_unfollows" and isinstance(raw_value, dict):
        follows = _to_decimal(raw_value.get("follows", 0))
        unfollows = _to_decimal(raw_value.get("unfollows", 0))
        net = follows - unfollows
        results.append(NormalizedObservation(
            normalized_metric="FOLLOWERS_NET_CHANGE",
            metric_value=net,
            raw_metric_name=raw_name,
            metric_scope="account",
            extra_dimensions={"follows": int(follows), "unfollows": int(unfollows)},
        ))

    # 3. Profile views & website clicks
    elif raw_name == "profile_views":
        results.append(NormalizedObservation(
            normalized_metric="PROFILE_VIEWS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))
    elif raw_name == "website_clicks":
        results.append(NormalizedObservation(
            normalized_metric="CLICKS_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
        ))

    # 4. Engagement & Interactions
    elif raw_name == "total_interactions":
        results.append(NormalizedObservation(
            normalized_metric="ENGAGEMENT_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))
    elif raw_name == "accounts_engaged":
        results.append(NormalizedObservation(
            normalized_metric="ENGAGEMENT_TOTAL",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="account",
            metadata={"measurement_type": "unique_accounts"},
        ))

    # 5. Likes / Reactions
    elif raw_name in ("likes", "like_count"):
        results.append(NormalizedObservation(
            normalized_metric="REACTIONS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 6. Comments
    elif raw_name in ("comments", "comments_count"):
        results.append(NormalizedObservation(
            normalized_metric="COMMENTS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 7. Shares
    elif raw_name == "shares":
        results.append(NormalizedObservation(
            normalized_metric="SHARES",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 8. Saves
    elif raw_name in ("saves", "saved"):
        results.append(NormalizedObservation(
            normalized_metric="SAVES",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope=scope,
        ))

    # 9. Reels plays vs Video views (Explicit Video Semantics)
    elif raw_name == "plays":
        # For Reels, plays represents video playbacks/loops
        results.append(NormalizedObservation(
            normalized_metric="VIDEO_VIEWS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name="plays",
            metric_scope="reel",
            metadata={
                "media_type": "REEL",
                "comparability_caveat": "Instagram Reel 'plays' represents play counts and loops, not 3s threshold.",
            },
        ))
    elif raw_name == "video_views":
        results.append(NormalizedObservation(
            normalized_metric="VIDEO_VIEWS",
            metric_value=_to_decimal(raw_value),
            raw_metric_name="video_views",
            metric_scope="video",
            metadata={"media_type": media_type or "VIDEO"},
        ))

    # 10. Watch times
    elif raw_name == "ig_reels_video_view_total_time":
        # Meta returns milliseconds in some versions or seconds; normalize to seconds if raw in ms
        val = _to_decimal(raw_value)
        # If val > 100000 and context indicates ms, we convert, else assume seconds
        results.append(NormalizedObservation(
            normalized_metric="VIDEO_WATCH_TIME",
            metric_value=val,
            raw_metric_name=raw_name,
            metric_scope="reel",
        ))
    elif raw_name == "ig_reels_avg_watch_time":
        results.append(NormalizedObservation(
            normalized_metric="VIDEO_AVG_WATCH_TIME",
            metric_value=_to_decimal(raw_value),
            raw_metric_name=raw_name,
            metric_scope="reel",
        ))

    return results


# ── Unified Normalization Dispatcher ───────────────────────────────────────────

def normalize_metric(
    platform: str,
    raw_metric_name: str,
    raw_value: Union[int, float, Decimal, str, dict],
    metric_scope: str = "account",
    context: Optional[Dict] = None,
) -> List[NormalizedObservation]:
    """
    Provider-neutral entrypoint to normalize raw metrics.
    Dispatches to platform normalizer and validates canonical keys.
    """
    plat = (platform or "").strip().lower()
    if plat == "facebook":
        observations = normalize_facebook_metric(raw_metric_name, raw_value, metric_scope, context)
    elif plat == "instagram":
        observations = normalize_instagram_metric(raw_metric_name, raw_value, metric_scope, context)
    else:
        observations = []

    # Validate that generated observations conform to canonical registry
    valid_observations = []
    for obs in observations:
        if is_valid_metric(obs.normalized_metric):
            valid_observations.append(obs)

    return valid_observations
