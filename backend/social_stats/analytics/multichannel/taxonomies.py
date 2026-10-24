"""
Taxonomies and Enumerations for Multichannel Metric Compatibility & Comparison.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Defines deterministic, machine-readable taxonomies for:
- ComparisonCompatibility
- ComparisonDirection
- NormalizationType
- ComparisonWinner
- ComparisonStatus
- ComparisonReasonCode
"""
from enum import Enum


class ComparisonCompatibility(str, Enum):
    """
    Explicit classification of cross-platform metric comparability.
    Cross-platform intelligence MUST NOT assume same metric name = same business meaning.
    """
    DIRECT = "DIRECT"
    # Same business concept and compatible measurement semantics across platforms.
    NORMALIZED = "NORMALIZED"
    # Comparable only after a documented normalization or transformation.
    CONDITIONAL = "CONDITIONAL"
    # Comparable only if runtime prerequisites are satisfied (e.g. period unique reach, provider capability).
    NON_COMPARABLE = "NON_COMPARABLE"
    # Must never be ranked directly across platforms due to fundamental semantic discrepancies.
    UNAVAILABLE = "UNAVAILABLE"
    # Required source data is missing, unsupported, or unqueryable for one or more platforms.


class ComparisonDirection(str, Enum):
    """
    Direction semantics for comparable metrics.
    Not every metric is 'higher is better'.
    """
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    # Greater value represents stronger performance (e.g. net follower growth, reactions).
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    # Lower value represents stronger performance (e.g. cost, bounce rate, churn).
    NEUTRAL = "NEUTRAL"
    # Informational or volume gauge; greater value does NOT imply superior performance (e.g. FOLLOWERS_TOTAL).
    NOT_APPLICABLE = "NOT_APPLICABLE"
    # Metric cannot or must not be ranked competitively (e.g. NON_COMPARABLE metrics).


class NormalizationType(str, Enum):
    """
    Explicit normalization transformations applied prior to comparison.
    Only defensible transformations from source data are permitted; never invent unavailable denominators.
    """
    NONE = "NONE"
    # Direct comparison of raw values without scaling.
    PER_POST = "PER_POST"
    # Scaled per published post in the period.
    PER_1000_FOLLOWERS = "PER_1000_FOLLOWERS"
    # Scaled per 1,000 active followers.
    PER_IMPRESSION = "PER_IMPRESSION"
    # Scaled per total impressions.
    PER_REACH = "PER_REACH"
    # Scaled per unique reached audience.
    RATE = "RATE"
    # Mathematical ratio or proportion (0.0 to 1.0 or percentage).
    LATEST_VALUE = "LATEST_VALUE"
    # Point-in-time snapshot gauge (e.g. active followers).
    DELTA = "DELTA"
    # Net change over an aligned discrete time period.
    DAILY_AVERAGE = "DAILY_AVERAGE"
    # Arithmetic mean across active days in the aligned period.


class ComparisonWinner(str, Enum):
    """
    Deterministic winner determination for rankable metrics.
    A winner may only exist if metric is comparable, both values valid, and direction supports ranking.
    """
    PLATFORM_A = "PLATFORM_A"
    PLATFORM_B = "PLATFORM_B"
    TIE = "TIE"
    NO_WINNER = "NO_WINNER"
    # Used when metric is non-rankable (e.g. NEUTRAL direction like FOLLOWERS_TOTAL) or direction is NOT_APPLICABLE.
    UNAVAILABLE = "UNAVAILABLE"
    # Used when comparison cannot be executed (e.g. missing data, provider partial, mismatch).


class ComparisonStatus(str, Enum):
    """
    High-level availability status of a comparison calculation.
    """
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


class ComparisonReasonCode(str, Enum):
    """
    Deterministic machine-readable reason codes explaining comparison status and decisions.
    """
    DIRECTLY_COMPARABLE = "DIRECTLY_COMPARABLE"
    NORMALIZATION_REQUIRED = "NORMALIZATION_REQUIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    PROVIDER_PARTIAL = "PROVIDER_PARTIAL"
    METRIC_NOT_EQUIVALENT = "METRIC_NOT_EQUIVALENT"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    DENOMINATOR_UNAVAILABLE = "DENOMINATOR_UNAVAILABLE"
    ZERO_BASELINE = "ZERO_BASELINE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    NON_RANKABLE_METRIC = "NON_RANKABLE_METRIC"
    UNSUPPORTED_METRIC = "UNSUPPORTED_METRIC"
    UNSUPPORTED_PLATFORM = "UNSUPPORTED_PLATFORM"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    COMPONENT_UNAVAILABLE = "COMPONENT_UNAVAILABLE"
    NON_AGGREGATABLE_SUMMATION_REJECTED = "NON_AGGREGATABLE_SUMMATION_REJECTED"
