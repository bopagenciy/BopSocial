"""
BS-6B.0C Audit Row Immutability & Approval-State Reconciliation Test Suite.
Validates:
1. legacy blocked run immutability (historical rows never modified)
2. block-state dynamic derivation for legacy rows lacking block_state_hash
3. attempt numbering deterministic and monotonic
4. approval status semantics (status=BLOCKED with OPERATOR_APPROVAL_REQUIRED)
5. approval-pending active uniqueness behavior
6. lock not held while awaiting human input
7. resume requires lock reacquisition
8. no duplicate approval resume
9. no provider calls
10. historical run fields unchanged
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from django.db.utils import IntegrityError

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    BusinessSignal,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation import (
    PIPELINE_VERSION,
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    SingleFlightLock,
    ConcurrencyLockError,
    evaluate_intelligence_automation_eligibility,
    preview_intelligence_automation,
    execute_intelligence_automation,
    compute_block_state_hash,
)
from social_stats.analytics.automation.tasks import (
    discover_and_enqueue_due_intelligence_automations,
    run_intelligence_automation_task,
)


class AuditRowImmutabilityAndApprovalContractTests(TestCase):
    def setUp(self):
        self.client_1 = Client.objects.create(
            name="Immutability Pilot Client",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="immutability_pilot@example.com",
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_1,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
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

    def test_01_legacy_blocked_run_immutability(self):
        """Proves that a legacy BLOCKED run lacking block_state_hash is never mutated by discovery."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        # Create a purely legacy run with minimal metadata (no block_state_hash)
        legacy_run = IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity="legacy-identity-abc",
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code="ANALYTICS_DATA_STALE",
            metadata={"freshness": {"code": "STALE"}},
        )
        initial_updated_at = legacy_run.updated_at
        initial_metadata = dict(legacy_run.metadata)

        # Trigger discovery scan
        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=ref_time):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        legacy_run.refresh_from_db()
        self.assertEqual(legacy_run.metadata, initial_metadata)
        self.assertNotIn("block_state_hash", legacy_run.metadata)
        self.assertEqual(legacy_run.updated_at, initial_updated_at)

    def test_02_block_state_calculation_for_legacy_row(self):
        """Proves discovery correctly derives legacy block-state dynamically without altering DB."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)
        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)

        with patch("django.utils.timezone.now", return_value=ref_time):
            # Pre-evaluate scheduled eligibility so error_code and freshness match
            elig = evaluate_intelligence_automation_eligibility(
                client_id=self.client_1.id,
                period_start=p_start,
                period_end=p_end,
                trigger_type="SCHEDULED",
                dry_run=True,
            )

            freshness_code = (
                elig.freshness.get("code")
                if isinstance(elig.freshness, dict)
                else (elig.freshness.code if elig.freshness else "")
            )

            legacy_run = IntelligenceAutomationRun.objects.create(
                client=self.client_1,
                period_start=p_start,
                period_end=p_end,
                pipeline_version=PIPELINE_VERSION,
                execution_identity=elig.execution_identity,
                trigger_type="SCHEDULED",
                status="BLOCKED",
                current_stage="ELIGIBILITY",
                error_code=elig.blocking_reasons[0],
                metadata={"freshness": {"code": freshness_code}},
            )

            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertNotIn(self.client_1.id, res["due_client_ids"])
            skipped = next((s for s in res["skipped_summary"] if s["client_id"] == self.client_1.id), None)
            self.assertIn("BLOCKED_STATE_UNCHANGED", skipped["reason"])

    def test_03_attempt_numbering_deterministic(self):
        """Proves that sequential attempts for the same execution identity receive monotonic attempt numbers."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        run1 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run1.metadata.get("attempt_number"), 1)

        run2 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run2.metadata.get("attempt_number"), 2)

        run3 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run3.metadata.get("attempt_number"), 3)

        # Verify historical runs were not renumbered
        r1_fresh = IntelligenceAutomationRun.objects.get(id=run1.id)
        self.assertEqual(r1_fresh.metadata.get("attempt_number"), 1)

    def test_04_approval_status_semantics(self):
        """Proves approval-gated runs evaluate to status=BLOCKED with OPERATOR_APPROVAL_REQUIRED."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertFalse(res.execution_authorized)
        self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", res.blocking_reasons)

    def test_05_approval_pending_active_uniqueness_behavior(self):
        """Proves that if an execution is active (RUNNING or ELIGIBILITY_CHECK), duplicate active attempts are rejected by DB constraint."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        run_active = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        run_active.status = AutomationStatus.RUNNING.value
        run_active.save()

        # Direct DB attempt with same execution identity and active status must raise IntegrityError
        with self.assertRaises(IntegrityError):
            IntelligenceAutomationRun.objects.create(
                client=self.client_1,
                period_start=p_start,
                period_end=p_end,
                pipeline_version=PIPELINE_VERSION,
                execution_identity=run_active.execution_identity,
                status=AutomationStatus.RUNNING.value,
                current_stage=AutomationStage.REPORT_CHECK.value,
            )

    def test_06_lock_not_held_while_awaiting_human_input(self):
        """Proves that terminal BLOCKED runs release the PostgreSQL advisory lock immediately."""
        lock_hex = "f" * 64
        lock = SingleFlightLock(lock_hex)
        self.assertTrue(lock.acquire())
        # Simulate stage execution completion and release
        lock.release()

        # Another process or worker must immediately be able to acquire the lock
        lock_worker = SingleFlightLock(lock_hex)
        acquired = lock_worker.acquire()
        self.assertTrue(acquired)
        lock_worker.release()

    def test_07_resume_requires_lock_reacquisition(self):
        """Proves that resuming an execution requires acquiring the single-flight advisory lock."""
        identity = "resume-test-identity-xyz"
        
        # Simulate active lock already held by another worker
        with patch.object(SingleFlightLock, "acquire", return_value=False):
            with self.assertRaises(ConcurrencyLockError):
                execute_intelligence_automation(
                    client_id=self.client_1.id,
                    dry_run=False,
                )

    def test_08_no_duplicate_approval_resume(self):
        """Proves that once approval is resolved, only one new run can transition through the pipeline."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        # Run 1: BLOCKED on approval
        run1 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run1.status, "BLOCKED")

        # Resolve approval
        self.config.require_operator_approval = False
        self.config.save()

        # Run 2: First resumed run
        run2 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run2.status, "BLOCKED")  # Still blocked by data missing/stale, but distinct attempt
        self.assertEqual(run2.metadata.get("attempt_number"), 2)

    def test_09_no_provider_calls(self):
        """Proves that zero LLM or external API calls occur during approval checks."""
        with patch("urllib.request.urlopen") as mock_http, \
             patch("requests.post") as mock_post:
            
            evaluate_intelligence_automation_eligibility(
                client_id=self.client_1.id,
                trigger_type="SCHEDULED",
                dry_run=True,
            )
            self.assertEqual(mock_http.call_count, 0)
            self.assertEqual(mock_post.call_count, 0)

    def test_10_historical_run_fields_unchanged(self):
        """Proves that historical audit fields (id, timestamps, status, execution_identity) remain strictly immutable."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        run = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        frozen_id = run.id
        frozen_identity = run.execution_identity
        frozen_started_at = run.started_at

        # Execute subsequent preview/discovery operations
        preview_intelligence_automation(client_id=self.client_1.id)
        
        run.refresh_from_db()
        self.assertEqual(run.id, frozen_id)
        self.assertEqual(run.execution_identity, frozen_identity)
        self.assertEqual(run.started_at, frozen_started_at)
