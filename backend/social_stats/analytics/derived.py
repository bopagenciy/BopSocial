"""
Pure Derived Metric Utilities for Bop Social Analytics.

Calculates engagement aggregates, engagement rates, and growth rates with safe division
and explicit handling for missing or zero denominators.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

Number = Union[int, float, Decimal, str]


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
) -> Decimal:
    """
    Calculate derived total engagement from interaction components.
    Ensures no double-counting with provider-level total_interactions.
    """
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
