"""
Core Comparison Service and Pure Functions for Multichannel Analytics.
Phase BS-5A: Multichannel Metric Compatibility & Comparison Model.

Implements:
- Pure calculation functions (absolute delta, safe relative delta, winner determination).
- ComparisonResult deterministic result dataclass with bilingual reason labels and machine evidence.
- compare_metric_across_platforms core service operating read-only on normalized analytics data.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db.models import Avg, Sum
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
)
from ..capabilities import get_provider_capability, SupportLevel
from ..registry import CANONICAL_METRICS, AggregationBehavior
from .labels import get_reason_labels, get_status_labels, get_winner_labels
from .rules import MetricComparisonRule, get_metric_comparison_rule
from .taxonomies import (
    ComparisonCompatibility,
    ComparisonDirection,
    ComparisonReasonCode,
    ComparisonStatus,
    ComparisonWinner,
    NormalizationType,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# PURE FUNCTIONS
# ==============================================================================

def calculate_absolute_delta(
    val_a: Optional[Decimal],
    val_b: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Computes absolute delta between platform A and platform B:
        delta_absolute = val_a - val_b

    Sign convention:
    - Positive: Platform A is greater than Platform B.
    - Negative: Platform B is greater than Platform A.
    - Returns None if either value is None.
    """
    if val_a is None or val_b is None:
        return None
    return (val_a - val_b).quantize(Decimal("0.0001"))


def calculate_relative_delta(
    val_a: Optional[Decimal],
    val_b: Optional[Decimal],
) -> Tuple[Optional[Decimal], Optional[ComparisonReasonCode]]:
    """
    Computes percentage change of Platform A relative to baseline Platform B:
        delta_relative = ((val_a - val_b) / abs(val_b)) * 100

    Safety rules:
    - If val_b == 0: returns (None, ZERO_BASELINE) to prevent division by zero.
    - If either value is None: returns (None, None).
    - Returns (Decimal percentage, None) upon valid calculation.
    """
    if val_a is None or val_b is None:
        return None, None

    if val_b == Decimal("0"):
        return None, ComparisonReasonCode.ZERO_BASELINE

    try:
        rel = ((val_a - val_b) / abs(val_b)) * Decimal("100")
        return rel.quantize(Decimal("0.0001")), None
    except (ZeroDivisionError, InvalidOperation):
        return None, ComparisonReasonCode.ZERO_BASELINE


def determine_winner(
    val_a: Optional[Decimal],
    val_b: Optional[Decimal],
    direction: ComparisonDirection,
    rankable: bool,
) -> ComparisonWinner:
    """
    Determines performance winner strictly according to metric direction and rankability.

    Rules:
    - If metric is NOT rankable or direction is NEUTRAL / NOT_APPLICABLE: returns NO_WINNER.
      (e.g. FOLLOWERS_TOTAL audience volume does not imply performance superiority).
    - If either value is None: returns UNAVAILABLE.
    - If val_a == val_b: returns TIE.
    - If HIGHER_IS_BETTER: PLATFORM_A if val_a > val_b else PLATFORM_B.
    - If LOWER_IS_BETTER: PLATFORM_A if val_a < val_b else PLATFORM_B.
    """
    if not rankable or direction in (ComparisonDirection.NEUTRAL, ComparisonDirection.NOT_APPLICABLE):
        return ComparisonWinner.NO_WINNER

    if val_a is None or val_b is None:
        return ComparisonWinner.UNAVAILABLE

    if val_a == val_b:
        return ComparisonWinner.TIE

    if direction == ComparisonDirection.HIGHER_IS_BETTER:
        return ComparisonWinner.PLATFORM_A if val_a > val_b else ComparisonWinner.PLATFORM_B

    if direction == ComparisonDirection.LOWER_IS_BETTER:
        return ComparisonWinner.PLATFORM_A if val_a < val_b else ComparisonWinner.PLATFORM_B

    return ComparisonWinner.NO_WINNER


# ==============================================================================
# COMPARISON RESULT MODEL
# ==============================================================================

