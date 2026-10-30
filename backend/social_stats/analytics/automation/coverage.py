"""
Target-period completeness evaluation engine for BS-6D.0C Intelligence Automation.
Distinguishes recent provider sync freshness from temporal period data completeness.
Enforces fail-closed completeness gates, platform-aware capability handling,
and sample-level rollup validation.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Set

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
)
from social_stats.analytics.capabilities import get_provider_capability, SupportLevel
from social_stats.analytics.registry import CANONICAL_METRICS
from .constants import (
    CoverageCode,
    DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT,
)


@dataclass
class PlatformCoverage:
    platform: str
    credential_active: bool
    capability_mode: str
    snapshot_count: int
    snapshot_distinct_days: int
    snapshot_coverage_percent: float
    earliest_snapshot_date: Optional[str]
    latest_snapshot_date: Optional[str]
    available_metrics: List[str]
    unavailable_metrics: List[str]
    rollup_distinct_days: int
    rollup_month_samples: Optional[int]
    coverage_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "credential_active": self.credential_active,
            "capability_mode": self.capability_mode,
            "snapshot_count": self.snapshot_count,
            "snapshot_distinct_days": self.snapshot_distinct_days,
            "snapshot_coverage_percent": self.snapshot_coverage_percent,
            "earliest_snapshot_date": self.earliest_snapshot_date,
            "latest_snapshot_date": self.latest_snapshot_date,
            "available_metrics": self.available_metrics,
            "unavailable_metrics": self.unavailable_metrics,
            "rollup_distinct_days": self.rollup_distinct_days,
            "rollup_month_samples": self.rollup_month_samples,
            "coverage_code": self.coverage_code,
        }


@dataclass
class CoverageResult:
    period_start: date
    period_end: date
    expected_days: int
    threshold_percent: int
    overall_code: CoverageCode
    overall_percent: float
    is_sufficient: bool
    is_multichannel_complete: bool
    platforms: Dict[str, Any] = field(default_factory=dict)
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "expected_days": self.expected_days,
            "threshold_percent": self.threshold_percent,
            "overall_code": self.overall_code.value if isinstance(self.overall_code, CoverageCode) else str(self.overall_code),
            "overall_percent": self.overall_percent,
            "is_sufficient": self.is_sufficient,
            "is_multichannel_complete": self.is_multichannel_complete,
            "platforms": {
                k: v.to_dict() if hasattr(v, "to_dict") else v
                for k, v in self.platforms.items()
            },
            "blocking_reasons": self.blocking_reasons,
            "warnings": self.warnings,
            "details": self.details,
        }


def evaluate_target_period_coverage(
    client_id: int,
    period_start: date,
    period_end: date,
    threshold_percent: int = DEFAULT_MINIMUM_PERIOD_COVERAGE_PERCENT,
) -> CoverageResult:
    """
    Evaluates whether the canonical target reporting period [period_start, period_end]
    has sufficient underlying telemetry (snapshots, rollups, and metric diversity).

    Enforces:
    1. Pure read-only operation (0 database writes, 0 network calls).
    2. Conservative fail-closed minimum coverage threshold (default: >= 80% of calendar days).
    3. At least one supported canonical platform with sufficient temporal coverage.
    4. Honest platform capability awareness: missing capability != zero; partial mode disclosed.
    5. Rollup validation: monthly rollup existence without underlying samples does not fake completeness.
    """
    expected_days = (period_end - period_start).days + 1
    if expected_days <= 0:
        return CoverageResult(
            period_start=period_start,
            period_end=period_end,
            expected_days=expected_days,
            threshold_percent=threshold_percent,
            overall_code=CoverageCode.INSUFFICIENT,
            overall_percent=0.0,
            is_sufficient=False,
            is_multichannel_complete=False,
            blocking_reasons=[f"INVALID_PERIOD_RANGE: period_start {period_start} > period_end {period_end}"],
        )

    # Inspect active platform credentials for this client
    creds_qs = PlatformCredential.objects.defer("access_token", "refresh_token").filter(
        client_id=client_id, is_active=True
    )
    creds_by_plat = {c.platform.lower(): c for c in creds_qs}

    if not creds_by_plat:
        return CoverageResult(
            period_start=period_start,
            period_end=period_end,
            expected_days=expected_days,
            threshold_percent=threshold_percent,
            overall_code=CoverageCode.NO_DATA,
            overall_percent=0.0,
            is_sufficient=False,
            is_multichannel_complete=False,
            blocking_reasons=["NO_ACTIVE_CREDENTIALS: no active platform credentials found"],
        )

    canonical_metric_names = sorted(list(CANONICAL_METRICS.keys()))
    platforms_coverage: Dict[str, PlatformCoverage] = {}
    warnings: List[str] = []
    blocking_reasons: List[str] = []

    # Evaluate each active connected platform
    for plat_name, cred in creds_by_plat.items():
        # 1. Snapshots
        snap_qs = SocialMetricSnapshot.objects.filter(
            client_id=client_id,
            platform=plat_name,
            bucket_timestamp__date__gte=period_start,
            bucket_timestamp__date__lte=period_end,
        )
        snap_dates = sorted(list(set(snap.bucket_timestamp.date() for snap in snap_qs)))
        distinct_snap_days = len(snap_dates)
        snap_count = snap_qs.count()
        snap_cov_pct = round((distinct_snap_days / float(expected_days)) * 100.0, 2)

        available_metrics = sorted(list(set(snap.normalized_metric for snap in snap_qs if snap.normalized_metric)))
        unavailable_metrics = [m for m in canonical_metric_names if m not in available_metrics]

        # 2. Rollups (Daily and Monthly)
        daily_rollups = SocialMetricRollup.objects.filter(
            client_id=client_id,
            platform=plat_name,
            period="day",
            period_start__gte=period_start,
            period_start__lte=period_end,
        )
        rollup_days = len(set(r.period_start for r in daily_rollups))

        month_rollups = SocialMetricRollup.objects.filter(
            client_id=client_id,
            platform=plat_name,
            period="month",
            period_start=period_start,
        )
        month_samples = None
        if month_rollups.exists():
            month_samples = max((r.sample_count for r in month_rollups), default=0)
            if month_samples < expected_days:
                warnings.append(
                    f"MONTH_ROLLUP_SAMPLE_DEFICIT: {plat_name} month rollup has sample_count={month_samples} < {expected_days} expected days"
                )

        # 3. Provider capability mode
        cap = get_provider_capability(plat_name, cred)
        cap_mode = cap.overall_support.value if hasattr(cap, "overall_support") else "UNKNOWN"

        if distinct_snap_days == 0:
            plat_code = CoverageCode.NO_DATA.value
        elif snap_cov_pct >= threshold_percent:
            plat_code = CoverageCode.SUFFICIENT.value
        else:
            plat_code = CoverageCode.INSUFFICIENT.value

        platforms_coverage[plat_name] = PlatformCoverage(
            platform=plat_name,
            credential_active=True,
            capability_mode=cap_mode,
            snapshot_count=snap_count,
            snapshot_distinct_days=distinct_snap_days,
            snapshot_coverage_percent=snap_cov_pct,
            earliest_snapshot_date=snap_dates[0].isoformat() if snap_dates else None,
            latest_snapshot_date=snap_dates[-1].isoformat() if snap_dates else None,
            available_metrics=available_metrics,
            unavailable_metrics=unavailable_metrics,
            rollup_distinct_days=rollup_days,
            rollup_month_samples=month_samples,
            coverage_code=plat_code,
        )

    # Determine overall tenant coverage
    # Find canonical primary platform (highest temporal coverage)
    best_plat_name = max(platforms_coverage.keys(), key=lambda p: platforms_coverage[p].snapshot_coverage_percent)
    best_plat = platforms_coverage[best_plat_name]
    overall_percent = best_plat.snapshot_coverage_percent

    # Check for platforms with zero data
    zero_data_platforms = [p for p, cov in platforms_coverage.items() if cov.snapshot_distinct_days == 0]
    for p in zero_data_platforms:
        warnings.append(
            f"PLATFORM_ZERO_COVERAGE: {p} has 0/{expected_days} days of data in period; cross-platform narrative claims are restricted"
        )

    # Check for partial capability platforms
    for p, cov in platforms_coverage.items():
        if cov.capability_mode == SupportLevel.PARTIAL.value:
            warnings.append(
                f"PLATFORM_PARTIAL_CAPABILITY: {p} operating in PARTIAL capability mode ({len(cov.available_metrics)}/{len(canonical_metric_names)} metrics available)"
            )

    all_zero = all(cov.snapshot_distinct_days == 0 for cov in platforms_coverage.values())
    if all_zero and threshold_percent > 0:
        overall_code = CoverageCode.NO_DATA
        is_sufficient = False
        is_multichannel_complete = False
        blocking_reasons.append(
            f"TARGET_PERIOD_COVERAGE_INSUFFICIENT: 0 days of telemetry across all platforms for period {period_start} to {period_end}"
        )
    elif best_plat.snapshot_coverage_percent < threshold_percent:
        overall_code = CoverageCode.INSUFFICIENT
        is_sufficient = False
        is_multichannel_complete = False
        blocking_reasons.append(
            f"TARGET_PERIOD_COVERAGE_INSUFFICIENT: platform '{best_plat_name}' temporal coverage "
            f"{best_plat.snapshot_coverage_percent:.1f}% ({best_plat.snapshot_distinct_days}/{expected_days} days) "
            f"is below minimum required {threshold_percent}%"
        )
    else:
        # At least one canonical platform meets or exceeds threshold (or threshold is 0)
        is_sufficient = True
        # Multichannel completeness requires ALL active connected platforms to meet threshold without zero coverage
        all_platforms_sufficient = all(
            cov.snapshot_coverage_percent >= threshold_percent for cov in platforms_coverage.values()
        )
        no_zero_platforms = len(zero_data_platforms) == 0
        has_partial_modes = any(cov.capability_mode == SupportLevel.PARTIAL.value for cov in platforms_coverage.values())

        if all_zero:
            overall_code = CoverageCode.NO_DATA
            is_multichannel_complete = False
        elif all_platforms_sufficient and no_zero_platforms and not has_partial_modes:
            overall_code = CoverageCode.SUFFICIENT
            is_multichannel_complete = True
        else:
            overall_code = CoverageCode.PARTIAL
            is_multichannel_complete = False

    return CoverageResult(
        period_start=period_start,
        period_end=period_end,
        expected_days=expected_days,
        threshold_percent=threshold_percent,
        overall_code=overall_code,
        overall_percent=overall_percent,
        is_sufficient=is_sufficient,
        is_multichannel_complete=is_multichannel_complete,
        platforms=platforms_coverage,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        details={
            "primary_platform": best_plat_name,
            "primary_coverage_percent": best_plat.snapshot_coverage_percent,
            "primary_distinct_days": best_plat.snapshot_distinct_days,
            "connected_platforms_count": len(creds_by_plat),
            "zero_data_platforms": zero_data_platforms,
        },
    )
