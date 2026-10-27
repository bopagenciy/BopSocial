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
from .period import calculate_reporting_period, get_tenant_local_datetime

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
    Future Periodic Discovery Scanner.
    Finds explicitly enabled tenant configs, computes due state in tenant timezone,
    verifies single-flight lock, and enqueues runs without global fan-out.

    REMAINS STRICTLY UNSCHEDULED IN BS-6A.
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

        # Check tenant local time
        local_dt = get_tenant_local_datetime(now, tz_name=config.timezone)
        local_date = local_dt.date()

        # Is tenant due on reporting day and hour?
        # For MONTHLY: e.g. day 1 at 06:00
        if config.reporting_frequency == "MONTHLY":
            is_due_day = (local_date.day == config.reporting_day)
            is_due_hour = (local_dt.hour == config.reporting_hour)
        elif config.reporting_frequency == "WEEKLY":
            # weekday: 0=Mon..6=Sun
            is_due_day = (local_date.weekday() == config.reporting_day)
            is_due_hour = (local_dt.hour == config.reporting_hour)
        else:
            is_due_day = False
            is_due_hour = False

        if not (is_due_day and is_due_hour):
            skipped_tenants.append({
                "client_id": client.id,
                "reason": f"NOT_DUE (day={local_date.day}/{config.reporting_day}, hour={local_dt.hour}/{config.reporting_hour})",
            })
            continue

        p_start, p_end = calculate_reporting_period(
            tz_name=config.timezone,
            frequency=config.reporting_frequency,
            reference_datetime=now,
            lookback_days=config.lookback_days,
            period_type="CALENDAR_MONTH",
        )

        # Check if already executed or active
        existing_run = IntelligenceAutomationRun.objects.filter(
            client=client,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            status__in=["COMPLETED", "RUNNING", "PENDING", "ELIGIBILITY_CHECK"],
        ).exists()

        if existing_run:
            skipped_tenants.append({
                "client_id": client.id,
                "reason": "RUN_ALREADY_EXISTS_OR_ACTIVE",
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