@dataclass(frozen=True)
class ComparisonResult:
    """
    Deterministic result model for multichannel cross-platform comparisons.
    Provides machine-readable evidence, typed enums, and bilingual reason labels.
    """
    metric: str
    platform_a: str
    platform_b: str
    status: ComparisonStatus
    compatibility: ComparisonCompatibility
    direction: ComparisonDirection
    normalization: NormalizationType
    rankable: bool
    value_a: Optional[Decimal]
    value_b: Optional[Decimal]
    normalized_value_a: Optional[Decimal]
    normalized_value_b: Optional[Decimal]
    delta_absolute: Optional[Decimal]
    delta_relative: Optional[Decimal]
    winner: ComparisonWinner
    period_start: Optional[date]
    period_end: Optional[date]
    sample_a: int
    sample_b: int
    reason_code: ComparisonReasonCode
    reason_labels: Dict[str, str] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes dataclass to JSON-serializable dictionary."""
        return {
            "metric": self.metric,
            "platform_a": self.platform_a,
            "platform_b": self.platform_b,
            "status": self.status.value,
            "status_labels": get_status_labels(self.status),
            "compatibility": self.compatibility.value,
            "direction": self.direction.value,
            "normalization": self.normalization.value,
            "rankable": self.rankable,
            "value_a": float(self.value_a) if self.value_a is not None else None,
            "value_b": float(self.value_b) if self.value_b is not None else None,
            "normalized_value_a": float(self.normalized_value_a) if self.normalized_value_a is not None else None,
            "normalized_value_b": float(self.normalized_value_b) if self.normalized_value_b is not None else None,
            "delta_absolute": float(self.delta_absolute) if self.delta_absolute is not None else None,
            "delta_relative": float(self.delta_relative) if self.delta_relative is not None else None,
            "winner": self.winner.value,
            "winner_labels": get_winner_labels(self.winner),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "sample_a": self.sample_a,
            "sample_b": self.sample_b,
            "reason_code": self.reason_code.value,
            "reason_labels": self.reason_labels or get_reason_labels(self.reason_code),
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


# ==============================================================================
# CORE COMPARISON SERVICE
# ==============================================================================

def _to_decimal(val: Optional[Union[Decimal, int, float, str]]) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None


def compare_metric_across_platforms(
    *,
    client: Optional[Client] = None,
    client_id: Optional[int] = None,
    metric: str,
    platform_a: str,
    platform_b: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: str = "day",
    # Direct synthetic overrides for unit testing / pure execution:
    value_a: Optional[Union[Decimal, int, float, str]] = None,
    value_b: Optional[Union[Decimal, int, float, str]] = None,
    is_available_a: Optional[bool] = None,
    is_available_b: Optional[bool] = None,
    sample_a: Optional[int] = None,
    sample_b: Optional[int] = None,
    period_start_a: Optional[date] = None,
    period_end_a: Optional[date] = None,
    period_start_b: Optional[date] = None,
    period_end_b: Optional[date] = None,
    allow_reach_daily_sum: bool = False,
) -> ComparisonResult:
    """
    Authoritative, deterministic cross-platform metric comparison service.
    Operates read-only across normalized Bop Social analytics telemetry.
    No provider calls. No database writes.
    """
    m_clean = (metric or "").strip().upper()
    plat_a = (platform_a or "").strip().lower()
    plat_b = (platform_b or "").strip().lower()

    # 1. Metric registry check (Fail closed if unknown metric)
    is_canon = m_clean in CANONICAL_METRICS or m_clean == "AVERAGE_DAILY_REACH"
    if not is_canon:
        rc = ComparisonReasonCode.UNSUPPORTED_METRIC
        return ComparisonResult(
            metric=m_clean or metric,
            platform_a=plat_a or platform_a,
            platform_b=plat_b or platform_b,
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=ComparisonCompatibility.UNAVAILABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=start_date,
            period_end=end_date,
            sample_a=0,
            sample_b=0,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={"error": f"Metric '{m_clean}' is unknown to canonical metric registry."},
        )

    # 2. Period alignment check
    if period_start_a and period_start_b and period_start_a != period_start_b:
        rc = ComparisonReasonCode.PERIOD_MISMATCH
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.INVALID,
            compatibility=ComparisonCompatibility.UNAVAILABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=period_start_a,
            period_end=period_end_a,
            sample_a=0,
            sample_b=0,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={"error": f"Period start mismatch: {period_start_a} != {period_start_b}"},
        )
    if period_end_a and period_end_b and period_end_a != period_end_b:
        rc = ComparisonReasonCode.PERIOD_MISMATCH
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.INVALID,
            compatibility=ComparisonCompatibility.UNAVAILABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=period_start_a,
            period_end=period_end_a,
            sample_a=0,
            sample_b=0,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={"error": f"Period end mismatch: {period_end_a} != {period_end_b}"},
        )
    if start_date and end_date and start_date > end_date:
        rc = ComparisonReasonCode.PERIOD_MISMATCH
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.INVALID,
            compatibility=ComparisonCompatibility.UNAVAILABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=start_date,
            period_end=end_date,
            sample_a=0,
            sample_b=0,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={"error": f"start_date ({start_date}) is after end_date ({end_date})"},
        )

    # 3. Rule lookup (Platform pair check)
    rule = get_metric_comparison_rule(m_clean, plat_a, plat_b)
    if rule is None:
        rc = ComparisonReasonCode.UNSUPPORTED_PLATFORM
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=ComparisonCompatibility.UNAVAILABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=start_date,
            period_end=end_date,
            sample_a=0,
            sample_b=0,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={"error": f"Platform pair '{plat_a}' <-> '{plat_b}' is unsupported or unregistered."},
        )

    # 4. Resolve client if requested
    resolved_client = client
    if resolved_client is None and client_id is not None:
        resolved_client = Client.objects.filter(id=client_id, is_active=True).first()

    # 5. Check synthetic value inputs vs database retrieval
    dec_val_a = _to_decimal(value_a)
    dec_val_b = _to_decimal(value_b)
    has_synthetic_inputs = (dec_val_a is not None or is_available_a is not None) and (dec_val_b is not None or is_available_b is not None)

    # If non-comparable rule: fail closed immediately for ranking
    if rule.compatibility == ComparisonCompatibility.NON_COMPARABLE:
        rc = ComparisonReasonCode.METRIC_NOT_EQUIVALENT
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=rule.compatibility,
            direction=rule.direction,
            normalization=rule.normalization,
            rankable=False,
            value_a=dec_val_a,
            value_b=dec_val_b,
            normalized_value_a=dec_val_a,
            normalized_value_b=dec_val_b,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.NO_WINNER,
            period_start=start_date,
            period_end=end_date,
            sample_a=sample_a or (1 if dec_val_a is not None else 0),
            sample_b=sample_b or (1 if dec_val_b is not None else 0),
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={
                "rule_notes": rule.notes,
                "compatibility": rule.compatibility.value,
            },
        )

    # 6. Database retrieval when synthetic values are not provided
    avail_a = is_available_a if is_available_a is not None else (dec_val_a is not None)
    avail_b = is_available_b if is_available_b is not None else (dec_val_b is not None)
    cnt_a = sample_a or (1 if dec_val_a is not None else 0)
    cnt_b = sample_b or (1 if dec_val_b is not None else 0)

    if not has_synthetic_inputs:
        if resolved_client is None:
            rc = ComparisonReasonCode.TENANT_MISMATCH
            return ComparisonResult(
                metric=m_clean,
                platform_a=plat_a,
                platform_b=plat_b,
                status=ComparisonStatus.UNAVAILABLE,
                compatibility=rule.compatibility,
                direction=rule.direction,
                normalization=rule.normalization,
                rankable=rule.rankable,
                value_a=None,
                value_b=None,
                normalized_value_a=None,
                normalized_value_b=None,
                delta_absolute=None,
                delta_relative=None,
                winner=ComparisonWinner.UNAVAILABLE,
                period_start=start_date,
                period_end=end_date,
                sample_a=0,
                sample_b=0,
                reason_code=rc,
                reason_labels=get_reason_labels(rc),
                evidence={"error": "Client not specified or client ID invalid."},
            )

        # Metric-level provider capability gating
        cred_a = PlatformCredential.objects.defer("access_token", "refresh_token").filter(
            client=resolved_client, platform=plat_a, is_active=True
        ).first()
        cred_b = PlatformCredential.objects.defer("access_token", "refresh_token").filter(
            client=resolved_client, platform=plat_b, is_active=True
        ).first()

        cap_a = get_provider_capability(plat_a, cred_a)
        cap_b = get_provider_capability(plat_b, cred_b)

        # Instagram partial mode checks
        ig_supported_under_partial = {"FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"}
        for p_name, cap in [(plat_a, cap_a), (plat_b, cap_b)]:
            if p_name == "instagram" and cap.overall_support == SupportLevel.PARTIAL:
                if m_clean == "ENGAGEMENT_TOTAL":
                    rc = ComparisonReasonCode.COMPONENT_UNAVAILABLE
                    return ComparisonResult(
                        metric=m_clean,
                        platform_a=plat_a,
                        platform_b=plat_b,
                        status=ComparisonStatus.UNAVAILABLE,
                        compatibility=rule.compatibility,
                        direction=rule.direction,
                        normalization=rule.normalization,
                        rankable=rule.rankable,
                        value_a=None,
                        value_b=None,
                        normalized_value_a=None,
                        normalized_value_b=None,
                        delta_absolute=None,
                        delta_relative=None,
                        winner=ComparisonWinner.UNAVAILABLE,
                        period_start=start_date,
                        period_end=end_date,
                        sample_a=0,
                        sample_b=0,
                        reason_code=rc,
                        reason_labels=get_reason_labels(rc),
                        evidence={
                            "platform": p_name,
                            "capability": cap.overall_support.value,
                            "missing_component": "SHARES",
                            "rule_notes": rule.notes,
                        },
                    )
                elif m_clean not in ig_supported_under_partial:
                    rc = ComparisonReasonCode.PROVIDER_PARTIAL
                    return ComparisonResult(
                        metric=m_clean,
                        platform_a=plat_a,
                        platform_b=plat_b,
                        status=ComparisonStatus.UNAVAILABLE,
                        compatibility=rule.compatibility,
                        direction=rule.direction,
                        normalization=rule.normalization,
                        rankable=rule.rankable,
                        value_a=None,
                        value_b=None,
                        normalized_value_a=None,
                        normalized_value_b=None,
                        delta_absolute=None,
                        delta_relative=None,
                        winner=ComparisonWinner.UNAVAILABLE,
                        period_start=start_date,
                        period_end=end_date,
                        sample_a=0,
                        sample_b=0,
                        reason_code=rc,
                        reason_labels=get_reason_labels(rc),
                        evidence={
                            "platform": p_name,
                            "capability": cap.overall_support.value,
                            "unsupported_metric": m_clean,
                        },
                    )

        # REACH Safety: daily reach cannot be summed across multiple dates
        if m_clean == "REACH":
            if start_date and end_date and start_date != end_date and not allow_reach_daily_sum:
                # Check if a single period-level rollup exists covering the range
                period_match_rollups = SocialMetricRollup.objects.filter(
                    client=resolved_client,
                    platform__in=[plat_a, plat_b],
                    normalized_metric="REACH",
                    period__in=["month", "week", "custom"],
                    period_start=start_date,
                )
                if period_match_rollups.count() < 2:
                    rc = ComparisonReasonCode.NON_AGGREGATABLE_SUMMATION_REJECTED
                    return ComparisonResult(
                        metric=m_clean,
                        platform_a=plat_a,
                        platform_b=plat_b,
                        status=ComparisonStatus.UNAVAILABLE,
                        compatibility=rule.compatibility,
                        direction=rule.direction,
                        normalization=rule.normalization,
                        rankable=rule.rankable,
                        value_a=None,
                        value_b=None,
                        normalized_value_a=None,
                        normalized_value_b=None,
                        delta_absolute=None,
                        delta_relative=None,
                        winner=ComparisonWinner.UNAVAILABLE,
                        period_start=start_date,
                        period_end=end_date,
                        sample_a=0,
                        sample_b=0,
                        reason_code=rc,
                        reason_labels=get_reason_labels(rc),
                        evidence={
                            "error": "Unique REACH cannot be arithmetically summed across multiple daily dates.",
                            "rule_notes": rule.notes,
                        },
                    )

        # Extract values for Platform A and Platform B from DB
        def _fetch_platform_metric(plat: str) -> Tuple[Optional[Decimal], bool, int]:
            source_metric = "REACH" if m_clean == "AVERAGE_DAILY_REACH" else m_clean
            qs = SocialMetricRollup.objects.filter(
                client=resolved_client,
                platform=plat,
                normalized_metric=source_metric,
            )
            if start_date:
                qs = qs.filter(period_start__gte=start_date)
            if end_date:
                qs = qs.filter(period_start__lte=end_date)

            rollups = list(qs)
            if not rollups:
                # Check snapshots as fallback
                s_qs = SocialMetricSnapshot.objects.filter(
                    client=resolved_client,
                    platform=plat,
                    normalized_metric=source_metric,
                )
                if start_date:
                    s_qs = s_qs.filter(bucket_timestamp__date__gte=start_date)
                if end_date:
                    s_qs = s_qs.filter(bucket_timestamp__date__lte=end_date)
                snaps = list(s_qs)
                if not snaps:
                    return None, False, 0
                total_val = sum((s.metric_value for s in snaps), Decimal("0"))
                return total_val, True, len(snaps)

            defn = CANONICAL_METRICS.get(source_metric)
            beh = defn.aggregation_behavior if defn else AggregationBehavior.SUMMABLE

            if m_clean == "AVERAGE_DAILY_REACH":
                total = sum((r.metric_value for r in rollups), Decimal("0"))
                avg_val = total / Decimal(str(len(rollups)))
                return avg_val.quantize(Decimal("0.0001")), True, len(rollups)

            if beh == AggregationBehavior.LATEST_VALUE:
                latest_r = max(rollups, key=lambda x: x.period_start)
                return latest_r.metric_value, True, len(rollups)
            elif beh == AggregationBehavior.AVERAGE:
                total = sum((r.metric_value for r in rollups), Decimal("0"))
                avg_val = total / Decimal(str(len(rollups)))
                return avg_val.quantize(Decimal("0.0001")), True, len(rollups)
            else:
                total = sum((r.metric_value for r in rollups), Decimal("0"))
                return total, True, len(rollups)

        dec_val_a, avail_a, cnt_a = _fetch_platform_metric(plat_a)
        dec_val_b, avail_b, cnt_b = _fetch_platform_metric(plat_b)

    # 7. Evaluate availability and observed zero
    # Observed zero is valid data; unavailable is missing data.
    if not avail_a or not avail_b or dec_val_a is None or dec_val_b is None:
        rc = ComparisonReasonCode.SOURCE_UNAVAILABLE
        return ComparisonResult(
            metric=m_clean,
            platform_a=plat_a,
            platform_b=plat_b,
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=rule.compatibility,
            direction=rule.direction,
            normalization=rule.normalization,
            rankable=rule.rankable,
            value_a=dec_val_a if avail_a else None,
            value_b=dec_val_b if avail_b else None,
            normalized_value_a=dec_val_a if avail_a else None,
            normalized_value_b=dec_val_b if avail_b else None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=start_date or period_start_a,
            period_end=end_date or period_end_a,
            sample_a=cnt_a,
            sample_b=cnt_b,
            reason_code=rc,
            reason_labels=get_reason_labels(rc),
            evidence={
                "platform_a_available": avail_a,
                "platform_b_available": avail_b,
                "rule_notes": rule.notes,
            },
        )

    # 8. Compute absolute and relative deltas
    delta_abs = calculate_absolute_delta(dec_val_a, dec_val_b)
    delta_rel, zero_reason = calculate_relative_delta(dec_val_a, dec_val_b)

    # 9. Determine winner strictly adhering to direction and rankability
    winner = determine_winner(dec_val_a, dec_val_b, rule.direction, rule.rankable)

    # 10. Select appropriate reason code
    if zero_reason:
        reason_code = zero_reason
    elif not rule.rankable or rule.direction == ComparisonDirection.NEUTRAL:
        reason_code = ComparisonReasonCode.NON_RANKABLE_METRIC
    else:
        reason_code = rule.default_reason_code

    return ComparisonResult(
        metric=m_clean,
        platform_a=plat_a,
        platform_b=plat_b,
        status=ComparisonStatus.AVAILABLE,
        compatibility=rule.compatibility,
        direction=rule.direction,
        normalization=rule.normalization,
        rankable=rule.rankable,
        value_a=dec_val_a,
        value_b=dec_val_b,
        normalized_value_a=dec_val_a,
        normalized_value_b=dec_val_b,
        delta_absolute=delta_abs,
        delta_relative=delta_rel,
        winner=winner,
        period_start=start_date or period_start_a,
        period_end=end_date or period_end_a,
        sample_a=cnt_a,
        sample_b=cnt_b,
        reason_code=reason_code,
        reason_labels=get_reason_labels(reason_code),
        evidence={
            "platform_a_value": float(dec_val_a),
            "platform_b_value": float(dec_val_b),
            "delta_absolute": float(delta_abs) if delta_abs is not None else None,
            "delta_relative": float(delta_rel) if delta_rel is not None else None,
            "rule_direction": rule.direction.value,
            "rule_compatibility": rule.compatibility.value,
            "rule_normalization": rule.normalization.value,
            "rankable": rule.rankable,
            "rule_notes": rule.notes,
        },
    )
