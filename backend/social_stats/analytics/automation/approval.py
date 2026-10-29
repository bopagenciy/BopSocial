"""
Run-Level Approval Workflow and Controlled Resume Foundation for BS-6C.
Provides:
1. Operator approval / rejection service with atomic transitions
2. Advisory lock release and reacquisition contracts
3. Complete safety revalidation after human delay
4. Strict provider execution boundary (zero external LLM calls)
5. Structured audit logging and double-approval prevention
"""
import logging
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
)
from .constants import (
    ApprovalStatus,
    AutomationStage,
    AutomationStatus,
    FreshnessCode,
    PROVIDER_EXECUTION_READY,
)
from .events import log_automation_event, redact_secrets
from .freshness import evaluate_tenant_freshness
from .identity import compute_approval_token
from .locking import ConcurrencyLockError, SingleFlightLock

logger = logging.getLogger("social_stats.analytics.automation")


class ApprovalError(Exception):
    """Base error for approval workflow failures."""
    pass


class DoubleApprovalError(ApprovalError):
    """Raised when an approval decision has already been executed on a run."""
    pass


class StaleApprovalError(ApprovalError):
    """Raised when the execution context or identity changed after approval request."""
    pass


class AuthorizationError(ApprovalError):
    """Raised when the acting operator lacks permission for the tenant/run."""
    pass


def verify_operator_authorization(operator_user: Any, client_id: int) -> None:
    """
    Verifies that the operator user has permission to approve/reject automation runs for client_id.
    Staff and superusers are globally authorized. Regular users must own or be assigned to the client.
    """
    if not operator_user or not getattr(operator_user, "is_authenticated", False):
        raise AuthorizationError("Operator must be an authenticated user.")

    if getattr(operator_user, "is_superuser", False) or getattr(operator_user, "is_staff", False):
        return

    # Check client ownership or staff assignment
    client = Client.objects.filter(id=client_id, is_active=True).first()
    if not client:
        raise AuthorizationError(f"Client #{client_id} not found or inactive.")

    if getattr(client, "owner_user_id", None) == operator_user.id:
        return

    # User profile / agency check if applicable
    user_clients = getattr(operator_user, "assigned_clients", None)
    if user_clients and user_clients.filter(id=client_id).exists():
        return

    raise AuthorizationError(f"User #{operator_user.id} is not authorized to operate Client #{client_id}.")


def approve_intelligence_run(
    run_id: int,
    operator_user: Any,
    comment: str = "",
) -> IntelligenceAutomationRun:
    """
    Approves an automation run currently in AWAITING_APPROVAL status.
    Guarantees:
    - Atomic transaction with row locking (select_for_update)
    - Operator authorization check
    - Double approval protection
    - Approval token validation
    - Immutable audit record
    - Zero external provider calls
    """
    with transaction.atomic():
        run = IntelligenceAutomationRun.objects.select_for_update().filter(id=run_id).first()
        if not run:
            raise ApprovalError(f"IntelligenceAutomationRun #{run_id} not found.")

        verify_operator_authorization(operator_user, run.client_id)

        # Status check
        if run.status != AutomationStatus.AWAITING_APPROVAL.value:
            raise ApprovalError(
                f"Cannot approve run #{run.id} with status '{run.status}'. Must be {AutomationStatus.AWAITING_APPROVAL.value}."
            )

        # Double approval check
        if run.approval_status == ApprovalStatus.APPROVED.value:
            raise DoubleApprovalError(f"Run #{run.id} has already been approved.")
        if run.approval_status != ApprovalStatus.PENDING.value:
            raise ApprovalError(f"Cannot approve run #{run.id} with approval_status '{run.approval_status}'.")

        # Freeze token validation
        expected_token = compute_approval_token(
            run_id=run.id,
            execution_identity=run.execution_identity,
            pipeline_version=run.pipeline_version,
            period_start=run.period_start,
            period_end=run.period_end,
            report_id=run.report_id,
        )
        if run.approval_token and run.approval_token != expected_token:
            raise StaleApprovalError(
                f"Run #{run.id} approval token mismatch. Run parameters may have changed."
            )

        now = timezone.now()
        safe_comment = redact_secrets(comment or "")

        run.approval_status = ApprovalStatus.APPROVED.value
        run.approval_decided_at = now
        run.approved_by = operator_user if getattr(operator_user, "is_authenticated", False) else None
        run.approval_comment_safe = safe_comment
        
        meta = run.metadata or {}
        meta["approved_by_id"] = getattr(operator_user, "id", None)
        meta["approval_decision_at"] = now.isoformat()
        run.metadata = meta

        run.save(update_fields=[
            "approval_status",
            "approval_decided_at",
            "approved_by",
            "approval_comment_safe",
            "metadata",
            "updated_at",
        ])

        log_automation_event(
            event_name="automation.approval.approved",
            run_id=run.id,
            client_id=run.client_id,
            stage=run.current_stage,
            status=run.status,
            operator_id=getattr(operator_user, "id", None),
            decision="APPROVED",
            extra={"comment": safe_comment, "approval_token": run.approval_token},
        )

        return run


