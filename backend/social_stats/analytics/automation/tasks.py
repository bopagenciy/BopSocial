"""
Future-safe Celery Task Wrappers and Discovery Task for BS-6A Intelligence Automation.
REMAINS STRICTLY UNSCHEDULED AND DISABLED IN BS-6A.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from celery import shared_task
from django.utils import timezone

from social_stats.models import (
    Client,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from .constants import (
    AutomationTriggerType,
    DEFAULT_MAX_RETRY_COUNT,
    PIPELINE_VERSION,
)
from .eligibility import evaluate_intelligence_automation_eligibility
from .orchestrator import execute_intelligence_automation, preview_intelligence_automation
from .period import (
    calculate_next_due_datetime,
    calculate_reporting_period,
    get_tenant_local_datetime,
    is_tenant_due,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=DEFAULT_MAX_RETRY_COUNT)
def run_intelligence_automation_task(
    self,
    client_id: int,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    trigger_type: str = AutomationTriggerType.SCHEDULED.value,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Celery task wrapper delegating directly to orchestration service.
    Zero duplicated business logic.
    Max retries hard-limited to 0 (fail-closed).
    """
    p_start = date.fromisoformat(period_start) if period_start else None
    p_end = date.fromisoformat(period_end) if period_end else None

    if dry_run:
        return preview_intelligence_automation(
            client_id=client_id,
            period_start=p_start,
            period_end=p_end,
            trigger_type=trigger_type,
        )

    run = execute_intelligence_automation(
        client_id=client_id,
        period_start=p_start,
        period_end=p_end,
        trigger_type=trigger_type,
        dry_run=False,
    )

    return {
        "run_id": run.id,
        "client_id": run.client_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "execution_identity": run.execution_identity,
    }


@shared_task
def discover_and_enqueue_due_intelligence_automations(dry_run: bool = True) -> Dict[str, Any]:
    """
    Periodic Discovery Scanner.
    Finds explicitly enabled tenant configs, computes due state in tenant timezone,
    prevents duplicate enqueues for active, completed, or already-evaluated periods,
    and supports missed-tick recovery across arbitrary tenant timezones.

    DOES NOT DIRECTLY INVOKE ANY LLM OR THIRD-PARTY PROVIDER.
    """
    now = timezone.now()
    due_tenants: List[int] = []
    skipped_tenants: List[Dict[str, Any]] = []

    # Enumerate ONLY explicitly enabled configurations
    enabled_configs = IntelligenceAutomationConfig.objects.filter(enabled=True).select_related("client")

    for config in enabled_configs:
        client = config.client
        if not client.is_active:
            skipped_tenants.append({"client_id": client.id, "reason": "CLIENT_INACTIVE"})
            continue

        # Evaluate due state using timezone-aware scheduler engine (supports missed ticks)
        is_due, p_start, p_end, due_reason = is_tenant_due(config, reference_datetime=now)
        if not is_due:
            skipped_tenants.append({
                "client_id": client.id,
                "reason": due_reason,
            })
            continue

        # Check if an active or completed run exists
        active_or_complete = IntelligenceAutomationRun.objects.filter(
            client=client,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            status__in=[
                "COMPLETED",
                "RUNNING",
                "PENDING",
                "ELIGIBILITY_CHECK",
                "AWAITING_APPROVAL",
                "PROVIDER_EXECUTION_READY",
                "PROVIDER_EXECUTING",
            ],
        ).order_by("-id").first()

        if active_or_complete:
            skipped_tenants.append({
                "client_id": client.id,
                "reason": f"RUN_ALREADY_EXISTS_OR_ACTIVE (run #{active_or_complete.id}, status={active_or_complete.status})",
            })
            continue

        # Inspect latest terminal BLOCKED run (if any)
        latest_blocked = IntelligenceAutomationRun.objects.filter(
            client=client,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            status="BLOCKED",
        ).order_by("-id").first()

        if latest_blocked:
            # Check current material eligibility fingerprint
            current_eligibility = evaluate_intelligence_automation_eligibility(
                client_id=client.id,
                period_start=p_start,
                period_end=p_end,
                pipeline_version=PIPELINE_VERSION,
                trigger_type=AutomationTriggerType.SCHEDULED.value,
                now=now,
                dry_run=True,
            )

            # Extract stored block_state_hash from previous run's metadata, or derive it from stored audit fields
            stored_metadata = latest_blocked.metadata or {}
            stored_hash = stored_metadata.get("block_state_hash") or ""
            if not stored_hash and latest_blocked.error_code:
                # Safe legacy fallback: derive hash dynamically from stored immutable fields
                from .identity import compute_block_state_hash
                stored_freshness = (stored_metadata.get("freshness") or {}).get("code", "")
                stored_hash = compute_block_state_hash(
                    blocking_reasons=[latest_blocked.error_code],
                    freshness_code=stored_freshness,
                    requires_approval=True,
                    config_enabled=config.enabled,
                )

            # If material block state is UNCHANGED and still not eligible/authorized:
            if current_eligibility.block_state_hash and (
                current_eligibility.block_state_hash == stored_hash
                or (not stored_hash and latest_blocked.error_code in current_eligibility.blocking_reasons)
            ):
                skipped_tenants.append({
                    "client_id": client.id,
                    "reason": f"BLOCKED_STATE_UNCHANGED (run #{latest_blocked.id}, hash={stored_hash or 'legacy'})",
                })
                continue

        due_tenants.append(client.id)

        if not dry_run:
            run_intelligence_automation_task.delay(
                client_id=client.id,
                period_start=p_start.isoformat(),
                period_end=p_end.isoformat(),
                trigger_type=AutomationTriggerType.SCHEDULED.value,
                dry_run=False,
            )

    logger.info(
        "discover_and_enqueue_due_intelligence_automations: %d due, %d skipped (dry_run=%s)",
        len(due_tenants),
        len(skipped_tenants),
        dry_run,
    )

    return {
        "timestamp": now.isoformat(),
        "dry_run": dry_run,
        "due_count": len(due_tenants),
        "due_client_ids": due_tenants,
        "skipped_summary": skipped_tenants,
    }
