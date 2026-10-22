"""
Centralized deterministic business intelligence rules, thresholds, and taxonomy.
No black-box scoring, no invented benchmarks, no generative AI.
"""
from decimal import Decimal
from typing import Optional


class SignalType:
    CONTENT_OUTPERFORMING = "CONTENT_OUTPERFORMING"
    CONTENT_UNDERPERFORMING = "CONTENT_UNDERPERFORMING"
    ENGAGEMENT_TREND_UP = "ENGAGEMENT_TREND_UP"
    ENGAGEMENT_TREND_DOWN = "ENGAGEMENT_TREND_DOWN"
    FOLLOWER_GROWTH_UP = "FOLLOWER_GROWTH_UP"
    FOLLOWER_GROWTH_DOWN = "FOLLOWER_GROWTH_DOWN"
    FORMAT_OUTPERFORMING = "FORMAT_OUTPERFORMING"
    FORMAT_UNDERPERFORMING = "FORMAT_UNDERPERFORMING"
    POSTING_TIME_OUTPERFORMING = "POSTING_TIME_OUTPERFORMING"
    POSTING_TIME_UNDERPERFORMING = "POSTING_TIME_UNDERPERFORMING"
    PLATFORM_OUTPERFORMING = "PLATFORM_OUTPERFORMING"
    PLATFORM_DEGRADING = "PLATFORM_DEGRADING"
    DATA_STALE = "DATA_STALE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    METRIC_UNAVAILABLE = "METRIC_UNAVAILABLE"
    PROVIDER_PARTIAL = "PROVIDER_PARTIAL"
    POSITIVE_OUTLIER = "POSITIVE_OUTLIER"
    NEGATIVE_OUTLIER = "NEGATIVE_OUTLIER"
    MOMENTUM_UP = "MOMENTUM_UP"
    MOMENTUM_DOWN = "MOMENTUM_DOWN"


class PerformanceTier:
    STRONG_OUTPERFORMANCE = "STRONG_OUTPERFORMANCE"
    OUTPERFORMANCE = "OUTPERFORMANCE"
    NORMAL_RANGE = "NORMAL_RANGE"
    UNDERPERFORMANCE = "UNDERPERFORMANCE"
    STRONG_UNDERPERFORMANCE = "STRONG_UNDERPERFORMANCE"


class ConfidenceTier:
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


# Centralized outperformance thresholds
THRESHOLDS = {
    "STRONG_OUTPERFORMANCE": Decimal("0.5000"),    # >= +50%
    "OUTPERFORMANCE": Decimal("0.2000"),           # +20% to +49.99%
    "NORMAL_LOWER": Decimal("-0.2000"),            # -19.99% to +19.99%
    "UNDERPERFORMANCE": Decimal("-0.2000"),        # -20% to -49.99%
    "STRONG_UNDERPERFORMANCE": Decimal("-0.5000"), # <= -50%
}

# Small sample size safety thresholds
SAMPLE_THRESHOLDS = {
    "MINIMUM_FOR_SIGNAL": 3,   # n < 3: INSUFFICIENT_SAMPLE / NONE confidence
    "LOW_CONFIDENCE_MAX": 5,   # 3 <= n < 5: LOW
    "MEDIUM_CONFIDENCE_MAX": 10,# 5 <= n < 10: MEDIUM
    "HIGH_CONFIDENCE_MIN": 10, # n >= 10: potential HIGH
}


def classify_performance_tier(relative_delta: Optional[Decimal]) -> str:
    """
    Classifies a relative delta into a deterministic performance tier.
    """
    if relative_delta is None:
        return PerformanceTier.NORMAL_RANGE

    if relative_delta >= THRESHOLDS["STRONG_OUTPERFORMANCE"]:
        return PerformanceTier.STRONG_OUTPERFORMANCE
    elif relative_delta >= THRESHOLDS["OUTPERFORMANCE"]:
        return PerformanceTier.OUTPERFORMANCE
    elif relative_delta <= THRESHOLDS["STRONG_UNDERPERFORMANCE"]:
        return PerformanceTier.STRONG_UNDERPERFORMANCE
    elif relative_delta <= THRESHOLDS["UNDERPERFORMANCE"]:
        return PerformanceTier.UNDERPERFORMANCE
    else:
        return PerformanceTier.NORMAL_RANGE


def calculate_confidence(sample_size: int, is_stale: bool = False, is_partial: bool = False) -> str:
    """
    Determines confidence tier based on sample size, freshness, and provider capability.
    Downgrades confidence if data is stale or provider operates in partial mode.
    """
    if sample_size < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
        return ConfidenceTier.NONE
    elif sample_size < SAMPLE_THRESHOLDS["LOW_CONFIDENCE_MAX"]:
        tier = ConfidenceTier.LOW
    elif sample_size < SAMPLE_THRESHOLDS["MEDIUM_CONFIDENCE_MAX"]:
        tier = ConfidenceTier.MEDIUM
    else:
        tier = ConfidenceTier.HIGH

    # Downgrade rules
    if is_stale or is_partial:
        if tier == ConfidenceTier.HIGH:
            tier = ConfidenceTier.MEDIUM
        elif tier == ConfidenceTier.MEDIUM:
            tier = ConfidenceTier.LOW
        elif tier == ConfidenceTier.LOW:
            tier = ConfidenceTier.NONE

    return tier


def determine_direction(relative_delta: Optional[Decimal]) -> str:
    """
    Determines signal direction from relative delta.
    """
    if relative_delta is None:
        return "NEUTRAL"
    if relative_delta >= Decimal("0.0500"):
        return "UP"
    elif relative_delta <= Decimal("-0.0500"):
        return "DOWN"
    return "FLAT"


def determine_severity(signal_type: str, performance_tier: str, direction: str, is_stale: bool = False) -> str:
    """
    Determines objective severity tier: INFO, POSITIVE, WARNING, CRITICAL.
    """
    if signal_type in (SignalType.DATA_STALE, SignalType.PLATFORM_DEGRADING) or is_stale:
        return "WARNING"

    if signal_type == SignalType.PROVIDER_PARTIAL:
        return "INFO"

    if signal_type == SignalType.INSUFFICIENT_SAMPLE:
        return "INFO"

    if performance_tier == PerformanceTier.STRONG_UNDERPERFORMANCE:
        return "CRITICAL"
    elif performance_tier == PerformanceTier.UNDERPERFORMANCE or direction == "DOWN":
        return "WARNING"
    elif performance_tier in (PerformanceTier.STRONG_OUTPERFORMANCE, PerformanceTier.OUTPERFORMANCE) or direction == "UP":
        return "POSITIVE"

    return "INFO"


def is_signal_actionable(signal_type: str) -> bool:
    """
    Identifies whether an executive or operator can take direct creative or operational action.
    """
    actionable_types = {
        SignalType.FORMAT_OUTPERFORMING,
        SignalType.FORMAT_UNDERPERFORMING,
        SignalType.POSTING_TIME_OUTPERFORMING,
        SignalType.CONTENT_OUTPERFORMING,
        SignalType.CONTENT_UNDERPERFORMING,
        SignalType.DATA_STALE,
        SignalType.POSITIVE_OUTLIER,
    }
    return signal_type in actionable_types
