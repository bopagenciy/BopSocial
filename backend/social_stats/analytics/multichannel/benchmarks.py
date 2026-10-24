"""
Cross-Platform Benchmark and Comparison Engine.
Phase BS-5B: Cross-Platform Benchmark & Comparison Engine.

Orchestrates deterministic multi-metric evaluations against normalized Bop Social analytics telemetry.
Guarantees:
- BS-5A compatibility rule consumption without duplication.
- Deterministic 15-metric canonical ordering.
- Deterministic SHA256 benchmark_hash identity.
- Metric-level provider capability binding.
- Reach aggregation safety (summation rejected).
- Safe relative delta (zero baseline handling).
- No overall platform winner (per-metric results only).
- Bounded, bulk-loaded query strategy (eliminates N+1).
- Zero database writes / 100% read-only operation.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db.models import Avg, Count
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    UnifiedPost,
    PlatformPublishLog,
    PostMetric,
)
from .comparison import (
    ComparisonResult,
    compare_metric_across_platforms,
    calculate_absolute_delta,
    calculate_relative_delta,
    determine_winner,
)
from .labels import get_reason_labels
from .rules import get_metric_comparison_rule
from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    ComparisonReasonCode,
    ComparisonStatus,
    ComparisonWinner,
    NormalizationType,
)

logger = logging.getLogger(__name__)

BENCHMARK_SCHEMA_VERSION = "bs5b-benchmark-v1"

CANONICAL_METRIC_ORDER = [
    "REACH",
    "AVERAGE_DAILY_REACH",
    "IMPRESSIONS",
    "FOLLOWERS_TOTAL",
    "FOLLOWERS_NET_CHANGE",
    "PROFILE_VIEWS",
    "CLICKS_TOTAL",
    "ENGAGEMENT_TOTAL",
    "REACTIONS",
    "COMMENTS",
    "SHARES",
    "SAVES",
    "VIDEO_VIEWS",
    "VIDEO_WATCH_TIME",
    "VIDEO_AVG_WATCH_TIME",
]

ALLOWED_GRANULARITIES = {"day", "week", "month", "period"}
MINIMUM_COHORT_SAMPLE = 3


# ==============================================================================
# BENCHMARK DOMAIN MODELS
# ==============================================================================

@dataclass(frozen=True)
class CoverageSummary:
    """Diagnostic metric coverage counts across the benchmark evaluation."""
    total_metrics: int
    comparable_metrics: int
    rankable_metrics: int
    non_rankable_metrics: int
    unavailable_metrics: int
    non_comparable_metrics: int
    invalid_metrics: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_metrics": self.total_metrics,
            "comparable_metrics": self.comparable_metrics,
            "rankable_metrics": self.rankable_metrics,
            "non_rankable_metrics": self.non_rankable_metrics,
            "unavailable_metrics": self.unavailable_metrics,
            "non_comparable_metrics": self.non_comparable_metrics,
            "invalid_metrics": self.invalid_metrics,
        }


@dataclass(frozen=True)
class WinnerSummary:
    """
    Summary tally of winning platforms across rankable metrics.
    Explicitly NO overall winner: metrics have heterogeneous scales and semantics.
    """
    platform_a_wins: int
    platform_b_wins: int
    ties: int
    no_winner: int
    unavailable: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "platform_a_wins": self.platform_a_wins,
            "platform_b_wins": self.platform_b_wins,
            "ties": self.ties,
            "no_winner": self.no_winner,
            "unavailable": self.unavailable,
        }


@dataclass(frozen=True)
class MultichannelBenchmarkResult:
    """
    Deterministic benchmark object encapsulating multi-metric cross-platform results,
    evidence provenance, and stable hash identity.
    """
    schema_version: str
    client_id: int
    platform_a: str
    platform_b: str
    period_start: date
    period_end: date
    granularity: str
    benchmark_hash: str
    coverage_summary: CoverageSummary
    winner_summary: WinnerSummary
    metric_results: List[ComparisonResult]
    cohort_results: Optional[List[Dict[str, Any]]] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "client_id": self.client_id,
            "platform_a": self.platform_a,
            "platform_b": self.platform_b,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "granularity": self.granularity,
            "benchmark_hash": self.benchmark_hash,
            "coverage_summary": self.coverage_summary.to_dict(),
            "winner_summary": self.winner_summary.to_dict(),
            "metric_results": [r.to_dict() for r in self.metric_results],
            "cohort_results": self.cohort_results or [],
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


# ==============================================================================
# DETERMINISTIC BENCHMARK IDENTITY HASH
# ==============================================================================

def generate_benchmark_hash(
    *,
    schema_version: str,
    client_id: int,
    platform_a: str,
    platform_b: str,
    period_start: date,
    period_end: date,
    granularity: str,
    metric_results: List[ComparisonResult],
) -> str:
    """
    Generates a deterministic SHA256 identity hash for the benchmark.
    Inputs are strictly canonicalized (no random IDs, no timestamps).
    Guarantees:
    - Same request + same underlying data = exact same hash.
    - Any change in underlying metrics/source data = altered hash.
    - Platform ordering (platform_a vs platform_b) is part of identity.
    """
    canonical_items = []
    # Sort results strictly according to canonical metric order
    metric_order_map = {m: i for i, m in enumerate(CANONICAL_METRIC_ORDER)}
    sorted_results = sorted(
        metric_results,
        key=lambda r: metric_order_map.get(r.metric, 999),
    )

    for r in sorted_results:
        canonical_items.append({
            "metric": r.metric,
            "status": r.status.value,
            "compatibility": r.compatibility.value,
            "direction": r.direction.value,
            "normalization": r.normalization.value,
            "rankable": r.rankable,
            "value_a": float(r.value_a) if r.value_a is not None else None,
            "value_b": float(r.value_b) if r.value_b is not None else None,
            "delta_absolute": float(r.delta_absolute) if r.delta_absolute is not None else None,
            "delta_relative": float(r.delta_relative) if r.delta_relative is not None else None,
            "winner": r.winner.value,
            "reason_code": r.reason_code.value,
            "sample_a": r.sample_a,
            "sample_b": r.sample_b,
        })

    payload = {
        "schema_version": schema_version,
        "client_id": client_id,
        "platform_a": platform_a.strip().lower(),
        "platform_b": platform_b.strip().lower(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "granularity": granularity.strip().lower(),
        "metrics": canonical_items,
    }

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ==============================================================================
# CONTENT COHORT BENCHMARKING (OPTIONAL SUPPORT)
# ==============================================================================

def evaluate_content_cohorts(
    *,
    client: Client,
    platform_a: str,
    platform_b: str,
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
    """
    Evaluates format/content cohorts (IMAGE, VIDEO, CAROUSEL) across platforms.
    Enforces minimum sample size threshold (n >= 3).
    If sample < 3: status is UNAVAILABLE, reason INSUFFICIENT_SAMPLE, winner NO_WINNER.
    """
    cohort_formats = ["IMAGE", "VIDEO", "CAROUSEL"]
    cohort_results = []

    # Query published posts within window
    posts = list(
        UnifiedPost.objects.filter(
            client=client,
            status="published",
            published_at__date__gte=start_date,
            published_at__date__lte=end_date,
        ).values("id", "media_type", "target_platforms")
    )

    counts: Dict[Tuple[str, str], int] = {}
    for p in posts:
        mtype = (p.get("media_type") or "image").strip().upper()
        targets = [str(t).strip().lower() for t in (p.get("target_platforms") or [])]
        for plat in (platform_a, platform_b):
            if plat in targets:
                counts[(plat, mtype)] = counts.get((plat, mtype), 0) + 1

    # Also check PlatformPublishLog if no UnifiedPost target_platforms were matched
    if not posts:
        logs = list(
            PlatformPublishLog.objects.filter(
                unified_post__client=client,
                platform__in=[platform_a, platform_b],
                status="success",
                completed_at__date__gte=start_date,
                completed_at__date__lte=end_date,
            ).values("id", "platform", "unified_post__media_type")
        )
        for l in logs:
            plat = l["platform"].strip().lower()
            mtype = (l.get("unified_post__media_type") or "image").strip().upper()
            counts[(plat, mtype)] = counts.get((plat, mtype), 0) + 1

    for fmt in cohort_formats:
        n_a = counts.get((platform_a, fmt), 0)
        n_b = counts.get((platform_b, fmt), 0)

        if n_a < MINIMUM_COHORT_SAMPLE or n_b < MINIMUM_COHORT_SAMPLE:
            rc = ComparisonReasonCode.INSUFFICIENT_SAMPLE
            cohort_results.append({
                "cohort_type": "format",
                "cohort_value": fmt,
                "status": ComparisonStatus.UNAVAILABLE.value,
                "sample_a": n_a,
                "sample_b": n_b,
                "minimum_sample": MINIMUM_COHORT_SAMPLE,
                "winner": ComparisonWinner.NO_WINNER.value,
                "reason_code": rc.value,
                "reason_labels": get_reason_labels(rc),
                "notes": f"Insufficient sample size: {platform_a} has {n_a}, {platform_b} has {n_b} (min {MINIMUM_COHORT_SAMPLE} required).",
            })
        else:
            cohort_results.append({
                "cohort_type": "format",
                "cohort_value": fmt,
                "status": ComparisonStatus.AVAILABLE.value,
                "sample_a": n_a,
                "sample_b": n_b,
                "minimum_sample": MINIMUM_COHORT_SAMPLE,
                "winner": ComparisonWinner.NO_WINNER.value,
                "reason_code": ComparisonReasonCode.DIRECTLY_COMPARABLE.value,
                "reason_labels": get_reason_labels(ComparisonReasonCode.DIRECTLY_COMPARABLE),
                "notes": f"Sufficient sample count available ({n_a} vs {n_b}).",
            })

    return cohort_results


# ==============================================================================
# BENCHMARK BUILD SERVICE
# ==============================================================================

def build_multichannel_benchmark(
    *,
    client: Client,
    platform_a: str,
    platform_b: str,
    start_date: date,
    end_date: date,
    granularity: str = "day",
    metrics: Optional[List[str]] = None,
    include_cohorts: bool = False,
) -> MultichannelBenchmarkResult:
    """
    Executes a deterministic multichannel benchmark evaluation for a client across an aligned period.
    Bulk-loads required rollup and snapshot telemetry to strictly eliminate N+1 queries.
    Operates strictly read-only: performs 0 database writes and 0 provider calls.
    """
    if client is None:
        raise ValueError("Client must be provided.")

    plat_a = (platform_a or "").strip().lower()
    plat_b = (platform_b or "").strip().lower()

    if plat_a == plat_b:
        raise ValueError(f"Cannot compare platform '{plat_a}' to itself.")

    if not plat_a or not plat_b:
        raise ValueError("Both platform_a and platform_b must be specified.")

    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) cannot be after end_date ({end_date}).")

    gran = (granularity or "day").strip().lower()
    if gran not in ALLOWED_GRANULARITIES:
        raise ValueError(f"Unsupported granularity '{gran}'. Must be one of: {sorted(list(ALLOWED_GRANULARITIES))}")

    # Determine metric evaluation set
    if metrics:
        metrics_to_run = [m.strip().upper() for m in metrics if m.strip()]
    else:
        metrics_to_run = list(CANONICAL_METRIC_ORDER)

    # 1. Bulk-load active credentials for platform_a and platform_b (Query 1)
    creds_list = list(
        PlatformCredential.objects.defer("access_token", "refresh_token").filter(
            client=client,
            platform__in=[plat_a, plat_b],
            is_active=True,
        )
    )
    preloaded_creds = {c.platform.strip().lower(): c for c in creds_list}

    # 2. Bulk-load rollups in the requested date range (Query 2)
    rollups_qs = SocialMetricRollup.objects.filter(
        client=client,
        platform__in=[plat_a, plat_b],
        period_start__gte=start_date,
        period_start__lte=end_date,
    )
    all_rollups = list(rollups_qs)

    preloaded_rollups: Dict[Tuple[str, str], List[SocialMetricRollup]] = {}
    for r in all_rollups:
        key = (r.platform.strip().lower(), r.normalized_metric.strip().upper())
        preloaded_rollups.setdefault(key, []).append(r)

    # 3. Bulk-load snapshots in the requested date range (Query 3)
    snapshots_qs = SocialMetricSnapshot.objects.filter(
        client=client,
        platform__in=[plat_a, plat_b],
        bucket_timestamp__date__gte=start_date,
        bucket_timestamp__date__lte=end_date,
    )
    all_snapshots = list(snapshots_qs)

    preloaded_snapshots: Dict[Tuple[str, str], List[SocialMetricSnapshot]] = {}
    for s in all_snapshots:
        key = (s.platform.strip().lower(), s.normalized_metric.strip().upper())
        preloaded_snapshots.setdefault(key, []).append(s)

    # 4. Evaluate each metric in canonical order
    results: List[ComparisonResult] = []
    for m in metrics_to_run:
        res = compare_metric_across_platforms(
            client=client,
            metric=m,
            platform_a=plat_a,
            platform_b=plat_b,
            start_date=start_date,
            end_date=end_date,
            period=gran,
            preloaded_rollups=preloaded_rollups,
            preloaded_snapshots=preloaded_snapshots,
            preloaded_credentials=preloaded_creds,
        )
        results.append(res)

    # 5. Compute CoverageSummary
    total_m = len(results)
    comp_m = sum(1 for r in results if r.status == ComparisonStatus.AVAILABLE)
    rank_m = sum(1 for r in results if r.status == ComparisonStatus.AVAILABLE and r.rankable)
    non_rank_m = sum(1 for r in results if r.status == ComparisonStatus.AVAILABLE and not r.rankable)
    unavail_m = sum(1 for r in results if r.status == ComparisonStatus.UNAVAILABLE and r.compatibility != ComparisonCompatibility.NON_COMPARABLE)
    non_comp_m = sum(1 for r in results if r.compatibility == ComparisonCompatibility.NON_COMPARABLE)
    inv_m = sum(1 for r in results if r.status == ComparisonStatus.INVALID)

    coverage_summary = CoverageSummary(
        total_metrics=total_m,
        comparable_metrics=comp_m,
        rankable_metrics=rank_m,
        non_rankable_metrics=non_rank_m,
        unavailable_metrics=unavail_m,
        non_comparable_metrics=non_comp_m,
        invalid_metrics=inv_m,
    )

    # 6. Compute WinnerSummary (No overall winner!)
    wins_a = sum(1 for r in results if r.winner == ComparisonWinner.PLATFORM_A)
    wins_b = sum(1 for r in results if r.winner == ComparisonWinner.PLATFORM_B)
    ties = sum(1 for r in results if r.winner == ComparisonWinner.TIE)
    no_win = sum(1 for r in results if r.winner == ComparisonWinner.NO_WINNER)
    unavail_win = sum(1 for r in results if r.winner == ComparisonWinner.UNAVAILABLE)

    winner_summary = WinnerSummary(
        platform_a_wins=wins_a,
        platform_b_wins=wins_b,
        ties=ties,
        no_winner=no_win,
        unavailable=unavail_win,
    )

    # 7. Generate deterministic benchmark hash
    b_hash = generate_benchmark_hash(
        schema_version=BENCHMARK_SCHEMA_VERSION,
        client_id=client.id,
        platform_a=plat_a,
        platform_b=plat_b,
        period_start=start_date,
        period_end=end_date,
        granularity=gran,
        metric_results=results,
    )

    # 8. Optional cohort evaluations
    cohort_results = None
    if include_cohorts:
        cohort_results = evaluate_content_cohorts(
            client=client,
            platform_a=plat_a,
            platform_b=plat_b,
            start_date=start_date,
            end_date=end_date,
        )

    # 9. Machine evidence payload
    evidence = {
        "client_id": client.id,
        "platform_a": plat_a,
        "platform_b": plat_b,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "granularity": gran,
        "rollups_scanned": len(all_rollups),
        "snapshots_scanned": len(all_snapshots),
        "credentials_loaded": list(preloaded_creds.keys()),
        "rule_version": "BS-5A",
    }

    return MultichannelBenchmarkResult(
        schema_version=BENCHMARK_SCHEMA_VERSION,
        client_id=client.id,
        platform_a=plat_a,
        platform_b=plat_b,
        period_start=start_date,
        period_end=end_date,
        granularity=gran,
        benchmark_hash=b_hash,
        coverage_summary=coverage_summary,
        winner_summary=winner_summary,
        metric_results=results,
        cohort_results=cohort_results,
        evidence=evidence,
        metadata={
            "rules_applied": len(results),
            "no_overall_winner_enforced": True,
        },
    )