def reject_intelligence_run(
    run_id: int,
    operator_user: Any,
    comment: str = "",
) -> IntelligenceAutomationRun:
    """
    Rejects an automation run currently in AWAITING_APPROVAL status.
    Transitions run status to CANCELLED and approval_status to REJECTED.
    """
    with transaction.atomic():
        run = IntelligenceAutomationRun.objects.select_for_update().filter(id=run_id).first()
        if not run:
            raise ApprovalError(f"IntelligenceAutomationRun #{run_id} not found.")

        verify_operator_authorization(operator_user, run.client_id)

        if run.status != AutomationStatus.AWAITING_APPROVAL.value:
            raise ApprovalError(
                f"Cannot reject run #{run.id} with status '{run.status}'. Must be {AutomationStatus.AWAITING_APPROVAL.value}."
            )

        if run.approval_status != ApprovalStatus.PENDING.value:
            raise ApprovalError(f"Cannot reject run #{run.id} with approval_status '{run.approval_status}'.")

        now = timezone.now()
        safe_comment = redact_secrets(comment or "")

        run.status = AutomationStatus.CANCELLED.value
        run.approval_status = ApprovalStatus.REJECTED.value
        run.approval_decided_at = now
        run.approved_by = operator_user if getattr(operator_user, "is_authenticated", False) else None
        run.approval_comment_safe = safe_comment
        run.finished_at = now

        meta = run.metadata or {}
        meta["rejected_by_id"] = getattr(operator_user, "id", None)
        meta["rejection_decision_at"] = now.isoformat()
        run.metadata = meta

        run.save(update_fields=[
            "status",
            "approval_status",
            "approval_decided_at",
            "approved_by",
            "approval_comment_safe",
            "finished_at",
            "metadata",
            "updated_at",
        ])

        log_automation_event(
            event_name="automation.approval.rejected",
            run_id=run.id,
            client_id=run.client_id,
            stage=run.current_stage,
            status=run.status,
            operator_id=getattr(operator_user, "id", None),
            decision="REJECTED",
            extra={"comment": safe_comment},
        )

        return run


