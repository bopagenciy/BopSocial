"""
Analytics package for Bop Social.
Exposes canonical metric registry, capabilities, normalizers, derived calculations,
ingestion services, adapters, rate limiters, and synchronization services.
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
from .exceptions import (
    AnalyticsError,
    AnalyticsAuthExpiredError,
    AnalyticsPermissionError,
    AnalyticsRateLimitedError,
    AnalyticsObjectUnavailableError,
    AnalyticsMetricUnsupportedError,
    AnalyticsTemporaryProviderError,
    classify_provider_error,
)
from .rate_limits import (
    parse_meta_rate_limit_headers,
    update_credential_rate_limit_state,
    evaluate_throttling,
)
from .adapters import (
    BaseAnalyticsAdapter,
    ProviderPayload,
    FacebookAnalyticsAdapter,
    InstagramAnalyticsAdapter,
    has_instagram_insights_capability,
)
from .sync_service import (
    SyncResult,
    sync_facebook_analytics,
    sync_instagram_analytics,
)
from .rollups import (
    get_client_timezone,
    calculate_period_start,
    aggregate_snapshots,
    build_rollups_for_client,
)
from .freshness import (
    evaluate_freshness,
    get_client_platform_freshness,
)
from .orchestrator import (
    acquire_sync_lock,
    release_sync_lock,
    is_sync_due,
    run_analytics_orchestrator,
)
from .backfill import (
    backfill_rollups,
)
from .api import (
    AnalyticsSummaryView,
    AnalyticsTrendsView,
    AnalyticsTopPostsView,
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
    "AnalyticsError",
    "AnalyticsAuthExpiredError",
    "AnalyticsPermissionError",
    "AnalyticsRateLimitedError",
    "AnalyticsObjectUnavailableError",
    "AnalyticsMetricUnsupportedError",
    "AnalyticsTemporaryProviderError",
    "classify_provider_error",
    "parse_meta_rate_limit_headers",
    "update_credential_rate_limit_state",
    "evaluate_throttling",
    "BaseAnalyticsAdapter",
    "ProviderPayload",
    "FacebookAnalyticsAdapter",
    "InstagramAnalyticsAdapter",
    "has_instagram_insights_capability",
    "SyncResult",
    "sync_facebook_analytics",
    "sync_instagram_analytics",
    "get_client_timezone",
    "calculate_period_start",
    "aggregate_snapshots",
    "build_rollups_for_client",
    "evaluate_freshness",
    "get_client_platform_freshness",
    "acquire_sync_lock",
    "release_sync_lock",
    "is_sync_due",
    "run_analytics_orchestrator",
    "backfill_rollups",
    "AnalyticsSummaryView",
    "AnalyticsTrendsView",
    "AnalyticsTopPostsView",
]
