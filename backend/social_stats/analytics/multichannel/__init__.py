"""
Multichannel Metric Compatibility & Comparison Package.
Phase BS-5A & BS-5B: Multichannel Metric Compatibility, Comparison & Benchmark Engine.

Exports the core taxonomies, rules, matrix, pure calculation utilities,
comparison service, and benchmark build service.
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
from .benchmarks import (
    BENCHMARK_SCHEMA_VERSION,
    CANONICAL_METRIC_ORDER,
    CoverageSummary,
    WinnerSummary,
    MultichannelBenchmarkResult,
    generate_benchmark_hash,
    evaluate_content_cohorts,
    build_multichannel_benchmark,
)
from .signals import (
    MultichannelSignalType,
    SignalCategory,
    SignalSeverity,
    ConfidenceTier,
    RecommendedActionCode,
    MATERIALITY_THRESHOLDS,
    FORBIDDEN_SIGNAL_TYPES,
    compute_multichannel_signal_identity,
    format_signal_description,
    validate_signal_candidate,
    MultichannelSignalValidationError,
    generate_multichannel_signals,
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
    # Benchmark Engine
    "BENCHMARK_SCHEMA_VERSION",
    "CANONICAL_METRIC_ORDER",
    "CoverageSummary",
    "WinnerSummary",
    "MultichannelBenchmarkResult",
    "generate_benchmark_hash",
    "evaluate_content_cohorts",
    "build_multichannel_benchmark",
    # Multichannel Signal Engine (BS-5C)
    "MultichannelSignalType",
    "SignalCategory",
    "SignalSeverity",
    "ConfidenceTier",
    "RecommendedActionCode",
    "MATERIALITY_THRESHOLDS",
    "FORBIDDEN_SIGNAL_TYPES",
    "compute_multichannel_signal_identity",
    "format_signal_description",
    "validate_signal_candidate",
    "MultichannelSignalValidationError",
    "generate_multichannel_signals",
]

