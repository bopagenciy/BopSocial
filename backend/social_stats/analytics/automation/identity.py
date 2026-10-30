"""
Execution Identity derivation for BS-6A Intelligence Automation.
Guarantees deterministic identity per tenant, period, and pipeline version.
"""
import hashlib
from datetime import date
from typing import Optional, Union

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

