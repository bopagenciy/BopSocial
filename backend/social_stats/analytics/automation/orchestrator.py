"""
Central Orchestrator for BS-6A Production Intelligence Automation.
Coordinates deterministic pipeline execution, single-flight locking, safe dry-run preview,
fail-closed stage transitions, and provider-call budgets.
"""
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from .constants import (
    ApprovalStatus,
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    DEFAULT_MAX_RETRY_COUNT,
    DEFAULT_PROVIDER_CALL_BUDGET,
    PIPELINE_VERSION,
)
from .eligibility import evaluate_intelligence_automation_eligibility, EligibilityResult
from .events import log_automation_event, redact_secrets
from .identity import compute_approval_token, compute_execution_identity
from .locking import SingleFlightLock, ConcurrencyLockError

logger = logging.getLogger(__name__)


def preview_intelligence_automation(
    client_id: int,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    pipeline_version: str = PIPELINE_VERSION,
    trigger_type: str = AutomationTriggerType.MANUAL.value,
    force: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Pure read-only preview of automation eligibility, period calculation, freshness,
    artifact reuse decisions, planned stages, and provider budgets.
    STRICTLY GUARANTEES ZERO DATABASE WRITES.
    """
    eligibility = evaluate_intelligence_automation_eligibility(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        pipeline_version=pipeline_version,
        trigger_type=trigger_type,
        now=now,
        dry_run=True,
    )

    return {
        "dry_run": True,
        "client_id": client_id,
        "eligible": eligibility.eligible,
        "data_eligible": eligibility.data_eligible,
        "execution_authorized": eligibility.execution_authorized,
        "period_start": eligibility.period_start.isoformat(),
        "period_end": eligibility.period_end.isoformat(),
        "execution_identity": eligibility.execution_identity,
        "pipeline_version": eligibility.pipeline_version,
        "trigger_type": trigger_type,
        "blocking_reasons": eligibility.blocking_reasons,
        "warnings": eligibility.warnings,
        "freshness": eligibility.freshness,
        "target_period_coverage": eligibility.target_period_coverage,
        "existing_artifacts": eligibility.existing_artifacts,
        "planned_stages": eligibility.planned_stages,
        "skipped_stages": eligibility.skipped_stages,
        "reuse_decisions": eligibility.reuse_decisions,
        "provider_call_budget": eligibility.provider_call_budget,
        "requires_operator_approval": eligibility.requires_operator_approval,
        "config_enabled": eligibility.config_enabled,
    }


def execute_intelligence_automation(
    client_id: int,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    pipeline_version: str = PIPELINE_VERSION,
    trigger_type: str = AutomationTriggerType.MANUAL.value,
    dry_run: bool = False,
    requested_by: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> IntelligenceAutomationRun:
    """
    Executes or simulates the intelligence automation pipeline for a single tenant and reporting period.
    Enforces:
    1. Single-flight concurrency locking
    2. Zero external provider calls in dry_run mode
    3. Fail-closed error handling and audit recording
    4. Exact provider call budget enforcement (MAX 1)
    """
    start_time = time.monotonic()
    current_time = now or timezone.now()

    # Pre-evaluate eligibility and period
    eligibility: EligibilityResult = evaluate_intelligence_automation_eligibility(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        pipeline_version=pipeline_version,
        trigger_type=trigger_type,
        now=current_time,
        dry_run=dry_run,
    )

    client = Client.objects.filter(id=client_id).first()
    if not client:
        raise ValueError(f"Active Client #{client_id} does not exist.")

    # Concurrency Lock
    lock = SingleFlightLock(eligibility.execution_identity)
    if not lock.acquire():
        error_msg = f"Single-flight lock acquisition rejected for identity: {eligibility.execution_identity}"
        log_automation_event(
            event_name="automation.run.blocked",
            client_id=client_id,
            stage=AutomationStage.ELIGIBILITY.value,
            trigger_type=trigger_type,
            dry_run=dry_run,
            status=AutomationStatus.BLOCKED.value,
            error_code="CONCURRENCY_LOCK_ACTIVE",
            error_message=error_msg,
        )
        raise ConcurrencyLockError(error_msg)

    try:
        # Create persistent AutomationRun audit record
        agency_val = str(client.bop_organization_id) if getattr(client, "bop_organization_id", None) else None
        
        # Determine attempt number for this execution identity
        prior_runs_count = IntelligenceAutomationRun.objects.filter(
            execution_identity=eligibility.execution_identity
        ).count()
        attempt_num = prior_runs_count + 1

        run = IntelligenceAutomationRun.objects.create(
            client=client,
            agency_id=agency_val,
            period_start=eligibility.period_start,
            period_end=eligibility.period_end,
            pipeline_version=pipeline_version,
            execution_identity=eligibility.execution_identity,
            trigger_type=trigger_type,
            status=AutomationStatus.ELIGIBILITY_CHECK.value,
            current_stage=AutomationStage.ELIGIBILITY.value,
            started_at=current_time,
            requested_by=requested_by if (requested_by and getattr(requested_by, "is_authenticated", False)) else None,
            dry_run=dry_run,
            provider_call_count=0,
            retry_count=0,
            fallback_count=0,
            metadata={
                "attempt_number": attempt_num,
                "block_state_hash": eligibility.block_state_hash,
                "freshness": eligibility.freshness,
                "target_period_coverage": eligibility.target_period_coverage,
                "existing_artifacts": eligibility.existing_artifacts,
                "planned_stages": eligibility.planned_stages,
                "skipped_stages": eligibility.skipped_stages,
                "reuse_decisions": eligibility.reuse_decisions,
            },
        )

        log_automation_event(
            event_name="automation.run.created",
            run_id=run.id,
            client_id=client_id,
            period_start=eligibility.period_start.isoformat(),
            period_end=eligibility.period_end.isoformat(),
            stage=AutomationStage.ELIGIBILITY.value,
            trigger_type=trigger_type,
            dry_run=dry_run,
            status=run.status,
        )

        # Check Eligibility Gate: hard blockers (data missing/stale, client inactive, creds disconnected)
        hard_blocking_reasons = [
            r for r in eligibility.blocking_reasons
            if not r.startswith("OPERATOR_APPROVAL_REQUIRED")
        ]
        if hard_blocking_reasons:
            run.status = AutomationStatus.BLOCKED.value
            run.current_stage = AutomationStage.ELIGIBILITY.value
            run.finished_at = timezone.now()
            first_blocker = hard_blocking_reasons[0]
            code = first_blocker.split(":")[0].strip() if ":" in first_blocker else first_blocker.strip()
            run.error_code = code[:100]
            run.error_message_safe = redact_secrets("; ".join(eligibility.blocking_reasons))
            run.save(update_fields=["status", "current_stage", "finished_at", "error_code", "error_message_safe", "updated_at"])

            log_automation_event(
                event_name="automation.eligibility.blocked",
                run_id=run.id,
                client_id=client_id,
                stage=AutomationStage.ELIGIBILITY.value,
                trigger_type=trigger_type,
                dry_run=dry_run,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Transition to RUNNING
        run.status = AutomationStatus.RUNNING.value
        run.save(update_fields=["status", "updated_at"])

        # Stage: REPORT_CHECK
        run.current_stage = AutomationStage.REPORT_CHECK.value
        matching_report = ExecutiveReport.objects.filter(
            client_id=client_id,
            period_start=eligibility.period_start,
            period_end=eligibility.period_end,
            status="GENERATED",
        ).order_by("-id").first()
        if matching_report:
            run.report = matching_report
            run.save(update_fields=["report", "current_stage", "updated_at"])

        # Stage: NARRATIVE_CHECK
        run.current_stage = AutomationStage.NARRATIVE_CHECK.value
        matching_narrative = None
        if run.report:
            matching_narrative = ExecutiveNarrative.objects.filter(
                executive_report=run.report,
                status="VALIDATED",
            ).order_by("-id").first()
        elif client_id:
            matching_narrative = ExecutiveNarrative.objects.filter(
                executive_report__client_id=client_id,
                executive_report__period_start=eligibility.period_start,
                executive_report__period_end=eligibility.period_end,
                status="VALIDATED",
            ).order_by("-id").first()

        if matching_narrative:
            # REUSE existing validated narrative!
            run.narrative = matching_narrative
            run.save(update_fields=["narrative", "current_stage", "updated_at"])
        else:
            config = IntelligenceAutomationConfig.objects.filter(client_id=client_id).first()
            gen_narrative = config.generate_narrative if config else False
            req_approval = config.require_operator_approval if config else True

            if gen_narrative and req_approval and not dry_run:
                # PAUSE at NARRATIVE_CHECK awaiting operator approval!
                token = compute_approval_token(
                    run_id=run.id,
                    execution_identity=run.execution_identity,
                    pipeline_version=run.pipeline_version,
                    period_start=run.period_start,
                    period_end=run.period_end,
                    report_id=run.report_id,
                )
                now_ts = timezone.now()
                run.status = AutomationStatus.AWAITING_APPROVAL.value
                run.current_stage = AutomationStage.NARRATIVE_CHECK.value
                run.approval_status = ApprovalStatus.PENDING.value
                run.approval_requested_at = now_ts
                run.approval_token = token
                run.provider_call_count = 0
                run.save(update_fields=[
                    "status",
                    "current_stage",
                    "approval_status",
                    "approval_requested_at",
                    "approval_token",
                    "provider_call_count",
                    "updated_at",
                ])

                log_automation_event(
                    event_name="automation.approval.requested",
                    run_id=run.id,
                    client_id=client_id,
                    stage=AutomationStage.NARRATIVE_CHECK.value,
                    trigger_type=trigger_type,
                    dry_run=False,
                    status=run.status,
                    extra={"approval_token": token},
                )
                # Lock is released in finally block
                return run

        # In DRY-RUN mode or after reuse complete immediately
        run.status = AutomationStatus.COMPLETED.value
        run.current_stage = AutomationStage.COMPLETE.value
        run.finished_at = timezone.now()
        duration_ms = (time.monotonic() - start_time) * 1000
        run.save(update_fields=["status", "current_stage", "finished_at", "updated_at"])

        log_automation_event(
            event_name="automation.run.completed",
            run_id=run.id,
            client_id=client_id,
            stage=AutomationStage.COMPLETE.value,
            trigger_type=trigger_type,
            dry_run=dry_run,
            status=run.status,
            report_id=run.report_id,
            narrative_id=run.narrative_id,
            duration_ms=duration_ms,
        )
        return run

    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000
        safe_msg = redact_secrets(str(exc))
        logger.exception("Automation execution failed for client %s: %s", client_id, safe_msg)

        if "run" in locals() and run.id:
            run.status = AutomationStatus.FAILED.value
            run.error_code = type(exc).__name__
            run.error_message_safe = safe_msg[:500]
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_code", "error_message_safe", "finished_at", "updated_at"])

            log_automation_event(
                event_name="automation.stage.failed",
                run_id=run.id,
                client_id=client_id,
                stage=run.current_stage,
                trigger_type=trigger_type,
                dry_run=dry_run,
                status=run.status,
                duration_ms=duration_ms,
                error_code=run.error_code,
                error_message=safe_msg,
            )
        raise
    finally:
        lock.release()
