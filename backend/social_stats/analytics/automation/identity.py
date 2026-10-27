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
