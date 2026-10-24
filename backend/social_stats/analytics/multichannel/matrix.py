"""
Facebook ↔ Instagram Multichannel Metric Compatibility Matrix.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Explicitly maps every canonical metric from the Bop Social Metric Registry:
1. REACH
2. AVERAGE_DAILY_REACH
3. IMPRESSIONS
4. FOLLOWERS_TOTAL
5. FOLLOWERS_NET_CHANGE
6. PROFILE_VIEWS
7. CLICKS_TOTAL
8. ENGAGEMENT_TOTAL
9. REACTIONS
10. COMMENTS
11. SHARES
12. SAVES
13. VIDEO_VIEWS
14. VIDEO_WATCH_TIME
15. VIDEO_AVG_WATCH_TIME

No metric is assumed comparable solely based on matching names.
"""
from typing import Dict
from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    NormalizationType,
    ComparisonReasonCode,
)
from .rules import MetricComparisonRule, register_rule


FB_IG_RULES: Dict[str, MetricComparisonRule] = {
    "REACH": MetricComparisonRule(
        metric="REACH",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["REACH"],
        minimum_sample=1,
        notes=(
            "Unique accounts reached. Valid across Facebook and Instagram only when comparing provider-supplied "
            "period-level unique reach. Arithmetic summation across daily reach is strictly rejected due to "
            "audience overlap."
        ),
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "AVERAGE_DAILY_REACH": MetricComparisonRule(
        metric="AVERAGE_DAILY_REACH",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.DAILY_AVERAGE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["REACH"],
        minimum_sample=1,
        notes=(
            "Daily average unique reach. May only be compared against the identical metric identity "
            "(AVERAGE_DAILY_REACH), never relabeled or confused with total period reach."
        ),
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "IMPRESSIONS": MetricComparisonRule(
        metric="IMPRESSIONS",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["IMPRESSIONS"],
        minimum_sample=1,
        notes=(
            "Total content impressions. Fully supported on Facebook Page insights. Instagram Graph API v18+ "
            "deprecated single-media impressions in favor of reach; comparison is conditional on source availability."
        ),
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "FOLLOWERS_TOTAL": MetricComparisonRule(
        metric="FOLLOWERS_TOTAL",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.LATEST_VALUE,
        direction=ComparisonDirection.NEUTRAL,
        rankable=False,
        required_metrics=["FOLLOWERS_TOTAL"],
        minimum_sample=1,
        notes=(
            "Audience volume gauge. Values are directly comparable as point-in-time audience size, but "
            "direction is strictly NEUTRAL and non-rankable for performance competition (winner is always NO_WINNER)."
        ),
        default_reason_code=ComparisonReasonCode.NON_RANKABLE_METRIC,
    ),
    "FOLLOWERS_NET_CHANGE": MetricComparisonRule(
        metric="FOLLOWERS_NET_CHANGE",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.DELTA,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["FOLLOWERS_NET_CHANGE"],
        minimum_sample=1,
        notes="Net audience shift (gains minus unfollows) over aligned period.",
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "PROFILE_VIEWS": MetricComparisonRule(
        metric="PROFILE_VIEWS",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=False,
        required_metrics=["PROFILE_VIEWS"],
        minimum_sample=1,
        notes=(
            "Semantic discrepancy: Facebook measures logged-in Page views whereas Instagram measures profile visits. "
            "Informational comparison only; direct competitive ranking disallowed without explicit normalization."
        ),
        default_reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
    ),
    "CLICKS_TOTAL": MetricComparisonRule(
        metric="CLICKS_TOTAL",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=False,
        required_metrics=["CLICKS_TOTAL"],
        minimum_sample=1,
        notes=(
            "Semantic discrepancy: Facebook aggregates post clicks, link clicks, and photo views; Instagram feed posts "
            "do not support outbound links and only measure bio website clicks. Informational only, non-rankable."
        ),
        default_reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
    ),
    "ENGAGEMENT_TOTAL": MetricComparisonRule(
        metric="ENGAGEMENT_TOTAL",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["REACTIONS", "COMMENTS", "SHARES"],
        minimum_sample=1,
        notes=(
            "Requires all canonical components: REACTIONS + COMMENTS + SHARES. If any required component is unavailable "
            "(e.g. Instagram in PARTIAL mode lacking SHARES), ENGAGEMENT_TOTAL comparison status is UNAVAILABLE. "
            "Never substitute partial components."
        ),
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "REACTIONS": MetricComparisonRule(
        metric="REACTIONS",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["REACTIONS"],
        minimum_sample=1,
        notes="Directly comparable count of positive user interactions / likes.",
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "COMMENTS": MetricComparisonRule(
        metric="COMMENTS",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["COMMENTS"],
        minimum_sample=1,
        notes="Directly comparable count of user comments and replies.",
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "SHARES": MetricComparisonRule(
        metric="SHARES",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.CONDITIONAL,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["SHARES"],
        minimum_sample=1,
        notes=(
            "Direct redistribution count. Conditional on runtime provider capabilities: Facebook supports Page shares "
            "natively; Instagram requires professional insight permissions and is unavailable under Basic/Partial mode."
        ),
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "SAVES": MetricComparisonRule(
        metric="SAVES",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.NON_COMPARABLE,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.NOT_APPLICABLE,
        rankable=False,
        required_metrics=["SAVES"],
        minimum_sample=1,
        notes="Instagram provides post saves/bookmarks; organic Facebook posts do not expose a public saves metric.",
        default_reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
    ),
    "VIDEO_VIEWS": MetricComparisonRule(
        metric="VIDEO_VIEWS",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.NON_COMPARABLE,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.NOT_APPLICABLE,
        rankable=False,
        required_metrics=["VIDEO_VIEWS"],
        minimum_sample=1,
        notes=(
            "Measurement threshold discrepancy: Facebook measures 3-second continuous views; Instagram measures Reel "
            "plays/starts including autoloops. Cross-platform raw volume ranking disallowed."
        ),
        default_reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
    ),
    "VIDEO_WATCH_TIME": MetricComparisonRule(
        metric="VIDEO_WATCH_TIME",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.NONE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["VIDEO_WATCH_TIME"],
        minimum_sample=1,
        notes="Cumulative viewer elapsed watch time normalized to seconds.",
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
    "VIDEO_AVG_WATCH_TIME": MetricComparisonRule(
        metric="VIDEO_AVG_WATCH_TIME",
        platform_a="facebook",
        platform_b="instagram",
        compatibility=ComparisonCompatibility.DIRECT,
        normalization=NormalizationType.DAILY_AVERAGE,
        direction=ComparisonDirection.HIGHER_IS_BETTER,
        rankable=True,
        required_metrics=["VIDEO_AVG_WATCH_TIME"],
        minimum_sample=1,
        notes="Average watch time per session in seconds. Must be averaged, never summed across time.",
        default_reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
    ),
}

# Auto-register all Facebook ↔ Instagram rules upon module import
for rule in FB_IG_RULES.values():
    register_rule(rule)
