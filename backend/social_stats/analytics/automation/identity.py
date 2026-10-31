"""
Execution Identity derivation for BS-6A Intelligence Automation.
Guarantees deterministic identity per tenant, period, and pipeline version.
"""
import hashlib
from datetime import date
from typing import Any, Optional, Tuple, Union

from .constants import PIPELINE_VERSION


def compute_execution_identity(
    client_id: int,
    period_start: Union[date, str],
    period_end: Union[date, str],
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    """
    Computes a deterministic SHA-256 execution identity string.
    Format: sha256("{client_id}:{period_start}:{period_end}:{pipeline_version}")
    """
    p_start_str = period_start.isoformat() if isinstance(period_start, date) else str(period_start)
    p_end_str = period_end.isoformat() if isinstance(period_end, date) else str(period_end)

    raw_identity = f"{client_id}:{p_start_str}:{p_end_str}:{pipeline_version}"
    return hashlib.sha256(raw_identity.encode("utf-8")).hexdigest()


def compute_block_state_hash(
    blocking_reasons: list,
    freshness_code: str = "",
    requires_approval: bool = True,
    config_enabled: bool = False,
    coverage_code: str = "",
    coverage_summary: str = "",
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of the tenant's material blocking state.
    Used to prevent repeated row storms when an invariant blocked condition persists,
    while permitting immediate reactivation when any blocker (freshness, coverage, approval, config) changes.
    """
    sorted_reasons = sorted(str(r) for r in blocking_reasons)
    payload = "|".join([
        ",".join(sorted_reasons),
        str(freshness_code),
        str(requires_approval),
        str(config_enabled),
        str(coverage_code),
        str(coverage_summary),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_approval_token(
    run_id: int,
    execution_identity: str,
    pipeline_version: str = PIPELINE_VERSION,
    period_start: Union[date, str] = "",
    period_end: Union[date, str] = "",
    report_id: Optional[int] = None,
) -> str:
    """
    Computes a deterministic SHA-256 token binding operator approval to this exact
    run, execution identity, pipeline version, reporting period, and report artifact.
    Prevents approval reuse across materially altered execution identities.
    """
    p_start_str = period_start.isoformat() if isinstance(period_start, date) else str(period_start)
    p_end_str = period_end.isoformat() if isinstance(period_end, date) else str(period_end)
    raw = f"{run_id}:{execution_identity}:{pipeline_version}:{p_start_str}:{p_end_str}:{report_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def get_deterministic_report_source_hash(
    client_id: int,
    period_start: date,
    period_end: date,
    platform: Optional[str] = None,
    language: str = "es",
) -> str:
    """
    Computes the canonical deterministic SHA-256 source hash for an executive report
    given current database inputs strictly contained in [period_start, period_end].
    Zero database mutations.
    """
    from django.db.models import Q
    from social_stats.models import SocialMetricRollup, BusinessSignal
    from social_stats.analytics.reporting.builder import compute_source_hash, TEMPLATE_VERSION
    from social_stats.analytics.multichannel.benchmarks import build_multichannel_benchmark

    # 1. Rollup count in period
    rollups_qs = SocialMetricRollup.objects.filter(
        client_id=client_id,
        period_start__gte=period_start,
        period_start__lte=period_end,
    )
    if platform:
        rollups_qs = rollups_qs.filter(platform=platform)
    source_rollup_count = rollups_qs.count()

    # 2. Persisted period-contained business signals
    signals_qs = BusinessSignal.objects.filter(
        client_id=client_id,
        period_start__gte=period_start,
        period_end__lte=period_end,
    )
    if platform:
        signals_qs = signals_qs.filter(Q(platform=platform) | Q(platform__contains=platform))
    persisted_signals = list(signals_qs.order_by("-period_end", "id"))
    signal_identities = [s.signal_identity for s in persisted_signals]

    # 3. Multichannel benchmark hash (if applicable)
    benchmark_hash = None
    if not platform or platform in ("facebook", "instagram"):
        try:
            bm = build_multichannel_benchmark(
                client_id=client_id,
                start_date=period_start,
                end_date=period_end,
                persist=False,
            )
            benchmark_hash = bm.benchmark_hash if bm else None
        except Exception:
            benchmark_hash = None

    return compute_source_hash(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        platform=platform,
        language=language,
        template_version=TEMPLATE_VERSION,
        rollup_count=source_rollup_count,
        signal_identities=signal_identities,
        benchmark_hash=benchmark_hash,
    )


def verify_executive_report_reuse(
    report: Optional[Any],
    client_id: int,
    period_start: date,
    period_end: date,
) -> Tuple[bool, str, Optional[str]]:
    """
    Verifies whether an existing ExecutiveReport matches the current deterministic
    source identity for the specified tenant and target period.
    Returns:
        (is_reusable: bool, reason: str, expected_source_hash: Optional[str])
    """
    if not report:
        return False, "NO_MATCHING_REPORT", None

    status = getattr(report, "status", None)
    if status != "GENERATED":
        return False, f"REPORT_STATUS_NOT_GENERATED ({status})", None

    rep_client_id = getattr(report, "client_id", None)
    if rep_client_id != client_id:
        return False, f"CLIENT_MISMATCH: report client={rep_client_id} != target={client_id}", None

    rep_p_start = getattr(report, "period_start", None)
    rep_p_end = getattr(report, "period_end", None)
    if rep_p_start != period_start or rep_p_end != period_end:
        return False, f"PERIOD_MISMATCH: report ({rep_p_start}..{rep_p_end}) != target ({period_start}..{period_end})", None

    expected_source_hash = get_deterministic_report_source_hash(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        platform=getattr(report, "platform_filter", None),
        language=getattr(report, "language", "es") or "es",
    )
    persisted_source_hash = getattr(report, "source_hash", "") or ""
    if not persisted_source_hash:
        return False, "PERSISTED_SOURCE_HASH_MISSING", expected_source_hash

    if persisted_source_hash != expected_source_hash:
        return False, f"SOURCE_HASH_MISMATCH: persisted={persisted_source_hash[:16]}... != current={expected_source_hash[:16]}...", expected_source_hash

    return True, "REUSABLE", expected_source_hash


def verify_executive_narrative_reuse(
    narrative: Optional[Any],
    report: Optional[Any],
    client_id: int,
    period_start: date,
    period_end: date,
) -> Tuple[bool, str, Optional[str]]:
    """
    Verifies whether an existing ExecutiveNarrative is valid and deterministically
    aligned with the linked report and current context identity.
    Returns:
        (is_reusable: bool, reason: str, expected_context_hash: Optional[str])
    """
    if not narrative:
        return False, "NO_MATCHING_NARRATIVE", None

    status = getattr(narrative, "status", None)
    if status != "VALIDATED":
        return False, f"NARRATIVE_STATUS_NOT_VALIDATED ({status})", None

    narr_client_id = getattr(narrative, "client_id", None)
    if narr_client_id != client_id:
        return False, f"CLIENT_MISMATCH: narrative client={narr_client_id} != target={client_id}", None

    if not report:
        return False, "NO_LINKED_REPORT", None

    rep_p_start = getattr(report, "period_start", None)
    rep_p_end = getattr(report, "period_end", None)
    if rep_p_start != period_start or rep_p_end != period_end:
        return False, f"REPORT_PERIOD_MISMATCH: report ({rep_p_start}..{rep_p_end}) != target ({period_start}..{period_end})", None

    # Check report source hash alignment
    narr_src_hash = getattr(narrative, "source_hash", "") or ""
    rep_src_hash = getattr(report, "source_hash", "") or ""
    if narr_src_hash != rep_src_hash:
        return False, f"NARRATIVE_REPORT_SOURCE_HASH_MISMATCH: narrative={narr_src_hash[:16]}... != report={rep_src_hash[:16]}...", None

    # Compute expected context hash from current report data
    from social_stats.analytics.narrative.context import build_grounded_narrative_context, compute_context_hash
    try:
        current_context = build_grounded_narrative_context(report)
        expected_context_hash = compute_context_hash(current_context)
    except Exception as exc:
        return False, f"CONTEXT_BUILD_FAILURE: {exc}", None

    persisted_context_hash = getattr(narrative, "context_hash", "") or ""
    if not persisted_context_hash:
        return False, "PERSISTED_CONTEXT_HASH_MISSING", expected_context_hash

    if persisted_context_hash != expected_context_hash:
        return False, f"CONTEXT_HASH_MISMATCH: persisted={persisted_context_hash[:16]}... != current={expected_context_hash[:16]}...", expected_context_hash

    return True, "REUSABLE", expected_context_hash

