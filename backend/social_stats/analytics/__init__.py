"""
Analytics package for Bop Social.
Exposes canonical metric registry, capabilities, normalizers, derived calculations, and ingestion services.
"""
from .registry import (
    AggregationBehavior,
    MetricValueType,
    MetricUnit,
    FreshnessState,
    MetricScope,
    MetricDefinition,
    CANONICAL_METRICS,
    get_metric_definition,
    is_valid_metric,
    get_canonical_keys,
)
from .capabilities import (
    SupportLevel,
    ProviderCapability,
    PROVIDER_CAPABILITIES,
    get_provider_capability,
)
from .normalizers import (
    NormalizedObservation,
    normalize_facebook_metric,
    normalize_instagram_metric,
    normalize_metric,
)
from .derived import (
    calculate_engagement_total,
    calculate_engagement_rate_reach,
    calculate_engagement_rate_followers,
    calculate_follower_growth_rate,
)
from .ingestion import (
    compute_dimensions_hash,
    find_publish_log_and_unified_post,
    ingest_metric_snapshot,
    ingest_observations,
)

__all__ = [
    "AggregationBehavior",
    "MetricValueType",
    "MetricUnit",
    "FreshnessState",
    "MetricScope",
    "MetricDefinition",
    "CANONICAL_METRICS",
    "get_metric_definition",
    "is_valid_metric",
    "get_canonical_keys",
    "SupportLevel",
    "ProviderCapability",
    "PROVIDER_CAPABILITIES",
    "get_provider_capability",
    "NormalizedObservation",
    "normalize_facebook_metric",
    "normalize_instagram_metric",
    "normalize_metric",
    "calculate_engagement_total",
    "calculate_engagement_rate_reach",
    "calculate_engagement_rate_followers",
    "calculate_follower_growth_rate",
    "compute_dimensions_hash",
    "find_publish_log_and_unified_post",
    "ingest_metric_snapshot",
    "ingest_observations",
]
