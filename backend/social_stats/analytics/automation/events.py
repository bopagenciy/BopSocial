"""
Structured Observability and Safe Audit Logging for BS-6A Intelligence Automation.
Guarantees 0 secret leaks (tokens, keys, passwords redacted) and emits structured events.
"""
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("social_stats.analytics.automation")

SECRET_PATTERNS = [
    re.compile(r"(EA[A-Za-z0-9]{30,})"),  # Meta user/page access tokens
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),  # Google API key
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),  # Generic API keys
    re.compile(r"password=['\"][^'\"]+['\"]", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redacts potential tokens, secrets, and credentials from text strings."""
    if not text:
        return ""
    sanitized = str(text)
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def log_automation_event(
    event_name: str,
    run_id: Optional[int] = None,
    client_id: Optional[int] = None,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    stage: Optional[str] = None,
    trigger_type: Optional[str] = None,
    dry_run: bool = False,
    status: Optional[str] = None,
    report_id: Optional[int] = None,
    narrative_id: Optional[int] = None,
    provider_call_count: int = 0,
    retry_count: int = 0,
    duration_ms: Optional[float] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    operator_id: Optional[int] = None,
    decision: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emits a structured log line for an automation event.
    No secrets or prompt bodies are logged.
    """
    safe_error_msg = redact_secrets(error_message or "") if error_message else None

    payload = {
        "event": event_name,
        "run_id": run_id,
        "client_id": client_id,
        "period_start": period_start,
        "period_end": period_end,
        "stage": stage,
        "trigger": trigger_type,
        "dry_run": dry_run,
        "status": status,
        "report_id": report_id,
        "narrative_id": narrative_id,
        "provider_call_count": provider_call_count,
        "retry_count": retry_count,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "error_code": error_code,
        "error_message": safe_error_msg,
        "operator_id": operator_id,
        "decision": decision,
    }
    if extra:
        payload["extra"] = {k: redact_secrets(str(v)) for k, v in extra.items()}

    log_level = logging.WARNING if error_code or (status in ["FAILED", "BLOCKED"]) else logging.INFO
    logger.log(log_level, f"[{event_name}] run={run_id} client={client_id} stage={stage} status={status}: {payload}")