def resume_approved_intelligence_run(
    run_id: int,
    operator_user: Optional[Any] = None,
    now: Optional[Any] = None,
) -> IntelligenceAutomationRun:
    """
    Resumes an approved automation run after operator sign-off.
    Enforces:
    1. Lock reacquisition before continuation
    2. Active uniqueness verification
    3. Complete safety revalidation after human delay
    4. Deterministic artifact reuse
    5. Strict provider boundary (no live LLM generation in BS-6C)
    """
    current_time = now or timezone.now()

    # Step 1: Load and verify approved state
    with transaction.atomic():
        run = IntelligenceAutomationRun.objects.select_for_update().filter(id=run_id).first()
        if not run:
            raise ApprovalError(f"IntelligenceAutomationRun #{run_id} not found.")

        if operator_user:
            verify_operator_authorization(operator_user, run.client_id)

        if run.status != AutomationStatus.AWAITING_APPROVAL.value or run.approval_status != ApprovalStatus.APPROVED.value:
            raise ApprovalError(
                f"Run #{run.id} is not eligible for resume (status='{run.status}', approval_status='{run.approval_status}')."
            )

    # Step 2: Reacquire single-flight advisory lock
    lock = SingleFlightLock(run.execution_identity)
    if not lock.acquire():
        error_msg = f"Single-flight lock reacquisition rejected for identity: {run.execution_identity}"
        log_automation_event(
            event_name="automation.resume.blocked",
            run_id=run.id,
            client_id=run.client_id,
            stage=run.current_stage,
            status=run.status,
            error_code="CONCURRENCY_LOCK_ACTIVE",
            error_message=error_msg,
        )
        raise ConcurrencyLockError(error_msg)

    try:
        # Step 3: Verify active uniqueness
        active_conflict = IntelligenceAutomationRun.objects.filter(
            client_id=run.client_id,
            period_start=run.period_start,
            period_end=run.period_end,
            pipeline_version=run.pipeline_version,
            status=AutomationStatus.RUNNING.value,
        ).exclude(id=run.id).first()

        if active_conflict:
            error_msg = f"Concurrent active run #{active_conflict.id} already executing for identity: {run.execution_identity}"
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "CONCURRENCY_ACTIVE_CONFLICT"
            run.error_message_safe = error_msg
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Step 4: Revalidate Safety Gates After Human Delay (Section N)
        # Gate 4.1: Client active
        client = Client.objects.filter(id=run.client_id).first()
        if not client or not client.is_active:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "CLIENT_INACTIVE"
            run.error_message_safe = "Client is inactive or deleted upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Gate 4.2: Config enabled
        config = IntelligenceAutomationConfig.objects.filter(client_id=run.client_id).first()
        if not config or not config.enabled:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "AUTOMATION_CONFIG_DISABLED"
            run.error_message_safe = "Automation configuration is missing or disabled upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Gate 4.3: Platform credentials
        creds = list(PlatformCredential.objects.filter(client_id=run.client_id, is_active=True).values("id", "expires_at"))
        if not creds:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "PROVIDER_DISCONNECTED"
            run.error_message_safe = "No active platform credentials found upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        all_expired = all(
            bool(c.get("expires_at") and current_time >= (c["expires_at"] - timedelta(minutes=10)))
            for c in creds
        )
        if all_expired:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "PROVIDER_CREDENTIAL_EXPIRED"
            run.error_message_safe = "All platform credentials expired upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Gate 4.4: Freshness recheck
        freshness = evaluate_tenant_freshness(
            client_id=run.client_id,
            period_start=run.period_start,
            period_end=run.period_end,
            max_staleness_hours=config.max_data_staleness_hours,
            now=current_time,
        )
        if freshness.code in [FreshnessCode.MISSING, FreshnessCode.UNKNOWN]:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = f"ANALYTICS_DATA_{freshness.code.value}"
            run.error_message_safe = f"Analytics data is {freshness.code.value} upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run
        elif freshness.code == FreshnessCode.STALE:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "ANALYTICS_DATA_STALE"
            run.error_message_safe = f"Analytics data became stale (age {freshness.data_age_hours:.1f}h > {config.max_data_staleness_hours}h) upon resume."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Gate 4.5: Approval token immutability verification
        expected_token = compute_approval_token(
            run_id=run.id,
            execution_identity=run.execution_identity,
            pipeline_version=run.pipeline_version,
            period_start=run.period_start,
            period_end=run.period_end,
            report_id=run.report_id,
        )
        if run.approval_token and run.approval_token != expected_token:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "APPROVAL_TOKEN_MISMATCH"
            run.error_message_safe = "Approval token mismatch. Execution identity or report changed."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Gate 4.6: Existing Validated Narrative Reuse (Section O)
        matching_narrative = None
        if run.report_id:
            matching_narrative = ExecutiveNarrative.objects.filter(
                executive_report_id=run.report_id,
                status="VALIDATED",
            ).order_by("-id").first()
        elif run.client_id:
            matching_narrative = ExecutiveNarrative.objects.filter(
                executive_report__client_id=run.client_id,
                executive_report__period_start=run.period_start,
                executive_report__period_end=run.period_end,
                status="VALIDATED",
            ).order_by("-id").first()

        if matching_narrative:
            # REUSE existing validated narrative! Zero LLM call!
            run.narrative = matching_narrative
            run.status = AutomationStatus.COMPLETED.value
            run.current_stage = AutomationStage.COMPLETE.value
            run.finished_at = timezone.now()
            meta = run.metadata or {}
            meta["narrative_reuse"] = f"REUSE ExecutiveNarrative #{matching_narrative.id} (VALIDATED)"
            run.metadata = meta
            run.save(update_fields=["narrative", "status", "current_stage", "finished_at", "metadata", "updated_at"])

            log_automation_event(
                event_name="automation.run.completed",
                run_id=run.id,
                client_id=run.client_id,
                stage=AutomationStage.COMPLETE.value,
                trigger_type=run.trigger_type,
                dry_run=run.dry_run,
                status=run.status,
                narrative_id=matching_narrative.id,
                extra={"reused_narrative_id": matching_narrative.id},
            )
            return run

        # Gate 4.7: Provider budget check
        if config.provider_call_budget < 1:
            run.status = AutomationStatus.BLOCKED.value
            run.error_code = "PROVIDER_CALL_BUDGET_EXHAUSTED"
            run.error_message_safe = "Provider call budget is exhausted (0)."
            run.save(update_fields=["status", "error_code", "error_message_safe", "updated_at"])
            log_automation_event(
                event_name="automation.resume.blocked",
                run_id=run.id,
                client_id=run.client_id,
                stage=run.current_stage,
                status=run.status,
                error_code=run.error_code,
                error_message=run.error_message_safe,
            )
            return run

        # Step 5: Transition to RUNNING
        run.status = AutomationStatus.RUNNING.value
        run.save(update_fields=["status", "updated_at"])

        log_automation_event(
            event_name="automation.resume.started",
            run_id=run.id,
            client_id=run.client_id,
            stage=run.current_stage,
            status=run.status,
            trigger_type=run.trigger_type,
        )

        # Step 6: Provider Boundary Reached (Section P)
        # In BS-6C: STOP immediately before any live provider call!
        meta = run.metadata or {}
        meta["provider_boundary_reached"] = True
        meta["provider_boundary_status"] = PROVIDER_EXECUTION_READY
        meta["would_call_provider"] = True
        meta["provider_call_count"] = 0
        meta["resumed_at"] = timezone.now().isoformat()
        run.metadata = meta
        run.provider_call_count = 0
        run.save(update_fields=["metadata", "provider_call_count", "updated_at"])

        log_automation_event(
            event_name="automation.provider_boundary.reached",
            run_id=run.id,
            client_id=run.client_id,
            stage=run.current_stage,
            status=run.status,
            provider_call_count=0,
            extra={
                "would_call_provider": True,
                "provider_boundary_status": PROVIDER_EXECUTION_READY,
                "approval_token": run.approval_token,
            },
        )

        return run

    finally:
        # Step 7: Always release lock before returning control
        lock.release()
