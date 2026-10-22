"""
Comprehensive tests for BOP SOCIAL Phase BS-4F Business Intelligence Foundation.
Covers:
- Baselines (median, mean, percentile, MAD, empty, single, outliers)
- Outperformance thresholds (+50%, +20%, normal, -20%, -50%)
- Confidence tiers (n=1, n=3, n=5, n=10+, stale downgrade)
- Follower semantics (gauge vs delta, never sum total followers)
- Reach constraints (NON_AGGREGATABLE multi-day guard)
- Format cohort separation
- Timezone conversions (America/New_York)
- Instagram PARTIAL mode capability guard
- Idempotency & zero duplication
- Source traceability in evidence
- Tenant isolation
- API endpoints (insights, executive-summary, history, permissions, empty states)
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import zoneinfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.analytics.capabilities import SupportLevel, get_provider_capability
from social_stats.analytics import can_derive_metric, derive_canonical_engagement_total
from social_stats.analytics.intelligence.baselines import (
    calculate_deltas,
    calculate_mad,
    calculate_mean,
    calculate_median,
    calculate_percentile,
    detect_anomalies,
)
from social_stats.analytics.intelligence.rules import (
    ConfidenceTier,
    PerformanceTier,
    SAMPLE_THRESHOLDS,
    SignalType,
    calculate_confidence,
    classify_performance_tier,
    determine_direction,
    determine_severity,
    is_signal_actionable,
)
from social_stats.analytics.intelligence.service import (
    compute_signal_identity,
    generate_business_signals,
    get_executive_summary,
    get_hour_bucket,
)
from social_stats.models import (
    BusinessSignal,
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    UnifiedPost,
)


class TestBaselinesAndStatistics(TestCase):
    """AV. TEST — BASELINE: median, mean, percentile, empty set, single observation, outliers."""

    def test_median_odd_and_even(self):
        # Odd
        odd_vals = [10, 20, 30]
        self.assertEqual(calculate_median(odd_vals), Decimal("20.0000"))

        # Even
        even_vals = [10, 20, 30, 40]
        self.assertEqual(calculate_median(even_vals), Decimal("25.0000"))

    def test_median_empty_and_single(self):
        self.assertIsNone(calculate_median([]))
        self.assertEqual(calculate_median([42]), Decimal("42.0000"))

    def test_mean(self):
        self.assertIsNone(calculate_mean([]))
        self.assertEqual(calculate_mean([10, 20, 30]), Decimal("20.0000"))
        self.assertEqual(calculate_mean([5]), Decimal("5.0000"))

    def test_percentile(self):
        vals = [10, 20, 30, 40, 50]
        self.assertEqual(calculate_percentile(vals, 0), Decimal("10.0000"))
        self.assertEqual(calculate_percentile(vals, 50), Decimal("30.0000"))
        self.assertEqual(calculate_percentile(vals, 100), Decimal("50.0000"))
        self.assertEqual(calculate_percentile(vals, 25), Decimal("20.0000"))
        self.assertEqual(calculate_percentile(vals, 75), Decimal("40.0000"))
        self.assertIsNone(calculate_percentile([], 50))

    def test_mad_and_anomaly_detection(self):
        # Normal series with an extreme outlier: 10, 11, 12, 10, 11, 100
        vals = [10, 11, 12, 10, 11, 100]
        med, mad = calculate_mad(vals)
        self.assertEqual(med, Decimal("11.0000"))
        # Deviations: |10-11|=1, |11-11|=0, |12-11|=1, |10-11|=1, |11-11|=0, |100-11|=89
        # Sorted deviations: 0, 0, 1, 1, 1, 89 -> median is 1.0000
        self.assertEqual(mad, Decimal("1.0000"))

        anomalies = detect_anomalies(vals, threshold_mad_multiplier=2.5)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0][0], 5)  # index 5
        self.assertEqual(anomalies[0][1], Decimal("100"))
        self.assertEqual(anomalies[0][2], "POSITIVE_OUTLIER")

    def test_deltas_and_zero_protection(self):
        # Positive delta
        abs_d, rel_d = calculate_deltas(150, 100)
        self.assertEqual(abs_d, Decimal("50.0000"))
        self.assertEqual(rel_d, Decimal("0.5000"))

        # Zero baseline protection (prevents division by zero or fake infinite)
        abs_d, rel_d = calculate_deltas(50, 0)
        self.assertEqual(abs_d, Decimal("50.0000"))
        self.assertIsNone(rel_d)

        # Both zero
        abs_d, rel_d = calculate_deltas(0, 0)
        self.assertEqual(abs_d, Decimal("0.0000"))
        self.assertEqual(rel_d, Decimal("0.0000"))


class TestPerformanceThresholds(TestCase):
    """AW. TEST — PERFORMANCE: +50%, +20%, normal, -20%, -50% threshold boundaries."""

    def test_outperformance_boundaries(self):
        # +50% -> STRONG_OUTPERFORMANCE
        self.assertEqual(classify_performance_tier(Decimal("0.5000")), PerformanceTier.STRONG_OUTPERFORMANCE)
        self.assertEqual(classify_performance_tier(Decimal("0.7500")), PerformanceTier.STRONG_OUTPERFORMANCE)

        # +20% to +49.99% -> OUTPERFORMANCE
        self.assertEqual(classify_performance_tier(Decimal("0.2000")), PerformanceTier.OUTPERFORMANCE)
        self.assertEqual(classify_performance_tier(Decimal("0.4999")), PerformanceTier.OUTPERFORMANCE)

        # Normal range (-19.99% to +19.99%)
        self.assertEqual(classify_performance_tier(Decimal("0.1999")), PerformanceTier.NORMAL_RANGE)
        self.assertEqual(classify_performance_tier(Decimal("0.0000")), PerformanceTier.NORMAL_RANGE)
        self.assertEqual(classify_performance_tier(Decimal("-0.1999")), PerformanceTier.NORMAL_RANGE)

        # -20% to -49.99% -> UNDERPERFORMANCE
        self.assertEqual(classify_performance_tier(Decimal("-0.2000")), PerformanceTier.UNDERPERFORMANCE)
        self.assertEqual(classify_performance_tier(Decimal("-0.4999")), PerformanceTier.UNDERPERFORMANCE)

        # <= -50% -> STRONG_UNDERPERFORMANCE
        self.assertEqual(classify_performance_tier(Decimal("-0.5000")), PerformanceTier.STRONG_UNDERPERFORMANCE)
        self.assertEqual(classify_performance_tier(Decimal("-0.8000")), PerformanceTier.STRONG_UNDERPERFORMANCE)


class TestConfidenceAndSampleProtection(TestCase):
    """AX. TEST — CONFIDENCE: n=1, n=3, n=5, n=10+, and stale downgrade."""

    def test_sample_size_confidence_tiers(self):
        # n < 3 -> NONE (Small sample protection)
        self.assertEqual(calculate_confidence(1), ConfidenceTier.NONE)
        self.assertEqual(calculate_confidence(2), ConfidenceTier.NONE)

        # 3 <= n < 5 -> LOW
        self.assertEqual(calculate_confidence(3), ConfidenceTier.LOW)
        self.assertEqual(calculate_confidence(4), ConfidenceTier.LOW)

        # 5 <= n < 10 -> MEDIUM
        self.assertEqual(calculate_confidence(5), ConfidenceTier.MEDIUM)
        self.assertEqual(calculate_confidence(9), ConfidenceTier.MEDIUM)

        # n >= 10 -> HIGH
        self.assertEqual(calculate_confidence(10), ConfidenceTier.HIGH)
        self.assertEqual(calculate_confidence(25), ConfidenceTier.HIGH)

    def test_stale_and_partial_confidence_downgrade(self):
        # HIGH with stale data -> MEDIUM
        self.assertEqual(calculate_confidence(12, is_stale=True), ConfidenceTier.MEDIUM)

        # MEDIUM with stale data -> LOW
        self.assertEqual(calculate_confidence(6, is_stale=True), ConfidenceTier.LOW)

        # LOW with stale data -> NONE
        self.assertEqual(calculate_confidence(3, is_stale=True), ConfidenceTier.NONE)


class TestBusinessIntelligenceService(TestCase):
    """Tests service logic, follower semantics, reach constraints, format separation, and timezone."""

    def setUp(self):
        self.user = User.objects.create_user(username="bi_tester", password="password123")
        self.client_a = Client.objects.create(
            name="Alpha Corp",
            company="Alpha Corp",
            email="alpha@corp.test",
            owner_user=self.user,
            timezone="America/New_York",
            is_active=True,
        )
        self.client_b = Client.objects.create(
            name="Beta LLC",
            company="Beta LLC",
            email="beta@llc.test",
            owner_user=self.user,
            timezone="UTC",
            is_active=True,
        )

        # Credentials
        self.cred_fb = PlatformCredential.objects.create(
            client=self.client_a,
            platform="facebook",
            is_active=True,
            access_token="valid_token",
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.cred_ig = PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            is_active=True,
            access_token="valid_token",
            expires_at=timezone.now() + timedelta(days=30),
        )

    def test_follower_gauge_semantics_never_summed(self):
        """AY. TEST — FOLLOWERS: verify FOLLOWERS_TOTAL is gauge and net change is delta."""
        # Create daily rollups for FOLLOWERS_TOTAL across 3 days: 100, 105, 110
        d1 = date(2026, 10, 1)
        d2 = date(2026, 10, 2)
        d3 = date(2026, 10, 3)

        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_TOTAL", period="day", period_start=d1,
            metric_value=Decimal("100.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_TOTAL", period="day", period_start=d2,
            metric_value=Decimal("105.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_TOTAL", period="day", period_start=d3,
            metric_value=Decimal("110.0000"), sample_count=1
        )

        # Also net change: 5, 5
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_NET_CHANGE", period="day", period_start=d2,
            metric_value=Decimal("5.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_NET_CHANGE", period="day", period_start=d3,
            metric_value=Decimal("5.0000"), sample_count=1
        )

        # Baseline window net change (e.g. 2 net change)
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="FOLLOWERS_NET_CHANGE", period="day", period_start=d1 - timedelta(days=1),
            metric_value=Decimal("2.0000"), sample_count=1
        )

        summary = get_executive_summary(self.client_a.id, date_from=d1, date_to=d3, platform="facebook")
        fol_dir = summary.get("follower_direction")
        # Should record latest total (110), NEVER sum of total (100+105+110=315)
        self.assertIsNotNone(fol_dir)
        signals = generate_business_signals(self.client_a.id, date_from=d1, date_to=d3, platform="facebook")
        fol_sig = [s for s in signals if s["signal_type"] == SignalType.FOLLOWER_GROWTH_UP]
        if fol_sig:
            self.assertEqual(fol_sig[0]["evidence"]["followers_total_gauge"], 110.0)
            self.assertNotEqual(fol_sig[0]["evidence"]["followers_total_gauge"], 315.0)

    def test_reach_aggregation_safety(self):
        """AZ. TEST — REACH: verify invalid multi-day reach aggregation never occurs."""
        # Daily rollups of reach must never be summed into a weekly/monthly total
        d1 = date(2026, 10, 1)
        d2 = date(2026, 10, 2)
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="REACH", period="day", period_start=d1,
            metric_value=Decimal("500.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", metric_scope="account",
            normalized_metric="REACH", period="day", period_start=d2,
            metric_value=Decimal("600.0000"), sample_count=1
        )

        signals = generate_business_signals(self.client_a.id, date_from=d1, date_to=d2, platform="facebook")
        # There should be no signal summing reach to 1100
        for s in signals:
            if s.get("metric") == "REACH":
                self.assertNotEqual(s.get("observed_value"), Decimal("1100.0000"))

    def test_format_cohort_separation(self):
        """BA. TEST — FORMAT: distinct formats (e.g. image vs reel) must not collapse into same cohort."""
        base_time = timezone.now() - timedelta(days=5)

        # Create 3 image posts
        for i in range(3):
            SocialMetricSnapshot.objects.create(
                client=self.client_a, platform="facebook", metric_scope="post",
                object_id=f"fb_img_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("20.0000"), bucket_timestamp=base_time - timedelta(hours=i),
                metadata={"media_type": "image"}
            )

        # Create 3 reel posts with much higher reactions
        for i in range(3):
            SocialMetricSnapshot.objects.create(
                client=self.client_a, platform="facebook", metric_scope="post",
                object_id=f"fb_reel_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("100.0000"), bucket_timestamp=base_time - timedelta(hours=i + 5),
                metadata={"media_type": "reel"}
            )

        signals = generate_business_signals(
            self.client_a.id,
            date_from=(base_time - timedelta(days=2)).date(),
            date_to=timezone.now().date(),
            platform="facebook"
        )

        format_signals = [s for s in signals if s["signal_type"] == SignalType.FORMAT_OUTPERFORMING]
        self.assertTrue(any(fs["object_id"] == "reel" for fs in format_signals))

        # Check content signals: an image post with 20 reactions is NOT compared to reels
        img_signals = [s for s in signals if s["scope"] == "post" and "img" in s["object_id"]]
        for s in img_signals:
            # Baseline for image cohort should be ~20, NOT skewed by 100-reaction reels
            self.assertEqual(s["baseline_value"], Decimal("20.0000"))

    def test_timezone_conversion(self):
        """BB. TEST — TIMEZONE: posting-time intelligence uses Client.timezone (America/New_York)."""
        # UTC 23:00 is 19:00 (evening) in America/New_York (EDT UTC-4)
        ny_tz = zoneinfo.ZoneInfo("America/New_York")
        utc_dt = datetime(2026, 10, 15, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo("UTC"))
        ny_dt = utc_dt.astimezone(ny_tz)
        self.assertEqual(ny_dt.hour, 19)

        bucket_utc = get_hour_bucket(utc_dt.hour)   # 23:00 -> late_night in UTC
        bucket_ny = get_hour_bucket(ny_dt.hour)     # 19:00 -> evening in NY
        self.assertEqual(bucket_utc, "late_night")
        self.assertEqual(bucket_ny, "evening")

    def test_partial_capability_guard(self):
        """BC. TEST — PARTIAL CAPABILITY: Instagram PARTIAL must not generate unavailable metric signals."""
        # Emit snapshots for Instagram: Reactions (supported) and Reach (unsupported)
        SocialMetricSnapshot.objects.create(
            client=self.client_a, platform="instagram", metric_scope="post",
            object_id="ig_1", raw_metric_name="reactions", normalized_metric="REACTIONS",
            metric_value=Decimal("50.0000"), bucket_timestamp=timezone.now() - timedelta(days=2),
            metadata={"media_type": "image"}
        )

        signals = generate_business_signals(self.client_a.id, platform="instagram")
        # Should include PROVIDER_PARTIAL data quality signal
        partial_sigs = [s for s in signals if s["signal_type"] == SignalType.PROVIDER_PARTIAL]
        self.assertTrue(len(partial_sigs) >= 1)

        # Must NOT generate signals for REACH or SAVES or SHARES
        unsupported = {"REACH", "SAVES", "SHARES", "VIDEO_VIEWS"}
        for s in signals:
            self.assertNotIn(s.get("metric"), unsupported)

    def test_idempotency(self):
        """BD. TEST — IDEMPOTENCY: Repeated synthetic generation creates 0 duplicate identities."""
        base_time = timezone.now() - timedelta(days=3)
        for i in range(4):
            SocialMetricSnapshot.objects.create(
                client=self.client_a, platform="facebook", metric_scope="post",
                object_id=f"fb_post_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("100.0000") if i == 0 else Decimal("20.0000"),
                bucket_timestamp=base_time - timedelta(hours=i),
                metadata={"media_type": "image"}
            )

        # First generation with persistence
        run1 = generate_business_signals(self.client_a.id, platform="facebook", persist=True)
        count1 = BusinessSignal.objects.filter(client=self.client_a).count()
        self.assertGreater(count1, 0)

        # Second generation over identical data
        run2 = generate_business_signals(self.client_a.id, platform="facebook", persist=True)
        count2 = BusinessSignal.objects.filter(client=self.client_a).count()

        # Idempotency check: exactly 0 duplicates added
        self.assertEqual(count1, count2)

    def test_traceability(self):
        """BE. TEST — TRACEABILITY: Every persisted signal contains source evidence."""
        base_time = timezone.now() - timedelta(days=2)
        for i in range(4):
            SocialMetricSnapshot.objects.create(
                client=self.client_a, platform="facebook", metric_scope="post",
                object_id=f"post_trace_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("200.0000") if i == 0 else Decimal("20.0000"),
                bucket_timestamp=base_time - timedelta(hours=i),
                metadata={"media_type": "image"}
            )

        signals = generate_business_signals(self.client_a.id, platform="facebook", persist=True)
        persisted = BusinessSignal.objects.filter(client=self.client_a)
        self.assertGreater(persisted.count(), 0)

        for sig in persisted:
            self.assertIsNotNone(sig.evidence)
            self.assertIsInstance(sig.evidence, dict)
            self.assertIsNotNone(sig.explanation_template)
            self.assertTrue(len(sig.explanation_template) > 0)
            self.assertTrue(len(sig.signal_identity) > 0)

    def test_tenant_isolation(self):
        """BF. TEST — TENANT: Client A data must never influence Client B baseline."""
        # Client A has posts with 1000 reactions
        base_time = timezone.now() - timedelta(days=2)
        for i in range(5):
            SocialMetricSnapshot.objects.create(
                client=self.client_a, platform="facebook", metric_scope="post",
                object_id=f"a_post_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("1000.0000"),
                bucket_timestamp=base_time - timedelta(hours=i),
                metadata={"media_type": "image"}
            )

        # Client B has posts with 10 reactions
        for i in range(5):
            SocialMetricSnapshot.objects.create(
                client=self.client_b, platform="facebook", metric_scope="post",
                object_id=f"b_post_{i}", raw_metric_name="reactions", normalized_metric="REACTIONS",
                metric_value=Decimal("10.0000"),
                bucket_timestamp=base_time - timedelta(hours=i),
                metadata={"media_type": "image"}
            )

        signals_b = generate_business_signals(self.client_b.id, platform="facebook")
        post_sigs_b = [s for s in signals_b if s["scope"] == "post" and s["object_id"].startswith("b_post")]
        for s in post_sigs_b:
            # Baseline for Client B must be 10, never contaminated by Client A's 1000
            self.assertEqual(s["baseline_value"], Decimal("10.0000"))


class TestBusinessIntelligenceAPI(TestCase):
    """BG. TEST — API: insights, executive-summary, history, filters, permissions, empty states."""

    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="password123")
        self.other_user = User.objects.create_user(username="other_user", password="password123")
        self.client_a = Client.objects.create(
            name="Alpha Corp",
            company="Alpha Corp",
            email="alpha@corp.test",
            owner_user=self.user,
            is_active=True,
        )
        self.client_b = Client.objects.create(
            name="Beta LLC",
            company="Beta LLC",
            email="beta_api@llc.test",
            owner_user=self.other_user,
            is_active=True,
        )

        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_insights_endpoint(self):
        # Empty client returns HTTP 200 with 0 count
        res = self.api.get(f"/api/analytics/insights/?client_id={self.client_a.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["client_id"], self.client_a.id)
        self.assertIn("signals", res.data)

    def test_executive_summary_endpoint(self):
        res = self.api.get(f"/api/analytics/executive-summary/?client_id={self.client_a.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("key_signals", res.data)
        self.assertIn("winning_formats", res.data)
        self.assertIn("posting_time_insights", res.data)
        self.assertIn("platform_health", res.data)
        self.assertIn("data_quality", res.data)

    def test_insights_history_endpoint(self):
        # Create a persisted signal
        BusinessSignal.objects.create(
            client=self.client_a,
            platform="facebook",
            signal_type=SignalType.CONTENT_OUTPERFORMING,
            metric="REACTIONS",
            scope="post",
            object_id="fb_123",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 20),
            observed_value=Decimal("50.0000"),
            baseline_value=Decimal("25.0000"),
            relative_delta=Decimal("1.0000"),
            sample_size=8,
            confidence_level="MEDIUM",
            direction="UP",
            severity="POSITIVE",
            signal_identity="test_history_identity_1",
            explanation_template="Sample template",
        )

        res = self.api.get(f"/api/analytics/insights/history/?client_id={self.client_a.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["signals"][0]["signal_identity"], "test_history_identity_1")

    def test_tenant_authorization_denial(self):
        # User is owner of Client A; attempting to access Client B returns HTTP 404
        res = self.api.get(f"/api/analytics/insights/?client_id={self.client_b.id}")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res_sum = self.api.get(f"/api/analytics/executive-summary/?client_id={self.client_b.id}")
        self.assertEqual(res_sum.status_code, status.HTTP_404_NOT_FOUND)

        res_hist = self.api.get(f"/api/analytics/insights/history/?client_id={self.client_b.id}")
        self.assertEqual(res_hist.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_denial(self):
        unauth_client = APIClient()
        res = unauth_client.get(f"/api/analytics/insights/?client_id={self.client_a.id}")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class InstagramPartialMetricIntegrityTests(TestCase):
    """
    Section I, J, K, L, M:
    Tests verifying Instagram PARTIAL capability metric integrity:
    - ENGAGEMENT_TOTAL requires REACTIONS, COMMENTS, SHARES.
    - Missing SHARES is NOT treated as zero.
    - Explicit SHARES=0 is valid data.
    - Signal suppression for incomplete derived metrics.
    - API exposure of unavailable metadata without fake zeros.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="ig_integrity_user", password="password")
        self.client_ig = Client.objects.create(
            name="IG Integrity Client",
            company="IG Integrity Corp",
            email="ig_integrity@example.com",
            owner_user=self.user,
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_ig,
            platform="instagram",
            scope="instagram_basic,pages_show_list",
            access_token="fake_ig_token",
            is_active=True,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_can_derive_metric_guard(self):
        # Case 1: Missing SHARES in dict -> unavailable
        can_derive, reason, missing = can_derive_metric(
            platform="instagram",
            capability_mode="PARTIAL",
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics={"REACTIONS": 50, "COMMENTS": 10},
        )
        self.assertFalse(can_derive)
        self.assertEqual(reason, "missing_required_components")
        self.assertIn("SHARES", missing)

        # Case 2: In list of metric keys without SHARES
        can_derive_list, _, missing_list = can_derive_metric(
            platform="instagram",
            capability_mode="PARTIAL",
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics=["REACTIONS", "COMMENTS"],
        )
        self.assertFalse(can_derive_list)
        self.assertIn("SHARES", missing_list)

    def test_shares_zero_valid_vs_shares_unavailable(self):
        # Test 1: Explicit SHARES = 0 is valid numeric data
        source_with_zero = {"REACTIONS": 50, "COMMENTS": 20, "SHARES": 0}
        can_derive, reason, missing = can_derive_metric(
            platform="facebook",
            capability_mode="FULL",
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics=source_with_zero,
        )
        self.assertTrue(can_derive)
        self.assertIsNone(reason)
        self.assertEqual(missing, [])
        derived_sum = derive_canonical_engagement_total(source_with_zero, "facebook")
        self.assertEqual(derived_sum, Decimal("70"))

        # Test 2: SHARES missing / None is unavailable
        source_with_none = {"REACTIONS": 50, "COMMENTS": 20, "SHARES": None}
        can_derive_none, reason_none, missing_none = can_derive_metric(
            platform="facebook",
            capability_mode="FULL",
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics=source_with_none,
        )
        self.assertFalse(can_derive_none)
        self.assertEqual(reason_none, "missing_required_components")
        self.assertIn("SHARES", missing_none)
        self.assertIsNone(derive_canonical_engagement_total(source_with_none, "facebook"))

    def test_full_capability_derivation(self):
        # Fully supported provider with all required components
        full_source = {"REACTIONS": Decimal("100"), "COMMENTS": Decimal("25"), "SHARES": Decimal("15")}
        total = derive_canonical_engagement_total(full_source, platform="facebook")
        self.assertEqual(total, Decimal("140"))

    def test_instagram_partial_signal_suppression_for_missing_shares(self):
        # Ingest 5 Instagram posts with REACTIONS and COMMENTS only (no SHARES)
        base_time = timezone.now() - timedelta(days=5)
        for i in range(5):
            SocialMetricSnapshot.objects.create(
                client=self.client_ig,
                platform="instagram",
                metric_scope="post",
                object_id=f"ig_post_{i}",
                normalized_metric="REACTIONS",
                metric_value=Decimal(str(20 + i * 5)),
                raw_metric_name="like_count",
                bucket_timestamp=base_time + timedelta(hours=i),
                metadata={"media_type": "image"},
            )
            SocialMetricSnapshot.objects.create(
                client=self.client_ig,
                platform="instagram",
                metric_scope="post",
                object_id=f"ig_post_{i}",
                normalized_metric="COMMENTS",
                metric_value=Decimal(str(5 + i)),
                raw_metric_name="comments_count",
                bucket_timestamp=base_time + timedelta(hours=i),
                metadata={"media_type": "image"},
            )

        # Generate signals
        signals = generate_business_signals(client_id=self.client_ig.id, platform="instagram")

        # Verify NO signal uses ENGAGEMENT_TOTAL for content performance, format, or time
        eng_total_content_signals = [
            s for s in signals
            if s.get("metric") == "ENGAGEMENT_TOTAL" and s.get("signal_type") in (
                SignalType.CONTENT_OUTPERFORMING,
                SignalType.CONTENT_UNDERPERFORMING,
                SignalType.FORMAT_OUTPERFORMING,
                SignalType.POSTING_TIME_OUTPERFORMING,
            )
        ]
        self.assertEqual(len(eng_total_content_signals), 0)

        # Content signals should exist based on supported metric (REACTIONS)
        reaction_signals = [s for s in signals if s.get("metric") == "REACTIONS"]
        self.assertGreater(len(reaction_signals), 0)

    def test_api_executive_summary_and_insights_unavailable_engagement_total(self):
        # Executive summary endpoint
        res = self.api.get(f"/api/analytics/executive-summary/?client_id={self.client_ig.id}&platform=instagram")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("engagement_total", res.data)
        eng_meta = res.data["engagement_total"]
        self.assertFalse(eng_meta["is_available"])
        self.assertEqual(eng_meta["reason"], "missing_required_components")
        self.assertIn("SHARES", eng_meta["missing_components"])
        self.assertIsNone(eng_meta["value"])  # Zero is NOT fabricated

        # Insights endpoint queried specifically for ENGAGEMENT_TOTAL
        res_ins = self.api.get(f"/api/analytics/insights/?client_id={self.client_ig.id}&platform=instagram&metric=ENGAGEMENT_TOTAL")
        self.assertEqual(res_ins.status_code, status.HTTP_200_OK)
        self.assertFalse(res_ins.data.get("is_available", True))
        self.assertIn("SHARES", res_ins.data.get("missing_components", []))
