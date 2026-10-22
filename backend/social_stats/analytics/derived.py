"""
Pure Derived Metric Utilities for Bop Social Analytics.

Calculates engagement aggregates, engagement rates, and growth rates with safe division
and explicit handling for missing or zero denominators.
"""
from collections.abc import Mapping, Iterable
from decimal import Decimal, InvalidOperation
from typing import Optional, Union, Tuple, List, Dict, Any

Number = Union[int, float, Decimal, str]

CANONICAL_REQUIRED_COMPONENTS = {
    "ENGAGEMENT_TOTAL": ["REACTIONS", "COMMENTS", "SHARES"],
}


def can_derive_metric(
    platform: Optional[str],
    capability_mode: Optional[Union[str, Any]],
    metric: str,
    available_source_metrics: Union[Iterable[str], Mapping[str, Any]],
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Capability-aware derived metric guard.
    Verifies that all required source components exist and are actually available.
    Explicitly distinguishes between:
      1) A component existing with value 0 (valid data).
      2) A component not existing or unavailable in the provider's capability mode.

    Returns:
      (can_derive: bool, reason: Optional[str], missing_components: List[str])
    """
    m_upper = (metric or "").strip().upper()

    cap_str = ""
    if capability_mode is not None:
        if hasattr(capability_mode, "value"):
            cap_str = str(capability_mode.value).upper()
        else:
            cap_str = str(capability_mode).upper()

    plat_str = (platform or "").strip().lower()

    def _is_component_available(comp: str) -> bool:
        comp_upper = comp.upper()
        if isinstance(available_source_metrics, Mapping):
            for k, v in available_source_metrics.items():
                if str(k).upper() == comp_upper:
                    return v is not None
            return False
        elif isinstance(available_source_metrics, (list, tuple, set)):
            upper_set = {str(x).upper() for x in available_source_metrics}
            return comp_upper in upper_set
        return False

    required = CANONICAL_REQUIRED_COMPONENTS.get(m_upper)
    if not required:
        if plat_str == "instagram" and cap_str == "PARTIAL":
            if m_upper in ("SHARES", "SAVES", "REACH", "VIDEO_VIEWS"):
                if not _is_component_available(m_upper):
                    return False, "unsupported_by_capability_mode", [m_upper]
        return True, None, []

    missing = []
    for comp in required:
        if not _is_component_available(comp):
            missing.append(comp)

    if missing:
        return False, "missing_required_components", missing

    return True, None, []


def derive_canonical_engagement_total(
    source_metrics: Mapping[str, Any],
    platform: Optional[str] = None,
    capability_mode: Optional[Union[str, Any]] = None,
) -> Optional[Decimal]:
    """
    Derives canonical ENGAGEMENT_TOTAL if all required components are available.
    Returns None if any required component is missing or unavailable.
    Does NOT treat missing components as zero.
    """
    can_derive, _, _ = can_derive_metric(
        platform=platform,
        capability_mode=capability_mode,
        metric="ENGAGEMENT_TOTAL",
        available_source_metrics=source_metrics,
    )
    if not can_derive:
        return None

    def _get_val(k_name: str) -> Optional[Number]:
        for k, v in source_metrics.items():
            if str(k).upper() == k_name.upper():
                return v
        return None

    reactions = _to_decimal(_get_val("REACTIONS")) or Decimal(0)
    comments = _to_decimal(_get_val("COMMENTS")) or Decimal(0)
    shares = _to_decimal(_get_val("SHARES")) or Decimal(0)
    saves = _to_decimal(_get_val("SAVES")) if _get_val("SAVES") is not None else Decimal(0)
    clicks = _to_decimal(_get_val("CLICKS")) if _get_val("CLICKS") is not None else Decimal(0)

    total = max(Decimal(0), reactions) + \
            max(Decimal(0), comments) + \
            max(Decimal(0), shares) + \
            max(Decimal(0), saves) + \
            max(Decimal(0), clicks)

    return total


def _to_decimal(val: Optional[Number]) -> Optional[Decimal]:
    """Safely coerce value to Decimal or return None if None or invalid."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def calculate_engagement_total(
    reactions: Optional[Number] = 0,
    comments: Optional[Number] = 0,
    shares: Optional[Number] = 0,
    saves: Optional[Number] = 0,
    clicks: Optional[Number] = 0,
    require_canonical: bool = False,
) -> Optional[Decimal]:
    """
    Calculate derived total engagement from interaction components.
    Ensures no double-counting with provider-level total_interactions.
    If require_canonical is True, reactions, comments, and shares must all be non-None;
    returns None if any required component is missing (no fake zeros).
    """
    if require_canonical:
        if reactions is None or comments is None or shares is None:
            return None

    d_reactions = _to_decimal(reactions) or Decimal(0)
    d_comments  = _to_decimal(comments) or Decimal(0)
    d_shares    = _to_decimal(shares) or Decimal(0)
    d_saves     = _to_decimal(saves) or Decimal(0)
    d_clicks    = _to_decimal(clicks) or Decimal(0)

    # Protect against negative counters
    total = max(Decimal(0), d_reactions) + \
            max(Decimal(0), d_comments) + \
            max(Decimal(0), d_shares) + \
            max(Decimal(0), d_saves) + \
            max(Decimal(0), d_clicks)

    return total


def calculate_engagement_rate_reach(
    engagement_total: Optional[Number],
    reach: Optional[Number],
) -> Optional[Decimal]:
    """
    Calculate engagement rate relative to unique reach: (engagement / reach) * 100.
    Returns None if reach is missing, None, or <= 0 (safe division).
    """
    d_eng = _to_decimal(engagement_total)
    d_reach = _to_decimal(reach)

    if d_eng is None or d_reach is None:
        return None

    if d_reach <= 0:
        return None

    if d_eng < 0:
        d_eng = Decimal(0)

    rate = (d_eng / d_reach) * Decimal(100)
    return rate.quantize(Decimal("0.0001"))


def calculate_engagement_rate_followers(
    engagement_total: Optional[Number],
    followers_total: Optional[Number],
) -> Optional[Decimal]:
    """
    Calculate engagement rate relative to total followers: (engagement / followers) * 100.
    Returns None if followers_total is missing, None, or <= 0 (safe division).
    """
    d_eng = _to_decimal(engagement_total)
    d_followers = _to_decimal(followers_total)

    if d_eng is None or d_followers is None:
        return None

    if d_followers <= 0:
        return None

    if d_eng < 0:
        d_eng = Decimal(0)

    rate = (d_eng / d_followers) * Decimal(100)
    return rate.quantize(Decimal("0.0001"))


def calculate_follower_growth_rate(
    start_followers: Optional[Number],
    end_followers: Optional[Number],
) -> Optional[Decimal]:
    """
    Calculate follower growth percentage over a period: ((end - start) / start) * 100.
    Returns None if start_followers is missing, None, or <= 0 (safe division).
    """
    d_start = _to_decimal(start_followers)
    d_end   = _to_decimal(end_followers)

    if d_start is None or d_end is None:
        return None

    if d_start <= 0:
        return None

    diff = d_end - d_start
    growth = (diff / d_start) * Decimal(100)
    return growth.quantize(Decimal("0.0001"))
