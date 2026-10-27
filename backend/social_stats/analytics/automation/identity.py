"""
Execution Identity derivation for BS-6A Intelligence Automation.
Guarantees deterministic identity per tenant, period, and pipeline version.
"""
import hashlib
from datetime import date
from typing import Union

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
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of the tenant's material blocking state.
    Used to prevent repeated row storms when an invariant blocked condition persists,
    while permitting immediate reactivation when any blocker (freshness, approval, config) changes.
    """
    sorted_reasons = sorted(str(r) for r in blocking_reasons)
    payload = "|".join([
        ",".join(sorted_reasons),
        str(freshness_code),
        str(requires_approval),
        str(config_enabled),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

