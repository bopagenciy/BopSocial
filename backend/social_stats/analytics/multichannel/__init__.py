"""
Multichannel Metric Compatibility & Comparison Package.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Exports the core taxonomies, rules, matrix, pure calculation utilities,
and comparison service.
"""
from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    NormalizationType,
    ComparisonWinner,
    ComparisonStatus,
    ComparisonReasonCode,
)
from .labels import (
    REASON_LABELS,
    STATUS_LABELS,
    WINNER_LABELS,
    get_reason_labels,
    get_status_labels,
    get_winner_labels,
)
from .rules import (
    MetricComparisonRule,
    register_rule,
    get_metric_comparison_rule,
    get_all_registered_rules,
)
from .matrix import (
    FB_IG_RULES,
)
from .comparison import (
    calculate_absolute_delta,
    calculate_relative_delta,
    determine_winner,
    ComparisonResult,
    compare_metric_across_platforms,
)

__all__ = [
    # Taxonomies
    "ComparisonCompatibility",
    "ComparisonDirection",
    "NormalizationType",
    "ComparisonWinner",
    "ComparisonStatus",
    "ComparisonReasonCode",
    # Labels
    "REASON_LABELS",
    "STATUS_LABELS",
    "WINNER_LABELS",
    "get_reason_labels",
    "get_status_labels",
    "get_winner_labels",
    # Rules & Matrix
    "MetricComparisonRule",
    "register_rule",
    "get_metric_comparison_rule",
    "get_all_registered_rules",
    "FB_IG_RULES",
    # Comparison Engine
    "calculate_absolute_delta",
    "calculate_relative_delta",
    "determine_winner",
    "ComparisonResult",
    "compare_metric_across_platforms",
]
