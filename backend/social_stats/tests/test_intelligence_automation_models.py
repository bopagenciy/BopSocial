"""
Unit Tests for BS-6A Intelligence Automation Models (Test Matrix AO).
Tests safe defaults, unique constraints, foreign keys, and status choices.
"""
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation.constants import (
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.identity import compute_execution_identity


class IntelligenceAutomationModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com")
        self.client_obj = Client.objects.create(
            name="Test Client",
            company="Test Client Co",
            email="test@client.com",
            is_active=True,
            timezone="America/New_York",
        )

    def test_config_safe_defaults(self):
        """IntelligenceAutomationConfig must default to safe values: disabled, no narrative, approval required."""
        config = IntelligenceAutomationConfig.objects.create(client=self.client_obj)

        self.assertFalse(config.enabled)
        self.assertFalse(config.generate_narrative)
        self.assertTrue(config.generate_report)
        self.assertTrue(config.require_operator_approval)
        self.assertEqual(config.provider_call_budget, 1)
        self.assertEqual(config.max_retry_count, 0)
        self.assertEqual(config.reporting_frequency, "MONTHLY")
        self.assertEqual(config.reporting_day, 1)
        self.assertEqual(config.reporting_hour, 6)
        self.assertEqual(config.lookback_days, 30)
        self.assertEqual(config.timezone, "America/New_York")
        self.assertEqual(config.max_data_staleness_hours, 24)
        self.assertIn("IntelligenceAutomationConfig", str(config))

    def test_run_model_creation_and_defaults(self):
        """IntelligenceAutomationRun defaults to PENDING status, ELIGIBILITY stage, and 0 retries/calls."""
        period_start = date(2026, 9, 1)
        period_end = date(2026, 9, 30)
        exec_id = compute_execution_identity(self.client_obj.id, period_start, period_end)

        run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period_start,
            period_end=period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=exec_id,
            trigger_type=AutomationTriggerType.MANUAL.value,
        )

        self.assertEqual(run.status, AutomationStatus.PENDING.value)
        self.assertEqual(run.current_stage, AutomationStage.ELIGIBILITY.value)
        self.assertEqual(run.provider_call_count, 0)
        self.assertEqual(run.retry_count, 0)
        self.assertEqual(run.fallback_count, 0)
        self.assertFalse(run.dry_run)
        self.assertIsNone(run.started_at)
        self.assertIsNone(run.finished_at)
        self.assertIsNone(run.error_code)
        self.assertEqual(run.error_message_safe, "")
        self.assertIn(f"Client #{self.client_obj.id}", str(run))

    def test_unique_active_run_constraint_enforced(self):
        """Database constraint must prevent two simultaneous active runs for same client, period, version."""
        period_start = date(2026, 9, 1)
        period_end = date(2026, 9, 30)
        exec_id = compute_execution_identity(self.client_obj.id, period_start, period_end)

        run1 = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period_start,
            period_end=period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=exec_id,
            status=AutomationStatus.RUNNING.value,
        )

        with self.assertRaises(IntegrityError):
            IntelligenceAutomationRun.objects.create(
                client=self.client_obj,
                period_start=period_start,
                period_end=period_end,
                pipeline_version=PIPELINE_VERSION,
                execution_identity=exec_id,
                status=AutomationStatus.RUNNING.value,
            )

    def test_completed_runs_allow_subsequent_runs(self):
        """Once a run is COMPLETED or BLOCKED, a new run record can be created for the same period."""
        period_start = date(2026, 9, 1)
        period_end = date(2026, 9, 30)
        exec_id = compute_execution_identity(self.client_obj.id, period_start, period_end)

        run1 = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period_start,
            period_end=period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=exec_id,
            status=AutomationStatus.COMPLETED.value,
        )

        # Another run can be created since run1 is COMPLETED (not active)
        run2 = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period_start,
            period_end=period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=exec_id,
            status=AutomationStatus.COMPLETED.value,
        )
        self.assertNotEqual(run1.id, run2.id)

    def test_different_period_or_client_allows_active_run(self):
        """Active runs for different periods or different clients do not collide."""
        period1_start = date(2026, 8, 1)
        period1_end = date(2026, 8, 31)
        period2_start = date(2026, 9, 1)
        period2_end = date(2026, 9, 30)

        run1 = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period1_start,
            period_end=period1_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=compute_execution_identity(self.client_obj.id, period1_start, period1_end),
            status=AutomationStatus.RUNNING.value,
        )

        # Different period on same client: Allowed
        run2 = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=period2_start,
            period_end=period2_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=compute_execution_identity(self.client_obj.id, period2_start, period2_end),
            status=AutomationStatus.RUNNING.value,
        )
        self.assertNotEqual(run1.id, run2.id)

        # Different client on same period: Allowed
        client2 = Client.objects.create(name="Client 2", company="Co 2", is_active=True)
        run3 = IntelligenceAutomationRun.objects.create(
            client=client2,
            period_start=period1_start,
            period_end=period1_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=compute_execution_identity(client2.id, period1_start, period1_end),
            status=AutomationStatus.RUNNING.value,
        )
        self.assertNotEqual(run1.id, run3.id)
