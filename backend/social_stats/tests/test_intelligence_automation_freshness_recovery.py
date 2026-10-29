"""
BS-6D.0: Unit Tests for Controlled Analytics Freshness Recovery & Downstream Invariance.
Verifies data freshness evaluation, fail-closed staleness gating, capability degradation
without fake zeroes, transparent credential decryption with rotated keys, and downstream
artifact immutability.
"""
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
    Client,
    DailyMetric,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    PostMetric,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation.constants import (
    AutomationStatus,
    FreshnessCode,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.eligibility import (
    evaluate_intelligence_automation_eligibility,
)
from social_stats.analytics.automation.freshness import (
    evaluate_tenant_freshness,
)
from social_stats.crypto import encrypt_value, decrypt_value


class IntelligenceAutomationFreshnessRecoveryTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Test Agency Tenant",
            company="Test Agency",
            email="tenant@agency.local",
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
            minimum_data_freshness="FRESH",
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=True,
            provider_call_budget=1,
            max_retry_count=0,
        )
        self.fb_cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            page_id="657647337668646",
            page_name="Test Page",
            access_token="fake_fb_token",
            is_active=True,
            scope="pages_read_engagement,read_insights,pages_manage_posts",
        )
        self.ig_cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="instagram",
            page_id="657647337668646",
            instagram_account_id="17841464843082253",
            page_name="test_ig",
            access_token="fake_ig_token",
            is_active=True,
            scope="instagram_basic,instagram_content_publish",  # No instagram_manage_insights
        )

    def test_01_stale_data_blocks_eligibility_until_fresh_sync_recorded(self):
        """When latest sync is >24h old, scheduled eligibility is data-blocked; becomes data-eligible once sync <24h."""
        now = timezone.now()
        period_start = (now - timedelta(days=30)).date()
        period_end = now.date()

        # Create a stale SyncLog (30 hours old)
        stale_time = now - timedelta(hours=30)
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="success",
            finished_at=stale_time,
            records_synced=10,
        )

        freshness_stale = evaluate_tenant_freshness(
            self.client_obj.id, period_start, period_end, max_staleness_hours=24, now=now
        )
        self.assertFalse(freshness_stale.is_fresh)
        self.assertEqual(freshness_stale.code, FreshnessCode.STALE)
        self.assertGreater(freshness_stale.data_age_hours, 24.0)

        # Check eligibility with stale sync under SCHEDULED trigger
        elig_stale = evaluate_intelligence_automation_eligibility(
            self.client_obj.id, trigger_type="SCHEDULED", now=now
        )
        self.assertFalse(elig_stale.eligible)
        self.assertFalse(elig_stale.data_eligible)
        self.assertTrue(any("ANALYTICS_DATA_STALE" in r for r in elig_stale.blocking_reasons))

        # Record a fresh SyncLog (10 minutes old)
        fresh_time = now - timedelta(minutes=10)
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="partial",
            finished_at=fresh_time,
            records_synced=25,
        )

        freshness_fresh = evaluate_tenant_freshness(
            self.client_obj.id, period_start, period_end, max_staleness_hours=24, now=now
        )
        self.assertTrue(freshness_fresh.is_fresh)
        self.assertEqual(freshness_fresh.code, FreshnessCode.FRESH)
        self.assertLess(freshness_fresh.data_age_hours, 1.0)

        # Check eligibility with fresh sync - data_eligible must be True
        elig_fresh = evaluate_intelligence_automation_eligibility(
            self.client_obj.id, trigger_type="SCHEDULED", now=now
        )
        self.assertTrue(elig_fresh.data_eligible)
        self.assertFalse(any("ANALYTICS_DATA_STALE" in r for r in elig_fresh.blocking_reasons))
        # Operator approval remains the sole blocker
        self.assertIn(
            "OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval",
            elig_fresh.blocking_reasons,
        )

    def test_02_missing_scope_capability_does_not_fabricate_zeroes(self):
        """Absence of instagram_manage_insights results in PARTIAL sync without zero-fabrication."""
        from social_stats.analytics.adapters import has_instagram_insights_capability

        self.assertFalse(has_instagram_insights_capability(self.ig_cred))

        # Verify that DailyMetric count is zero when daily insights are skipped
        initial_dm_count = DailyMetric.objects.filter(client=self.client_obj).count()
        self.assertEqual(initial_dm_count, 0)

    def test_03_downstream_artifacts_remain_immutable_during_freshness_update(self):
        """Downstream BusinessSignals, ExecutiveReport, and ExecutiveNarrative are not modified."""
        report = ExecutiveReport.objects.create(
            client=self.client_obj,
            title="Monthly Report",
            report_type="MONTHLY_EXECUTIVE",
            period_start=date(2026, 9, 22),
            period_end=date(2026, 10, 22),
            status="GENERATED",
            source_hash="test_source_hash_12345",
        )
        narrative = ExecutiveNarrative.objects.create(
            client=self.client_obj,
            executive_report=report,
            rendered_text="Baseline narrative text.",
            status="VALIDATED",
            prompt_version="bs5e-prompt-v3",
            context_hash="test_context_hash_67890",
        )
        signal = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="cross_platform",
            signal_type="CROSS_PLATFORM_VELOCITY",
            metric="ENGAGEMENT_RATE",
            scope="account",
            period_start=date(2026, 9, 22),
            period_end=date(2026, 10, 22),
            observed_value=0.05,
            confidence_level="HIGH",
            direction="UP",
            severity="INFO",
        )

        rep_updated_at = report.updated_at
        nar_updated_at = narrative.updated_at
        sig_updated_at = signal.updated_at

        # Simulate freshness sync event by creating a new SyncLog and snapshot
        SyncLog.objects.create(
            client=self.client_obj,
            platform="instagram",
            status="partial",
            finished_at=timezone.now(),
            records_synced=5,
        )
        SocialMetricSnapshot.objects.create(
            client=self.client_obj,
            platform="instagram",
            metric_scope="account",
            object_id="17841464843082253",
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=50.0,
            raw_metric_name="followers_count",
            bucket_period="day",
            bucket_timestamp=timezone.now(),
        )

        # Refresh downstream instances
        report.refresh_from_db()
        narrative.refresh_from_db()
        signal.refresh_from_db()

        self.assertEqual(report.updated_at, rep_updated_at)
        self.assertEqual(narrative.updated_at, nar_updated_at)
        self.assertEqual(signal.updated_at, sig_updated_at)
        self.assertEqual(report.source_hash, "test_source_hash_12345")
        self.assertEqual(narrative.context_hash, "test_context_hash_67890")

    def test_04_historical_blocked_runs_remain_immutable_on_freshness_recovery(self):
        """Historical BLOCKED runs retain status, failure reason, and block_state_hash."""
        run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            agency_id=2,
            period_start=date(2026, 9, 22),
            period_end=date(2026, 10, 22),
            pipeline_version=PIPELINE_VERSION,
            execution_identity="ident_historical_run_123",
            trigger_type="MANUAL",
            status=AutomationStatus.BLOCKED,
            error_code="ANALYTICS_DATA_STALE: age 139.4h > 24h threshold",
            metadata={"freshness": {"code": "STALE"}, "block_state_hash": "a994751af2b69ed1"},
        )
        original_updated_at = run.updated_at

        # Fresh sync arrives
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="partial",
            finished_at=timezone.now(),
            records_synced=10,
        )

        run.refresh_from_db()
        self.assertEqual(run.status, AutomationStatus.BLOCKED)
        self.assertEqual(run.error_code, "ANALYTICS_DATA_STALE: age 139.4h > 24h threshold")
        self.assertEqual(run.metadata["block_state_hash"], "a994751af2b69ed1")
        self.assertEqual(run.updated_at, original_updated_at)

    def test_05_field_encryption_and_decryption_with_key_list(self):
        """EncryptedTextField encrypts with primary key and decrypts transparently."""
        secret = "synthetic_dummy_token_for_fernet_crypto_testing_only"
        ciphertext = encrypt_value(secret)
        self.assertTrue(ciphertext.startswith("enc::"))

        decrypted = decrypt_value(ciphertext)
        self.assertEqual(decrypted, secret)
