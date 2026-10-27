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

        # Check if already executed, active, or evaluated for this target period
        # Excludes COMPLETED, RUNNING, PENDING, ELIGIBILITY_CHECK, and already-BLOCKED runs
        # (preventing row storms on repeated scans of an invariant blocked tenant)
        existing_run = IntelligenceAutomationRun.objects.filter(
            client=client,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            status__in=["COMPLETED", "RUNNING", "PENDING", "ELIGIBILITY_CHECK", "BLOCKED"],
        ).order_by("-id").first()

        if existing_run:
            skipped_tenants.append({
                "client_id": client.id,
                "reason": f"RUN_ALREADY_EXISTS_OR_ACTIVE (run #{existing_run.id}, status={existing_run.status})",
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
