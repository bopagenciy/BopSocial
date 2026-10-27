"""
Unit Tests for BS-6A Stage Failure Contracts and Provider Budget (Test Matrices AT & AU).
Tests fail-closed stage execution, downstream stage abortion, and provider call limits.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation.constants import (
    AutomationStage,
    AutomationStatus,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.locking import ConcurrencyLockError, SingleFlightLock
from social_stats.analytics.automation.orchestrator import execute_intelligence_automation


class IntelligenceAutomationOrchestrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="orch_user", email="orch@example.com")
        self.client_obj = Client.objects.create(
            name="Orch Client",
            company="Orch Co",
            is_active=True,
            timezone="America/New_York",
            requires_approval=False,
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client_obj,
            enabled=True,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=False,
            provider_call_budget=1,
            max_retry_count=0,
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            is_active=True,
            access_token="orch_token_123",
        )
        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 30)

        # Baseline snapshot & rollup & sync
        SocialMetricSnapshot.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=25000.0,
            bucket_period="DAY",
            bucket_timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
            dimensions_hash="snap_hash_orch",
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=250000.0,
            period="MONTH",
            period_start=self.period_start,
        )
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=1),
        )

    def test_eligibility_failure_aborts_pipeline_records_blocked_status(self):
        """When eligibility checks fail, status is set to BLOCKED and no stages run."""
        # Disable client to trigger eligibility failure
        self.client_obj.is_active = False
        self.client_obj.save()

        run = execute_intelligence_automation(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )

        self.assertEqual(run.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(run.current_stage, AutomationStage.ELIGIBILITY.value)
        self.assertEqual(run.error_code, "CLIENT_INACTIVE")
        self.assertIn("CLIENT_INACTIVE", run.error_message_safe)
        self.assertIsNotNone(run.finished_at)

    @patch("social_stats.analytics.automation.orchestrator.SingleFlightLock.acquire", return_value=False)
    def test_concurrency_lock_failure_raises_and_aborts(self, mock_acquire):
        """If a lock cannot be acquired (already held by another worker), execution raises ConcurrencyLockError."""
        with self.assertRaises(ConcurrencyLockError):
            execute_intelligence_automation(
                client_id=self.client_obj.id,
                period_start=self.period_start,
                period_end=self.period_end,
                dry_run=False,
            )

    def test_dry_run_creates_audit_record_without_provider_calls(self):
        """Dry-run execution creates an audit record marked dry_run=True, 0 provider calls, COMPLETED."""
        run = execute_intelligence_automation(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=True,
        )

        self.assertEqual(run.status, AutomationStatus.COMPLETED.value)
        self.assertEqual(run.current_stage, AutomationStage.COMPLETE.value)
        self.assertTrue(run.dry_run)
        self.assertEqual(run.provider_call_count, 0)
        self.assertEqual(run.retry_count, 0)
        self.assertEqual(run.fallback_count, 0)

    def test_provider_call_budget_zero_blocks_narrative_generation(self):
        """When provider_call_budget=0 and narrative is requested, eligibility engine blocks."""
        self.config.provider_call_budget = 0
        self.config.save()

        from social_stats.analytics.automation.eligibility import evaluate_intelligence_automation_eligibility
        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )

        self.assertFalse(elig.eligible)
        self.assertTrue(any("PROVIDER_CALL_BUDGET_EXHAUSTED" in r for r in elig.blocking_reasons))
