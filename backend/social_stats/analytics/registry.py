"""
Canonical Analytics Metric Registry for Bop Social.

Defines the single source of truth for normalized social metric definitions,
aggregation behaviors, cross-platform comparability, and freshness states.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


class AggregationBehavior(str, Enum):
    """
    Classifies how a metric behaves mathematically across time and entities.
    """
    SUMMABLE = "SUMMABLE"                 # Discrete counts that can be summed (e.g. reactions, shares)
    LATEST_VALUE = "LATEST_VALUE"         # Point-in-time gauge; must not be summed across dates (e.g. followers)
    DELTA = "DELTA"                       # Net change within a time bucket (e.g. net follower change)
    AVERAGE = "AVERAGE"                   # Ratio/duration that must be averaged, not summed (e.g. avg watch time)
    NON_AGGREGATABLE = "NON_AGGREGATABLE" # Unique sets that cannot be summed due to audience overlap (e.g. reach)


class MetricValueType(str, Enum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    PERCENTAGE = "percentage"
    DURATION_SECONDS = "duration_seconds"


class MetricUnit(str, Enum):
    COUNT = "count"
    SECONDS = "seconds"
    PERCENT = "percent"
    RATIO = "ratio"


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class MetricScope(str, Enum):
    ACCOUNT = "account"
    POST = "post"
    STORY = "story"
    REEL = "reel"
    VIDEO = "video"
    CAMPAIGN = "campaign"


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    value_type: MetricValueType
    unit: MetricUnit
    aggregation_behavior: AggregationBehavior
    allowed_scopes: Set[MetricScope]
    semantic_description: str
    cross_platform_comparability: str
    higher_is_better: bool = True
    metadata: Dict = field(default_factory=dict)


CANONICAL_METRICS: Dict[str, MetricDefinition] = {
    "REACH": MetricDefinition(
        key="REACH",
        display_name="Reach",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.NON_AGGREGATABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.STORY, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Unique accounts/users that saw the content at least once during the reporting period.",
        cross_platform_comparability=(
            "Generally comparable across Facebook and Instagram (unique users). Cannot be summed across multiple days "
            "because the same user may view content on consecutive days."
        ),
        higher_is_better=True,
    ),
    "IMPRESSIONS": MetricDefinition(
        key="IMPRESSIONS",
        display_name="Impressions",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.STORY},
        semantic_description="Total number of times content entered the screen, including multiple views by the same person.",
        cross_platform_comparability=(
            "Provider-specific. Fully supported on Facebook Pages and posts. In Instagram Graph API v18+, "
            "impressions are deprecated on single media in favor of reach and interaction metrics."
        ),
        higher_is_better=True,
    ),
    "FOLLOWERS_TOTAL": MetricDefinition(
        key="FOLLOWERS_TOTAL",
        display_name="Total Followers",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.LATEST_VALUE,
        allowed_scopes={MetricScope.ACCOUNT},
        semantic_description="Total active followers/fans as of the reporting timestamp.",
        cross_platform_comparability=(
            "Directly comparable across Facebook (followers_count / fan_count) and Instagram (follower_count). "
            "Must never be summed across calendar days."
        ),
        higher_is_better=True,
    ),
    "FOLLOWERS_NET_CHANGE": MetricDefinition(
        key="FOLLOWERS_NET_CHANGE",
        display_name="Followers Net Change",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.DELTA,
        allowed_scopes={MetricScope.ACCOUNT},
        semantic_description="Net follower shift (gains minus unfollows) observed within the discrete time bucket.",
        cross_platform_comparability=(
            "Comparable. Computed from follows minus unfollows on both Facebook Page insights and Instagram account insights."
        ),
        higher_is_better=True,
    ),
    "PROFILE_VIEWS": MetricDefinition(
        key="PROFILE_VIEWS",
        display_name="Profile / Page Views",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT},
        semantic_description="Number of times the account profile or Facebook Page was viewed by users.",
        cross_platform_comparability=(
            "Comparable intent, but Facebook counts logged-in Page views while Instagram counts profile visits."
        ),
        higher_is_better=True,
    ),
    "CLICKS_TOTAL": MetricDefinition(
        key="CLICKS_TOTAL",
        display_name="Total Clicks / Actions",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.STORY},
        semantic_description="Total button clicks, website taps, direction clicks, or link clicks.",
        cross_platform_comparability=(
            "Not directly uniform: Facebook post_clicks includes link clicks, photo views, and 'see more'; "
            "Instagram feed posts do not support hyperlinks, so clicks on IG are restricted to profile website clicks."
        ),
        higher_is_better=True,
    ),
    "ENGAGEMENT_TOTAL": MetricDefinition(
        key="ENGAGEMENT_TOTAL",
        display_name="Total Engagement",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Sum of all user-initiated interactions (reactions, comments, shares, saves, clicks).",
        cross_platform_comparability=(
            "Comparable high-level engagement index. Can be derived from components or ingested from provider total_interactions."
        ),
        higher_is_better=True,
    ),
    "REACTIONS": MetricDefinition(
        key="REACTIONS",
        display_name="Reactions / Likes",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Positive reaction counters (likes on Instagram, like/love/wow/haha/sad/angry on Facebook).",
        cross_platform_comparability=(
            "Directly comparable for total like counts. Facebook additionally supports sub-dimension breakdown by reaction type."
        ),
        higher_is_better=True,
    ),
    "COMMENTS": MetricDefinition(
        key="COMMENTS",
        display_name="Comments",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Total top-level and reply comments submitted by users.",
        cross_platform_comparability="Directly comparable across Facebook and Instagram.",
        higher_is_better=True,
    ),
    "SHARES": MetricDefinition(
        key="SHARES",
        display_name="Shares / Reposts",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Total times content was forwarded, reposted, or sent via direct share.",
        cross_platform_comparability="Directly comparable.",
        higher_is_better=True,
    ),
    "SAVES": MetricDefinition(
        key="SAVES",
        display_name="Saves / Bookmarks",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Total times content was saved or bookmarked for later viewing.",
        cross_platform_comparability="Standard metric on Instagram; unavailable as a distinct public metric on organic Facebook posts.",
        higher_is_better=True,
    ),
    "VIDEO_VIEWS": MetricDefinition(
        key="VIDEO_VIEWS",
        display_name="Video Views / Plays",
        value_type=MetricValueType.INTEGER,
        unit=MetricUnit.COUNT,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Total video playbacks or view events as measured by the provider.",
        cross_platform_comparability=(
            "NOT directly comparable between Facebook 3-second video views and Instagram Reel 'plays' (starts/loops). "
            "Original raw provider metric identity must be preserved in snapshots."
        ),
        higher_is_better=True,
    ),
    "VIDEO_WATCH_TIME": MetricDefinition(
        key="VIDEO_WATCH_TIME",
        display_name="Total Video Watch Time",
        value_type=MetricValueType.DECIMAL,
        unit=MetricUnit.SECONDS,
        aggregation_behavior=AggregationBehavior.SUMMABLE,
        allowed_scopes={MetricScope.ACCOUNT, MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Cumulative elapsed watch time in seconds across all viewer sessions.",
        cross_platform_comparability="Comparable when normalized to seconds.",
        higher_is_better=True,
    ),
    "VIDEO_AVG_WATCH_TIME": MetricDefinition(
        key="VIDEO_AVG_WATCH_TIME",
        display_name="Average Watch Time",
        value_type=MetricValueType.DECIMAL,
        unit=MetricUnit.SECONDS,
        aggregation_behavior=AggregationBehavior.AVERAGE,
        allowed_scopes={MetricScope.POST, MetricScope.REEL, MetricScope.VIDEO},
        semantic_description="Mean viewing duration per session in seconds.",
        cross_platform_comparability="Comparable ratio. Must be averaged, never summed.",
        higher_is_better=True,
    ),
}


def get_metric_definition(metric_key: str) -> Optional[MetricDefinition]:
    """Retrieve canonical definition or return None."""
    if not metric_key:
        return None
    return CANONICAL_METRICS.get(metric_key.strip().upper())


def is_valid_metric(metric_key: str) -> bool:
    """Validate whether key exists in canonical registry."""
    return get_metric_definition(metric_key) is not None


def get_canonical_keys() -> List[str]:
    """Return sorted list of all canonical metric keys."""
    return sorted(list(CANONICAL_METRICS.keys()))
