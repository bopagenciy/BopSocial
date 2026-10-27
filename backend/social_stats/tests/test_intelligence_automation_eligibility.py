"""
Unit Tests for BS-6A Eligibility Engine (Test Matrix AQ).
Verifies all fail-closed blocking gates, warning generation, and eligible controlled fixtures.
"""
from datetime import date, datetime, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
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
from social_stats.analytics.automation.constants import (
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    FreshnessCode,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.eligibility import evaluate_intelligence_automation_eligibility
from social_stats.analytics.automation.identity import compute_execution_identity


class IntelligenceAutomationEligibilityTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Pilot Client",
            company="Pilot Agency",
            email="pilot@client.com",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client_obj,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            lookback_days=30,
            generate_report=True,
            generate_narrative=False,
            require_operator_approval=True,
            provider_call_budget=1,
            max_retry_count=0,
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            is_active=True,
            access_token="valid_test_token_12345",
        )
        # Establish valid period
        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 30)

        # Baseline snapshot & rollup
        SocialMetricSnapshot.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=5000.0,
            bucket_period="DAY",
            bucket_timestamp=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
            dimensions_hash="test_snap_hash_1",
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=50000.0,
            period="MONTH",
            period_start=self.period_start,
        )
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=2),
        )

    def test_eligible_controlled_fixture(self):
        """A properly configured tenant with fresh data, credentials, and valid period is eligible."""
        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
            trigger_type="MANUAL",
        )

        self.assertTrue(result.eligible)
        self.assertEqual(len(result.blocking_reasons), 0)
        self.assertEqual(result.freshness["code"], FreshnessCode.FRESH.value)
        self.assertEqual(result.existing_artifacts["snapshots_count"], 1)
        self.assertEqual(result.existing_artifacts["rollups_count"], 1)

    def test_blocked_client_not_found(self):
        """Non-existent client fails closed immediately."""
        result = evaluate_intelligence_automation_eligibility(
            client_id=999999,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertFalse(result.eligible)
        self.assertIn("CLIENT_NOT_FOUND", result.blocking_reasons)

    def test_blocked_client_inactive(self):
        """Inactive client fails closed."""
        self.client_obj.is_active = False
        self.client_obj.save()

        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertFalse(result.eligible)
        self.assertIn("CLIENT_INACTIVE", result.blocking_reasons)

    def test_blocked_disabled_config_on_scheduled_trigger(self):
        """Scheduled trigger blocks if config is disabled."""
        self.config.enabled = False
        self.config.save()

        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
            trigger_type="SCHEDULED",
        )
        self.assertFalse(result.eligible)
        self.assertIn("AUTOMATION_CONFIG_DISABLED", result.blocking_reasons)

    def test_blocked_missing_provider_credentials(self):
        """Tenant with no active platform credentials fails closed."""
        self.cred.delete()

        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertFalse(result.eligible)
        self.assertTrue(any("PROVIDER_DISCONNECTED" in r for r in result.blocking_reasons))

    def test_blocked_duplicate_active_run(self):
        """If an active execution is already running for the same period, fail closed."""
        exec_id = compute_execution_identity(self.client_obj.id, self.period_start, self.period_end)
        IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=exec_id,
            status=AutomationStatus.RUNNING.value,
        )

        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertFalse(result.eligible)
        self.assertTrue(any("DUPLICATE_ACTIVE_RUN_EXISTS" in r for r in result.blocking_reasons))

    def test_blocked_invalid_period_boundaries(self):
        """period_start >= period_end fails closed."""
        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 9, 1),
        )
        self.assertFalse(result.eligible)
        self.assertIn("INVALID_PERIOD_START_GTE_END", result.blocking_reasons)

    def test_blocked_period_in_future(self):
        """Reporting period ending in future fails closed."""
        future_end = date.today() + timedelta(days=10)
        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=date.today(),
            period_end=future_end,
        )
        self.assertFalse(result.eligible)
        self.assertIn("PERIOD_END_IN_FUTURE", result.blocking_reasons)

    def test_approval_boundary_blocks_unauthorized_narrative_generation(self):
        """If requires_approval is True and generate_narrative is requested, blocks automated execution."""
        self.config.generate_narrative = True
        self.config.require_operator_approval = True
        self.config.save()

        result = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
            dry_run=False,
        )
        self.assertFalse(result.eligible)
        self.assertTrue(any("OPERATOR_APPROVAL_REQUIRED" in r for r in result.blocking_reasons))
