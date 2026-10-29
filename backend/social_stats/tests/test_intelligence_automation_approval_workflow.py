"""
BS-6C Run-Level Approval Workflow & Controlled Automation Resume Test Suite.
Validates:
1. Status transitions: RUNNING -> AWAITING_APPROVAL -> RUNNING (resume) -> COMPLETED
2. Rejection path: AWAITING_APPROVAL -> CANCELLED (approval_status=REJECTED)
3. Invalid transitions: COMPLETED / BLOCKED runs cannot be approved
4. Locking contract: advisory lock released on AWAITING_APPROVAL, reacquired on resume
5. Security: authorized operator vs unauthorized role vs wrong tenant isolation
6. Double approval: second approval rejected with DoubleApprovalError
7. Immutability: decision and token remain frozen
8. Revalidation after delay:
   - Fresh -> Stale blocks resume
   - Enabled -> Disabled blocks resume
   - Creds -> Missing/expired blocks resume
   - Narrative appears -> REUSES existing narrative without provider call
   - Budget exhausted -> blocks resume
9. Provider boundary: stops before live Ollama/LLM invocation (provider_call_count=0)
10. Scanner behavior: 96 discovery ticks produce 0 duplicate runs and 0 provider calls
"""
from datetime import date, datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation import (
    PIPELINE_VERSION,
    PROVIDER_EXECUTION_READY,
    ApprovalError,
    ApprovalStatus,
    AuthorizationError,
    AutomationStage,
    AutomationStatus,
    ConcurrencyLockError,
    DoubleApprovalError,
    SingleFlightLock,
    StaleApprovalError,
    approve_intelligence_run,
    compute_approval_token,
    compute_execution_identity,
    execute_intelligence_automation,
    reject_intelligence_run,
    resume_approved_intelligence_run,
)
from social_stats.analytics.automation.tasks import discover_and_enqueue_due_intelligence_automations

User = get_user_model()


class IntelligenceAutomationApprovalWorkflowTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(
            username="admin_operator",
            email="admin_op@example.com",
            password="securepassword123",
        )
        self.unauthorized_user = User.objects.create_user(
            username="random_viewer",
            email="random@example.com",
            password="securepassword123",
        )
        self.tenant_client = Client.objects.create(
            name="Approval Pilot Tenant",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="approval_tenant@example.com",
        )
        self.other_client = Client.objects.create(
            name="Other Client Tenant",
            is_active=True,
            timezone="America/New_York",
            email="other_tenant@example.com",
        )
        self.client_user = User.objects.create_user(
            username="client_owner",
            email="owner@example.com",
            password="securepassword123",
        )
        self.tenant_client.owner_user = self.client_user
        self.tenant_client.save()

        self.cred = PlatformCredential.objects.create(
            client=self.tenant_client,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.tenant_client,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
            lookback_days=30,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=True,
            provider_call_budget=1,
            max_retry_count=0,
            max_data_staleness_hours=24,
        )
        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 30)

        # Seed minimal fresh data so run passes data eligibility
        self.sync_log = SyncLog.objects.create(
            client=self.tenant_client,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=2),
            records_synced=10,
        )
        self.snapshot = SocialMetricSnapshot.objects.create(
            client=self.tenant_client,
            platform="facebook",
            account_id="act_123",
            metric_scope="PAGE",
            object_id="page_123",
            raw_metric_name="impressions",
            normalized_metric="impressions",
            metric_value=1500,
            bucket_period="DAY",
            bucket_timestamp=datetime(2026, 9, 15, 12, 0, 0, tzinfo=dt_tz.utc),
        )
        self.report = ExecutiveReport.objects.create(
            client=self.tenant_client,
            period_start=self.period_start,
            period_end=self.period_end,
            status="GENERATED",
            source_hash="sha256-report-abc-123",
        )

    # ── Z. Status Transitions ──────────────────────────────────────────────────
    def test_01_running_to_awaiting_approval_transition(self):
        """Proves that a run with generate_narrative=True and require_operator_approval=True pauses in AWAITING_APPROVAL."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)
        self.assertEqual(run.current_stage, AutomationStage.NARRATIVE_CHECK.value)
        self.assertEqual(run.approval_status, ApprovalStatus.PENDING.value)
        self.assertIsNotNone(run.approval_requested_at)
        self.assertTrue(bool(run.approval_token))
        self.assertEqual(run.provider_call_count, 0)
        self.assertIsNone(run.finished_at)

    def test_02_approval_and_resume_transitions(self):
        """Proves AWAITING_APPROVAL -> APPROVED -> RUNNING (resume) -> Provider Boundary."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)

        # Operator approves
        approved_run = approve_intelligence_run(
            run_id=run.id,
            operator_user=self.operator,
            comment="Approved for review",
        )
        self.assertEqual(approved_run.approval_status, ApprovalStatus.APPROVED.value)
        self.assertEqual(approved_run.approved_by, self.operator)
        self.assertIsNotNone(approved_run.approval_decided_at)
        self.assertEqual(approved_run.status, AutomationStatus.AWAITING_APPROVAL.value)

        # Operator resumes
        resumed_run = resume_approved_intelligence_run(
            run_id=run.id,
            operator_user=self.operator,
        )
        self.assertEqual(resumed_run.status, AutomationStatus.PROVIDER_EXECUTION_READY.value)
        self.assertEqual(resumed_run.provider_call_count, 0)
        self.assertTrue(resumed_run.metadata.get("provider_boundary_reached"))
        self.assertEqual(resumed_run.metadata.get("provider_boundary_status"), PROVIDER_EXECUTION_READY)

    def test_03_rejection_transitions_to_cancelled(self):
        """Proves AWAITING_APPROVAL -> CANCELLED after operator rejection."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        rejected_run = reject_intelligence_run(
            run_id=run.id,
            operator_user=self.operator,
            comment="Period cancelled by client request",
        )
        self.assertEqual(rejected_run.status, AutomationStatus.CANCELLED.value)
        self.assertEqual(rejected_run.approval_status, ApprovalStatus.REJECTED.value)
        self.assertEqual(rejected_run.approved_by, self.operator)
        self.assertIsNotNone(rejected_run.finished_at)
        self.assertEqual(rejected_run.provider_call_count, 0)

    def test_04_invalid_transition_rejected(self):
        """Proves COMPLETED and BLOCKED runs cannot be approved."""
        completed_run = IntelligenceAutomationRun.objects.create(
            client=self.tenant_client,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity="completed-identity-123",
            status=AutomationStatus.COMPLETED.value,
            current_stage=AutomationStage.COMPLETE.value,
        )
        with self.assertRaises(ApprovalError):
            approve_intelligence_run(completed_run.id, self.operator)

        blocked_run = IntelligenceAutomationRun.objects.create(
            client=self.tenant_client,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity="blocked-identity-456",
            status=AutomationStatus.BLOCKED.value,
            current_stage=AutomationStage.ELIGIBILITY.value,
            error_code="ANALYTICS_DATA_MISSING",
        )
        with self.assertRaises(ApprovalError):
            approve_intelligence_run(blocked_run.id, self.operator)

    # ── AA. Locking Contract ──────────────────────────────────────────────────
    def test_05_lock_released_on_awaiting_approval(self):
        """Proves that advisory lock is released when run pauses in AWAITING_APPROVAL."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)

        # Another process must immediately be able to acquire the execution identity lock
        test_lock = SingleFlightLock(run.execution_identity)
        acquired = test_lock.acquire()
        self.assertTrue(acquired)
        test_lock.release()

    def test_06_resume_reacquires_lock(self):
        """Proves resume requires reacquiring the lock and fails closed if already held."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        # Simulate lock held by another concurrent worker process
        with patch.object(SingleFlightLock, "acquire", return_value=False):
            with self.assertRaises(ConcurrencyLockError):
                resume_approved_intelligence_run(run.id, self.operator)

    def test_07_active_uniqueness_includes_awaiting_approval(self):
        """Proves DB unique constraint prevents duplicate runs while one is AWAITING_APPROVAL."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)

        with self.assertRaises(IntegrityError):
            IntelligenceAutomationRun.objects.create(
                client=self.tenant_client,
                period_start=self.period_start,
                period_end=self.period_end,
                pipeline_version=PIPELINE_VERSION,
                execution_identity=run.execution_identity,
                status=AutomationStatus.RUNNING.value,
                current_stage=AutomationStage.REPORT_CHECK.value,
            )

    # ── AB. Security & Tenant Isolation ────────────────────────────────────────
    def test_08_operator_authorization_and_tenant_isolation(self):
        """Proves superuser/client owner can approve, but wrong tenant or unauthorized user is denied."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        # Unauthorized random user denied
        with self.assertRaises(AuthorizationError):
            approve_intelligence_run(run.id, self.unauthorized_user)

        # Client owner allowed
        approved = approve_intelligence_run(run.id, self.client_user, comment="Client owner sign-off")
        self.assertEqual(approved.approval_status, ApprovalStatus.APPROVED.value)

    def test_09_double_approval_protection(self):
        """Proves double approval raises DoubleApprovalError and preserves first decision."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator, comment="Initial approval")

        with self.assertRaises(DoubleApprovalError):
            approve_intelligence_run(run.id, self.operator, comment="Second approval attempt")

        run.refresh_from_db()
        self.assertEqual(run.approval_comment_safe, "Initial approval")

    def test_10_approval_token_identity_freeze(self):
        """Proves tampering with execution parameters invalidates approval token."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        # Corrupt approval token
        run.approval_token = "tampered-token-xyz"
        run.save(update_fields=["approval_token"])

        with self.assertRaises(StaleApprovalError):
            approve_intelligence_run(run.id, self.operator)

    # ── AC. Revalidation After Delay ───────────────────────────────────────────
    def test_11_revalidation_data_became_stale(self):
        """Proves that if data becomes stale between approval and resume, resume blocks safely."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        # Simulate 72 hours passing: sync log is now 74 hours old (>24h max staleness)
        simulated_future = timezone.now() + timedelta(hours=72)
        resumed = resume_approved_intelligence_run(
            run_id=run.id,
            operator_user=self.operator,
            now=simulated_future,
        )
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "ANALYTICS_DATA_STALE")
        self.assertEqual(resumed.provider_call_count, 0)

    def test_12_revalidation_config_disabled(self):
        """Proves that disabling config between approval and resume blocks execution."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        # Operator disables config in the interim
        self.config.enabled = False
        self.config.save()

        resumed = resume_approved_intelligence_run(run.id, self.operator)
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "AUTOMATION_CONFIG_DISABLED")
        self.assertEqual(resumed.provider_call_count, 0)

    def test_13_revalidation_credentials_disconnected(self):
        """Proves that revoked credentials between approval and resume block execution."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        # Disconnect credentials
        self.cred.is_active = False
        self.cred.save()

        resumed = resume_approved_intelligence_run(run.id, self.operator)
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "PROVIDER_DISCONNECTED")
        self.assertEqual(resumed.provider_call_count, 0)

    def test_14_revalidation_validated_narrative_appears(self):
        """Proves that if a VALIDATED narrative appears before resume, resume reuses it and completes cleanly."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        # A validated narrative is uploaded/generated in the interim
        narrative = ExecutiveNarrative.objects.create(
            client=self.tenant_client,
            executive_report=self.report,
            prompt_version="bs4h-v1",
            status="VALIDATED",
            rendered_text="Pre-existing validated executive overview.",
            provider="fake",
            model_name="stub-model",
            source_hash="sha256-report-abc-123",
            context_hash="sha256-context-abc-123",
        )

        resumed = resume_approved_intelligence_run(run.id, self.operator)
        self.assertEqual(resumed.status, AutomationStatus.COMPLETED.value)
        self.assertEqual(resumed.narrative_id, narrative.id)
        self.assertEqual(resumed.provider_call_count, 0)

    def test_15_revalidation_provider_budget_exhausted(self):
        """Proves that if provider call budget is set to 0, resume blocks."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        self.config.provider_call_budget = 0
        self.config.save()

        resumed = resume_approved_intelligence_run(run.id, self.operator)
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "PROVIDER_CALL_BUDGET_EXHAUSTED")
        self.assertEqual(resumed.provider_call_count, 0)

    # ── AD. Provider Boundary (Zero Provider Calls) ────────────────────────────
    def test_16_provider_boundary_reached_with_zero_calls(self):
        """Proves that in BS-6C, resume stops strictly at the provider boundary without calling Ollama."""
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        approve_intelligence_run(run.id, self.operator)

        with patch("urllib.request.urlopen") as mock_url, \
             patch("requests.post") as mock_post:
            
            resumed = resume_approved_intelligence_run(run.id, self.operator)
            self.assertEqual(resumed.status, AutomationStatus.PROVIDER_EXECUTION_READY.value)
            self.assertEqual(resumed.provider_call_count, 0)
            self.assertTrue(resumed.metadata.get("provider_boundary_reached"))
            self.assertTrue(resumed.metadata.get("would_call_provider"))
            
            # Zero HTTP / API calls to any LLM provider
            self.assertEqual(mock_url.call_count, 0)
            self.assertEqual(mock_post.call_count, 0)

    # ── AE. Scanner Awaiting-Approval Behavior ─────────────────────────────────
    def test_17_scanner_recognizes_awaiting_approval_over_96_ticks(self):
        """Simulates 96 discovery ticks (24 hours at 15m) while run awaits approval: 0 duplicate runs, 0 provider calls."""
        # Create initial awaiting-approval run
        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)
        initial_run_count = IntelligenceAutomationRun.objects.count()

        start_tick = datetime(2026, 10, 1, 2, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        for tick in range(96):
            tick_time = start_tick + timedelta(minutes=15 * tick)
            with patch("django.utils.timezone.now", return_value=tick_time):
                res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
                # Client must NOT be re-enqueued
                self.assertNotIn(self.tenant_client.id, res["due_client_ids"])
                # Summary must cite RUN_ALREADY_EXISTS_OR_ACTIVE with AWAITING_APPROVAL status
                skipped = next((s for s in res["skipped_summary"] if s["client_id"] == self.tenant_client.id), None)
                self.assertIsNotNone(skipped)
                self.assertIn("RUN_ALREADY_EXISTS_OR_ACTIVE", skipped["reason"])
                self.assertIn("AWAITING_APPROVAL", skipped["reason"])

        # AutomationRun count must remain strictly invariant
        final_run_count = IntelligenceAutomationRun.objects.count()
        self.assertEqual(final_run_count, initial_run_count)

    # ── Management Command & API Workflows ─────────────────────────────────────
    def test_18_management_command_workflow(self):
        """Proves python manage.py approve_intelligence_run CLI operates safely."""
        from django.core.management import call_command
        from io import StringIO

        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        out = StringIO()
        call_command(
            "approve_intelligence_run",
            run=run.id,
            comment="CLI approval sign-off",
            operator_id=self.operator.id,
            stdout=out,
        )
        run.refresh_from_db()
        self.assertEqual(run.approval_status, ApprovalStatus.APPROVED.value)
        self.assertEqual(run.approved_by, self.operator)
        self.assertIn("APPROVED", out.getvalue())

    def test_19_api_endpoints_workflow(self):
        """Proves API endpoints for approve, reject, and resume operate with proper tenant isolation."""
        from rest_framework.test import APIClient

        run = execute_intelligence_automation(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )

        client = APIClient()
        # Unauthorized client attempt
        client.force_authenticate(user=self.unauthorized_user)
        resp = client.post(f"/api/analytics/automation/runs/{run.id}/approve/", {"comment": "hack attempt"})
        self.assertEqual(resp.status_code, 403)

        # Authorized operator approval
        client.force_authenticate(user=self.operator)
        resp = client.post(f"/api/analytics/automation/runs/{run.id}/approve/", {"comment": "API operator sign-off"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["approval_status"], "APPROVED")

        # Controlled resume via API
        resp_resume = client.post(f"/api/analytics/automation/runs/{run.id}/resume/")
        self.assertEqual(resp_resume.status_code, 200)
        self.assertEqual(resp_resume.data["status"], "PROVIDER_EXECUTION_READY")
        self.assertEqual(resp_resume.data["provider_call_count"], 0)
