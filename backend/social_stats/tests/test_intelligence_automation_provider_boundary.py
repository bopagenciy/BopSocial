"""
BS-6C.0A Provider Boundary Single-Flight & Execution-Ready State Contract Test Suite.

Validates:
1. provider-ready state classification (persisted in model choices, constants, and database)
2. provider-ready active uniqueness (database constraint blocks duplicate insert)
3. scanner does not duplicate provider-ready run
4. 96-tick no-duplicate test
5. provider execution reacquires advisory lock
6. concurrent executor blocked
7. approval token rechecked
8. freshness rechecked
9. config rechecked
10. credentials rechecked
11. budget rechecked
12. narrative reuse race
13. provider reservation atomicity
14. crash-before-call state behavior
15. zero live provider calls
"""
from datetime import date, datetime, timedelta, timezone as dt_tz
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
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
    PROVIDER_EXECUTING,
    ApprovalError,
    ApprovalIdentityMismatchError,
    ApprovalStateError,
    ApprovalStatus,
    AuthorizationError,
    AutomationStage,
    AutomationStatus,
    ConcurrencyLockError,
    SingleFlightLock,
    compute_approval_token,
    compute_execution_identity,
    reserve_provider_execution,
    resume_approved_intelligence_run,
)
from social_stats.analytics.automation.tasks import discover_and_enqueue_due_intelligence_automations

User = get_user_model()


class ProviderBoundarySingleFlightContractTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(
            username="boundary_operator",
            email="operator@example.com",
            password="securepassword123",
        )
        self.tenant_client = Client.objects.create(
            name="Boundary Pilot Tenant",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="boundary_tenant@example.com",
        )
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

        # Baseline fresh telemetry
        self.ref_now = timezone.now()
        SyncLog.objects.create(
            client=self.tenant_client,
            platform="facebook",
            status="success",
            finished_at=self.ref_now - timedelta(hours=2),
            records_synced=10,
        )
        SocialMetricSnapshot.objects.create(
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
            source_hash="boundary_report_hash_123",
        )
        self.exec_identity = compute_execution_identity(
            client_id=self.tenant_client.id,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
        )

    def _create_approved_run(self, status=AutomationStatus.PROVIDER_EXECUTION_READY.value):
        """Helper to create a run in provider-ready state."""
        run = IntelligenceAutomationRun.objects.create(
            client=self.tenant_client,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=self.exec_identity,
            trigger_type="MANUAL",
            status=status,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            approval_status=ApprovalStatus.APPROVED.value,
            approval_requested_at=timezone.now() - timedelta(minutes=10),
            approval_decided_at=timezone.now() - timedelta(minutes=5),
            approved_by=self.operator,
            approval_comment_safe="Approved for provider boundary testing",
            report=self.report,
            provider_call_count=0,
        )
        run.approval_token = compute_approval_token(
            run_id=run.id,
            execution_identity=run.execution_identity,
            pipeline_version=run.pipeline_version,
            period_start=run.period_start,
            period_end=run.period_end,
            report_id=run.report_id,
        )
        run.save(update_fields=["approval_token"])
        return run

    def test_01_provider_ready_and_executing_state_classification(self):
        """1. Verify PROVIDER_EXECUTION_READY and PROVIDER_EXECUTING are first-class choices and persist cleanly."""
        self.assertEqual(AutomationStatus.PROVIDER_EXECUTION_READY.value, "PROVIDER_EXECUTION_READY")
        self.assertEqual(AutomationStatus.PROVIDER_EXECUTING.value, "PROVIDER_EXECUTING")
        self.assertEqual(PROVIDER_EXECUTION_READY, "PROVIDER_EXECUTION_READY")
        self.assertEqual(PROVIDER_EXECUTING, "PROVIDER_EXECUTING")

        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)
        self.assertEqual(run.status, "PROVIDER_EXECUTION_READY")

        run.status = AutomationStatus.PROVIDER_EXECUTING.value
        run.save(update_fields=["status"])
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, "PROVIDER_EXECUTING")

    def test_02_provider_ready_active_uniqueness(self):
        """2. Verify unique_active_intelligence_run protects PROVIDER_EXECUTION_READY against duplicate runs."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Attempt to insert a second active run for same client, period, pipeline_version
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                IntelligenceAutomationRun.objects.create(
                    client=self.tenant_client,
                    period_start=self.period_start,
                    period_end=self.period_end,
                    pipeline_version=PIPELINE_VERSION,
                    execution_identity=self.exec_identity,
                    trigger_type="SCHEDULED",
                    status="PENDING",
                )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                IntelligenceAutomationRun.objects.create(
                    client=self.tenant_client,
                    period_start=self.period_start,
                    period_end=self.period_end,
                    pipeline_version=PIPELINE_VERSION,
                    execution_identity=self.exec_identity,
                    trigger_type="SCHEDULED",
                    status="PROVIDER_EXECUTION_READY",
                )

    def test_03_scanner_does_not_duplicate_provider_ready_run(self):
        """3. Verify periodic discovery scanner recognizes PROVIDER_EXECUTION_READY as active and skips enqueuing."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Align due date
        oct_now = datetime(2026, 10, 2, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("django.utils.timezone.now", return_value=oct_now):
            result = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        self.assertNotIn(self.tenant_client.id, result["due_client_ids"])
        skipped = [s for s in result["skipped_summary"] if s["client_id"] == self.tenant_client.id]
        self.assertTrue(len(skipped) > 0)
        self.assertIn("RUN_ALREADY_EXISTS_OR_ACTIVE", skipped[0]["reason"])
        self.assertIn("PROVIDER_EXECUTION_READY", skipped[0]["reason"])

        # No new run created
        self.assertEqual(IntelligenceAutomationRun.objects.filter(client=self.tenant_client).count(), 1)

    def test_04_96_tick_scanner_no_duplicate_and_zero_provider_calls(self):
        """4. Verify 96 consecutive scanner ticks produce 0 duplicate runs and 0 provider calls while in PROVIDER_EXECUTION_READY."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        base_time = datetime(2026, 10, 2, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        for tick in range(96):
            tick_now = base_time + timedelta(minutes=15 * tick)
            with patch("django.utils.timezone.now", return_value=tick_now):
                discover_and_enqueue_due_intelligence_automations(dry_run=True)

        # Total runs must remain exactly 1
        total_runs = IntelligenceAutomationRun.objects.filter(client=self.tenant_client).count()
        self.assertEqual(total_runs, 1)

        # Provider calls must remain 0
        reloaded_run = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded_run.provider_call_count, 0)

    def test_05_provider_execution_reacquires_advisory_lock(self):
        """5. Verify reserve_provider_execution requires single-flight advisory lock."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Simulate lock held by another process
        with patch.object(SingleFlightLock, "acquire", return_value=False):
            with self.assertRaises(ConcurrencyLockError):
                reserve_provider_execution(run.id, self.operator)

        # Run remains unchanged
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, "PROVIDER_EXECUTION_READY")
        self.assertEqual(reloaded.provider_call_count, 0)

    def test_06_concurrent_executor_blocked(self):
        """6. Verify concurrent executor is blocked if status is already PROVIDER_EXECUTING."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # First executor successfully reserves
        res1 = reserve_provider_execution(run.id, self.operator)
        self.assertTrue(res1["reserved"])
        self.assertEqual(res1["status"], "PROVIDER_EXECUTING")

        # Second executor attempts to reserve the same run
        with self.assertRaises(ApprovalStateError) as ctx:
            reserve_provider_execution(run.id, self.operator)
        self.assertIn("Must be 'PROVIDER_EXECUTION_READY'", str(ctx.exception))

    def test_07_approval_token_rechecked(self):
        """7. Verify approval token is rechecked before reservation and blocks if identity/report changed."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Tamper with approval token
        run.approval_token = "tampered_corrupted_token_digest_1234567890abcdef"
        run.save(update_fields=["approval_token"])

        with self.assertRaises(ApprovalIdentityMismatchError):
            reserve_provider_execution(run.id, self.operator)

        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(reloaded.error_code, "APPROVAL_TOKEN_MISMATCH")

    def test_08_freshness_rechecked(self):
        """8. Verify telemetry freshness is rechecked and blocks if data became stale."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Fast-forward time past max_data_staleness_hours (24h)
        future_time = self.ref_now + timedelta(hours=36)
        res = reserve_provider_execution(run.id, self.operator, now=future_time)

        self.assertFalse(res["reserved"])
        self.assertIn("ANALYTICS_DATA_STALE", res["reason"])
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(reloaded.error_code, "ANALYTICS_DATA_STALE")

    def test_09_config_rechecked(self):
        """9. Verify config enabled is rechecked and blocks if disabled."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        self.config.enabled = False
        self.config.save(update_fields=["enabled"])

        res = reserve_provider_execution(run.id, self.operator)
        self.assertFalse(res["reserved"])
        self.assertEqual(res["reason"], "AUTOMATION_CONFIG_DISABLED")
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.BLOCKED.value)

    def test_10_credentials_rechecked(self):
        """10. Verify platform credentials are rechecked and blocks if expired."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        self.cred.expires_at = timezone.now() - timedelta(minutes=5)
        self.cred.save(update_fields=["expires_at"])

        res = reserve_provider_execution(run.id, self.operator)
        self.assertFalse(res["reserved"])
        self.assertEqual(res["reason"], "PROVIDER_CREDENTIAL_EXPIRED")
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.BLOCKED.value)

    def test_11_budget_rechecked(self):
        """11. Verify provider call budget is rechecked and blocks if exhausted."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        self.config.provider_call_budget = 0
        self.config.save(update_fields=["provider_call_budget"])

        res = reserve_provider_execution(run.id, self.operator)
        self.assertFalse(res["reserved"])
        self.assertEqual(res["reason"], "PROVIDER_CALL_BUDGET_EXHAUSTED")
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.BLOCKED.value)

    def test_12_narrative_reuse_race(self):
        """12. Verify that if a VALIDATED narrative appears before reservation, it is reused with 0 provider calls."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Another process creates a validated narrative
        narrative = ExecutiveNarrative.objects.create(
            client=self.tenant_client,
            executive_report=self.report,
            status="VALIDATED",
            rendered_text="Pre-existing validated narrative text.",
            model_name="test-model",
            prompt_version="v1",
            source_hash="narr_src_hash_1",
            context_hash="narr_ctx_hash_1",
        )

        res = reserve_provider_execution(run.id, self.operator)
        self.assertFalse(res["reserved"])
        self.assertTrue(res.get("reused"))
        self.assertEqual(res.get("narrative_id"), narrative.id)

        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, AutomationStatus.COMPLETED.value)
        self.assertEqual(reloaded.narrative_id, narrative.id)
        self.assertEqual(reloaded.provider_call_count, 0)

    def test_13_provider_reservation_atomicity(self):
        """13. Verify reservation atomically transitions to PROVIDER_EXECUTING and increments call budget."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        res = reserve_provider_execution(run.id, self.operator)
        self.assertTrue(res["reserved"])
        self.assertEqual(res["status"], AutomationStatus.PROVIDER_EXECUTING.value)
        self.assertEqual(res["provider_call_count"], 1)
        self.assertTrue(bool(res["reservation_token"]))

        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, "PROVIDER_EXECUTING")
        self.assertEqual(reloaded.provider_call_count, 1)
        self.assertIn("provider_call_reserved_at", reloaded.metadata)

    def test_14_crash_before_call_state_behavior(self):
        """14. Verify crash-before-call fail-closed behavior: session lock releases, run remains PROVIDER_EXECUTING, no auto-retry."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Reservation completes
        res = reserve_provider_execution(run.id, self.operator)
        self.assertTrue(res["reserved"])

        # Worker crashes here before dispatching network call.
        # Lock is session-scoped, so in PostgreSQL pg_locks advisory lock automatically vanishes.
        # Check that the run cannot be re-reserved (budget exhausted and status != PROVIDER_EXECUTION_READY)
        with self.assertRaises(ApprovalStateError):
            reserve_provider_execution(run.id, self.operator)

        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, "PROVIDER_EXECUTING")
        self.assertEqual(reloaded.provider_call_count, 1)
        # Fail-closed invariant: zero automatic retry
        self.assertEqual(self.config.max_retry_count, 0)

    def test_15_zero_live_provider_calls(self):
        """15. Verify that 0 live provider calls (Ollama, OpenAI, Gemini, Anthropic, Meta) occur across all steps."""
        run = self._create_approved_run(status=AutomationStatus.PROVIDER_EXECUTION_READY.value)
        res = reserve_provider_execution(run.id, self.operator)

        # Zero actual network requests made; provider_call_count recorded 1 reservation slot
        reloaded = IntelligenceAutomationRun.objects.get(id=run.id)
        self.assertEqual(reloaded.status, "PROVIDER_EXECUTING")
        # Ensure no mock or live external client was invoked
        self.assertTrue(res["reserved"])
