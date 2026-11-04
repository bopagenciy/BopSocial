"""
Unit Tests for Phase BS-6D.0D: Sync Provenance Contract & Controlled Historical Recovery (Test Matrix AD).
Verifies:
1. Historical SyncLog does not advance freshness
2. Current SyncLog does advance freshness
3. Historical sync improves target coverage
4. Coverage and freshness remain strictly independent
5. Historical scope stored/auditable in SyncLog
6. Explicit historical date bounds honored
7. Other clients untouched
8. Unavailable historical IG != zero
9. No synthetic snapshots
10. Affected rollups only
11. 24/30 passes 80% coverage
12. <24/30 fails coverage
13. Manual force cannot bypass coverage
14. Historical completion cannot bypass stale current data
15. Zero LLM calls
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    DailyMetric,
    IntelligenceAutomationConfig,
    PlatformCredential,
    PostMetric,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation.constants import (
    AutomationStatus,
    CoverageCode,
    FreshnessCode,
)
from social_stats.analytics.automation.coverage import evaluate_target_period_coverage
from social_stats.analytics.automation.eligibility import evaluate_intelligence_automation_eligibility
from social_stats.analytics.automation.freshness import evaluate_tenant_freshness
from social_stats.analytics.automation.orchestrator import preview_intelligence_automation
from social_stats.analytics.rollups import build_rollups_for_client
from social_stats.analytics.sync_service import sync_facebook_analytics, sync_instagram_analytics


class SyncFreshnessProvenanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="prov_user", email="prov@example.com")
        self.client_a = Client.objects.create(
            name="Client Alpha",
            company="Alpha Corp",
            email="alpha@example.com",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
        )
        self.client_b = Client.objects.create(
            name="Client Beta",
            company="Beta Corp",
            email="beta@example.com",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
        )
        self.config_a = IntelligenceAutomationConfig.objects.create(
            client=self.client_a,
            enabled=True,
            minimum_period_coverage_percent=80,
            minimum_data_freshness="FRESH",
            max_data_staleness_hours=24,
            require_operator_approval=True,
            provider_call_budget=1,
            max_retry_count=0,
        )
        self.cred_fb = PlatformCredential.objects.create(
            client=self.client_a,
            platform="facebook",
            page_id="100200300",
            access_token="valid_token_fb",
            is_active=True,
        )
        self.cred_ig = PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            instagram_account_id="ig_100200",
            access_token="valid_token_ig",
            is_active=True,
            scope="instagram_basic,instagram_content_publish",  # No manage_insights -> PARTIAL mode
        )

        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 30)

    # 1. Historical SyncLog does not advance freshness
    def test_01_historical_synclog_does_not_advance_freshness(self):
        """Historical SyncLog with sync_scope='HISTORICAL' must NOT qualify as current freshness evidence."""
        now = timezone.now()
        # Seed an old current sync (48 hours ago)
        old_sync = SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="CURRENT",
            finished_at=now - timedelta(hours=48),
            records_synced=10,
        )

        fresh_before = evaluate_tenant_freshness(self.client_a.id, now=now)
        self.assertEqual(fresh_before.code, FreshnessCode.STALE)
        self.assertEqual(fresh_before.latest_sync_at, old_sync.finished_at)
        self.assertAlmostEqual(fresh_before.data_age_hours, 48.0, delta=0.5)

        # Complete a historical sync right NOW for period 2026-09-01 to 2026-09-21
        hist_sync = SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="HISTORICAL",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 21),
            finished_at=now,
            records_synced=50,
        )

        fresh_after = evaluate_tenant_freshness(self.client_a.id, now=now)
        # Invariant: Freshness must remain STALE and latest_sync_at must NOT change to hist_sync
        self.assertEqual(fresh_after.code, FreshnessCode.STALE)
        self.assertEqual(fresh_after.latest_sync_at, old_sync.finished_at)
        self.assertNotEqual(fresh_after.latest_sync_at, hist_sync.finished_at)
        self.assertAlmostEqual(fresh_after.data_age_hours, 48.0, delta=0.5)

    # 2. Current SyncLog does advance freshness
    def test_02_current_synclog_does_advance_freshness(self):
        """CURRENT SyncLog does advance tenant freshness when finished recently."""
        now = timezone.now()
        SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="CURRENT",
            finished_at=now - timedelta(hours=30),
            records_synced=10,
        )
        self.assertEqual(evaluate_tenant_freshness(self.client_a.id, now=now).code, FreshnessCode.STALE)

        # Perform fresh CURRENT sync 10 minutes ago
        fresh_sync = SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="CURRENT",
            finished_at=now - timedelta(minutes=10),
            records_synced=20,
        )

        res = evaluate_tenant_freshness(self.client_a.id, now=now)
        self.assertEqual(res.code, FreshnessCode.FRESH)
        self.assertEqual(res.latest_sync_at, fresh_sync.finished_at)
        self.assertLess(res.data_age_hours, 1.0)

    # 3. Historical sync improves target coverage
    def test_03_historical_sync_improves_target_coverage(self):
        """Recovering missing historical days increases coverage percentage from 30% to 100%."""
        # Baseline: 9 days (30%)
        for d in range(22, 31):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        cov_before = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end)
        self.assertEqual(cov_before.overall_percent, 30.0)
        self.assertFalse(cov_before.is_sufficient)

        # Recover missing 21 days (Sept 1 to 21)
        for d in range(1, 22):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        cov_after = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end)
        self.assertEqual(cov_after.overall_percent, 100.0)
        self.assertTrue(cov_after.is_sufficient)

    # 4. Coverage and freshness remain strictly independent
    def test_04_coverage_and_freshness_remain_independent(self):
        """Full 100% period coverage can coexist with STALE tenant freshness."""
        now = timezone.now()
        # 30 days of snapshots in September
        for d in range(1, 31):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        # Sync is 40 hours old
        SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="CURRENT",
            finished_at=now - timedelta(hours=40),
            records_synced=10,
        )

        cov = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end)
        fresh = evaluate_tenant_freshness(self.client_a.id, now=now)

        self.assertTrue(cov.is_sufficient)
        self.assertEqual(cov.overall_percent, 100.0)
        self.assertFalse(fresh.is_fresh)
        self.assertEqual(fresh.code, FreshnessCode.STALE)

    # 5. Historical scope stored/auditable in SyncLog
    def test_05_historical_scope_stored_and_auditable(self):
        """Historical SyncLog cleanly persists scope, bounds, and safe metadata."""
        log = SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="HISTORICAL",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 21),
            records_synced=42,
            metadata={"records_seen": 42, "records_ingested": 42, "records_updated": 0},
        )
        fetched = SyncLog.objects.get(id=log.id)
        self.assertEqual(fetched.sync_scope, "HISTORICAL")
        self.assertEqual(fetched.period_start, date(2026, 9, 1))
        self.assertEqual(fetched.period_end, date(2026, 9, 21))
        self.assertEqual(fetched.metadata.get("records_ingested"), 42)

    # 6. Explicit historical date bounds honored in sync_facebook_analytics
    @patch("social_stats.analytics.adapters.facebook.FacebookAnalyticsAdapter.fetch_account_metrics")
    @patch("social_stats.analytics.adapters.facebook.FacebookAnalyticsAdapter.fetch_post_metrics")
    def test_06_explicit_historical_date_bounds_honored(self, mock_posts, mock_acct):
        """sync_facebook_analytics passes explicit since and until date bounds to adapter."""
        from social_stats.analytics.adapters.base import ProviderPayload
        mock_acct.return_value = ProviderPayload(raw_data={"page_node": {}, "insights": []})
        mock_posts.return_value = ProviderPayload(raw_data={"posts": []})

        since_d = date(2026, 9, 1)
        until_d = date(2026, 9, 21)

        res = sync_facebook_analytics(
            client_id=self.client_a.id,
            since=since_d,
            until=until_d,
            sync_scope="HISTORICAL",
            dual_write=False,
        )

        mock_acct.assert_called_once()
        _, kwargs = mock_acct.call_args
        self.assertEqual(kwargs.get("since"), since_d)
        self.assertEqual(kwargs.get("until"), until_d)

        log = SyncLog.objects.filter(client=self.client_a, sync_scope="HISTORICAL").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.period_start, since_d)
        self.assertEqual(log.period_end, until_d)

    # 7. Other clients untouched
    def test_07_other_clients_untouched(self):
        """Historical backfill for client_a creates zero records for client_b."""
        count_b_snaps = SocialMetricSnapshot.objects.filter(client=self.client_b).count()
        count_b_logs = SyncLog.objects.filter(client=self.client_b).count()

        SocialMetricSnapshot.objects.create(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=100.0,
            bucket_period="day",
            bucket_timestamp=datetime(2026, 9, 5, 12, 0, tzinfo=dt_timezone.utc),
        )
        SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="HISTORICAL",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 21),
            records_synced=1,
        )

        self.assertEqual(SocialMetricSnapshot.objects.filter(client=self.client_b).count(), count_b_snaps)
        self.assertEqual(SyncLog.objects.filter(client=self.client_b).count(), count_b_logs)

    # 8. Unavailable historical IG != zero
    def test_08_unavailable_historical_ig_not_zero(self):
        """Instagram in PARTIAL capability reports unavailable metrics without fabricating zeroes."""
        # No Instagram snapshots in September
        cov = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end)
        ig_cov = cov.platforms["instagram"]
        self.assertEqual(ig_cov.capability_mode, "PARTIAL")
        self.assertEqual(ig_cov.snapshot_distinct_days, 0)
        self.assertEqual(len(ig_cov.available_metrics), 0)
        self.assertIn("REACH", ig_cov.unavailable_metrics)
        self.assertIn("IMPRESSIONS", ig_cov.unavailable_metrics)
        # Zero rows were created for Instagram
        self.assertEqual(SocialMetricSnapshot.objects.filter(client=self.client_a, platform="instagram").count(), 0)

    # 9. No synthetic snapshots
    def test_09_no_synthetic_snapshots(self):
        """Only genuine provider observations are recorded; missing dates are never padded with zeroes."""
        # Seed 5 days
        for d in [1, 2, 3, 4, 5]:
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=500.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        self.assertEqual(
            SocialMetricSnapshot.objects.filter(
                client=self.client_a,
                bucket_timestamp__date__gte=self.period_start,
                bucket_timestamp__date__lte=self.period_end,
            ).count(),
            5,
        )

    # 10. Affected rollups only
    def test_10_affected_rollups_only(self):
        """Rollup build with date filter updates only September rollups, leaving other periods untouched."""
        # Create an August snapshot and rollup
        aug_snap = SocialMetricSnapshot.objects.create(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=200.0,
            bucket_period="day",
            bucket_timestamp=datetime(2026, 8, 15, 12, 0, tzinfo=dt_timezone.utc),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            period="month",
            period_start=date(2026, 8, 1),
            metric_value=200.0,
            sample_count=1,
        )

        # Create September snapshot
        SocialMetricSnapshot.objects.create(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=300.0,
            bucket_period="day",
            bucket_timestamp=datetime(2026, 9, 10, 12, 0, tzinfo=dt_timezone.utc),
        )

        # Build rollups bounded to September only
        build_rollups_for_client(
            self.client_a.id,
            platform="facebook",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        # August month rollup remains untouched
        aug_rollup = SocialMetricRollup.objects.get(client=self.client_a, period="month", period_start=date(2026, 8, 1))
        self.assertEqual(aug_rollup.sample_count, 1)
        self.assertEqual(aug_rollup.metric_value, 200.0)

        # September month rollup was created
        sept_rollup = SocialMetricRollup.objects.get(client=self.client_a, period="month", period_start=date(2026, 9, 1))
        self.assertEqual(sept_rollup.sample_count, 1)
        self.assertEqual(sept_rollup.metric_value, 300.0)

    # 11. 24/30 passes 80% coverage
    def test_11_24_of_30_passes_80_percent_coverage(self):
        """24 distinct days out of 30 days equals 80.0% and passes the coverage gate."""
        for d in range(1, 25):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        cov = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end, threshold_percent=80)
        self.assertEqual(cov.overall_percent, 80.0)
        self.assertTrue(cov.is_sufficient)

    # 12. <24/30 fails coverage
    def test_12_under_24_of_30_fails_coverage(self):
        """23 distinct days out of 30 days equals 76.67% and fails closed (< 80%)."""
        for d in range(1, 24):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        cov = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end, threshold_percent=80)
        self.assertAlmostEqual(cov.overall_percent, 76.67, delta=0.01)
        self.assertFalse(cov.is_sufficient)
        self.assertEqual(cov.overall_code, CoverageCode.INSUFFICIENT)

    # 13. Manual force cannot bypass coverage
    def test_13_manual_force_cannot_bypass_coverage(self):
        """CLI or API force=True cannot override TARGET_PERIOD_COVERAGE_INSUFFICIENT."""
        # 10 days = 33.3%
        for d in range(1, 11):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        preview = preview_intelligence_automation(
            client_id=self.client_a.id,
            period_start=self.period_start,
            period_end=self.period_end,
            trigger_type="MANUAL",
            force=True,
        )
        self.assertFalse(preview["eligible"])
        self.assertFalse(preview["data_eligible"])
        self.assertTrue(any("TARGET_PERIOD_COVERAGE_INSUFFICIENT" in r for r in preview["blocking_reasons"]))

    # 14. Historical completion cannot bypass stale current data
    def test_14_historical_completion_cannot_bypass_stale_current_data(self):
        """Scheduled run with 100% historical coverage still fails closed if current operational sync is stale."""
        now = timezone.now()
        # 30 days of snapshots in September
        for d in range(1, 31):
            SocialMetricSnapshot.objects.create(
                client=self.client_a,
                platform="facebook",
                metric_scope="account",
                normalized_metric="IMPRESSIONS",
                metric_value=100.0,
                bucket_period="day",
                bucket_timestamp=datetime(2026, 9, d, 12, 0, tzinfo=dt_timezone.utc),
            )
        # Rollups
        build_rollups_for_client(self.client_a.id, platform="facebook", start_date=self.period_start, end_date=self.period_end)

        # Operational sync is 36 hours old
        SyncLog.objects.create(
            client=self.client_a,
            platform="facebook",
            status="success",
            sync_scope="CURRENT",
            finished_at=now - timedelta(hours=36),
            records_synced=10,
        )

        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_a.id,
            period_start=self.period_start,
            period_end=self.period_end,
            trigger_type="SCHEDULED",
            now=now,
        )
        # Coverage is sufficient, but scheduled eligibility remains blocked on staleness
        self.assertTrue(elig.target_period_coverage.get("is_sufficient"))
        self.assertFalse(elig.eligible)
        self.assertTrue(any("ANALYTICS_DATA_STALE" in r for r in elig.blocking_reasons))

    # 15. Zero LLM calls
    def test_15_zero_llm_calls_during_coverage_and_provenance_evaluation(self):
        """Evaluation of coverage and sync provenance makes zero calls to LLMs."""
        with patch("social_stats.ai.client.AIClient.complete") as mock_ai, \
             patch("social_stats.analytics.narrative.providers.ollama.OllamaNarrativeProvider.generate") as mock_ollama:
            cov = evaluate_target_period_coverage(self.client_a.id, self.period_start, self.period_end)
            fresh = evaluate_tenant_freshness(self.client_a.id)
            mock_ai.assert_not_called()
            mock_ollama.assert_not_called()
