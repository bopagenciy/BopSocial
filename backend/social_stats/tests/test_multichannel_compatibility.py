"""
Unit and Integration Test Suite for BS-5A:
Multichannel Metric Compatibility & Comparison Model.

Tests all required semantic invariants:
- AN: Direct comparison (REACTIONS, COMMENTS)
- AO: Observed zero vs missing
- AP: Unavailable is not zero
- AQ: Period mismatch
- AR: Followers total non-rankable (NO_WINNER)
- AS: Reach non-summation rejection
- AT: Average daily reach identity preservation
- AU: Engagement total partial failure when component missing
- AV: Relative delta safe zero baseline (ZERO_BASELINE)
- AW: Platform order symmetry
- AX: Unknown metric fail-closed
- AY: Unknown platform fail-closed
- AZ: Provider partial gating
- BA: Available metric under partial provider
- BB: Tenant isolation
- BC: Zero database writes guarantee
- Complete 15 canonical metric matrix coverage
- Bilingual ES/EN label mappings
- REST API compatibility and comparison endpoints
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.analytics.multichannel import (
    ComparisonCompatibility,
    ComparisonDirection,
    NormalizationType,
    ComparisonWinner,
    ComparisonStatus,
    ComparisonReasonCode,
    MetricComparisonRule,
    get_metric_comparison_rule,
    get_all_registered_rules,
    FB_IG_RULES,
    calculate_absolute_delta,
    calculate_relative_delta,
    determine_winner,
    ComparisonResult,
    compare_metric_across_platforms,
    get_reason_labels,
    get_status_labels,
    get_winner_labels,
)
from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    BusinessSignal,
    ExecutiveReport,
    ExecutiveNarrative,
    DailyMetric,
    PostMetric,
    SyncLog,
    UnifiedPost,
    PlatformPublishLog,
    PostQueue,
    QueuedItem,
)


class MultichannelCompatibilityTests(TestCase):
    """Exhaustive test suite for BS-5A multichannel comparison model."""

    def setUp(self):
        self.user = User.objects.create_user(username="bs5a_user", password="password123")
        self.other_user = User.objects.create_user(username="bs5a_other", password="password123")

        self.client_a = Client.objects.create(
            name="Alpha Corp",
            company="Alpha Corp",
            email="alpha@example.com",
            timezone="UTC",
            owner_user=self.user,
            is_active=True,
        )

        self.client_b = Client.objects.create(
            name="Beta Corp",
            company="Beta Corp",
            email="beta@example.com",
            timezone="UTC",
            owner_user=self.other_user,
            is_active=True,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    # --------------------------------------------------------------------------
    # AN. DIRECT COMPARISON
    # --------------------------------------------------------------------------
    def test_an_direct_comparison(self):
        """Synthetic source-backed comparable metric: REACTIONS FB=100, IG=80."""
        res = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("100"),
            value_b=Decimal("80"),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(res.compatibility, ComparisonCompatibility.DIRECT)
        self.assertEqual(res.direction, ComparisonDirection.HIGHER_IS_BETTER)
        self.assertTrue(res.rankable)
        self.assertEqual(res.value_a, Decimal("100"))
        self.assertEqual(res.value_b, Decimal("80"))
        self.assertEqual(res.delta_absolute, Decimal("20.0000"))
        self.assertEqual(res.delta_relative, Decimal("25.0000"))
        self.assertEqual(res.winner, ComparisonWinner.PLATFORM_A)
        self.assertEqual(res.reason_code, ComparisonReasonCode.DIRECTLY_COMPARABLE)

    # --------------------------------------------------------------------------
    # AO. OBSERVED ZERO
    # --------------------------------------------------------------------------
    def test_ao_observed_zero(self):
        """Observed zero remains a valid zero and does not become unavailable."""
        res = compare_metric_across_platforms(
            metric="COMMENTS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("5"),
            value_b=Decimal("0"),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(res.value_a, Decimal("5"))
        self.assertEqual(res.value_b, Decimal("0"))
        self.assertEqual(res.delta_absolute, Decimal("5.0000"))
        # Relative delta with 0 baseline must be None with ZERO_BASELINE reason code
        self.assertIsNone(res.delta_relative)
        self.assertEqual(res.reason_code, ComparisonReasonCode.ZERO_BASELINE)
        self.assertEqual(res.winner, ComparisonWinner.PLATFORM_A)

    # --------------------------------------------------------------------------
    # AP. UNAVAILABLE IS NOT ZERO
    # --------------------------------------------------------------------------
    def test_ap_unavailable_is_not_zero(self):
        """FB shares=12, IG shares=unavailable must NOT emit a false 12-vs-0 comparison."""
        res = compare_metric_across_platforms(
            metric="SHARES",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("12"),
            value_b=None,
            is_available_b=False,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.winner, ComparisonWinner.UNAVAILABLE)
        self.assertIsNone(res.delta_absolute)
        self.assertIsNone(res.delta_relative)
        self.assertEqual(res.reason_code, ComparisonReasonCode.SOURCE_UNAVAILABLE)

    # --------------------------------------------------------------------------
    # AQ. PERIOD MISMATCH
    # --------------------------------------------------------------------------
    def test_aq_period_mismatch(self):
        """Unaligned comparison periods or invalid date bounds must return PERIOD_MISMATCH."""
        # 1. Start date after end date
        res1 = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("10"),
            value_b=Decimal("10"),
            start_date=date(2026, 10, 10),
            end_date=date(2026, 10, 5),
        )
        self.assertEqual(res1.status, ComparisonStatus.INVALID)
        self.assertEqual(res1.reason_code, ComparisonReasonCode.PERIOD_MISMATCH)

        # 2. Asymmetric platform periods
        res2 = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("10"),
            value_b=Decimal("10"),
            period_start_a=date(2026, 10, 1),
            period_start_b=date(2026, 10, 2),
        )
        self.assertEqual(res2.status, ComparisonStatus.INVALID)
        self.assertEqual(res2.reason_code, ComparisonReasonCode.PERIOD_MISMATCH)

    # --------------------------------------------------------------------------
    # AR. FOLLOWERS TOTAL NON-RANKABLE
    # --------------------------------------------------------------------------
    def test_ar_followers_total_non_rankable(self):
        """FOLLOWERS_TOTAL is an audience gauge; winner is strictly NO_WINNER."""
        res = compare_metric_across_platforms(
            metric="FOLLOWERS_TOTAL",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("1000"),
            value_b=Decimal("300"),
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(res.direction, ComparisonDirection.NEUTRAL)
        self.assertFalse(res.rankable)
        self.assertEqual(res.winner, ComparisonWinner.NO_WINNER)
        self.assertEqual(res.delta_absolute, Decimal("700.0000"))
        self.assertEqual(res.reason_code, ComparisonReasonCode.NON_RANKABLE_METRIC)

    # --------------------------------------------------------------------------
    # AS. REACH NON-SUMMATION
    # --------------------------------------------------------------------------
    def test_as_reach_non_summation(self):
        """Daily reach cannot be arithmetically summed across multiple dates."""
        # Create daily rollups for Facebook and Instagram for client_a across 2 dates
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("100"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 2),
            metric_value=Decimal("120"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("90"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 2),
            metric_value=Decimal("110"),
        )

        res = compare_metric_across_platforms(
            client=self.client_a,
            metric="REACH",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            allow_reach_daily_sum=False,
        )

        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.NON_AGGREGATABLE_SUMMATION_REJECTED)
        self.assertEqual(res.winner, ComparisonWinner.UNAVAILABLE)

    # --------------------------------------------------------------------------
    # AT. AVERAGE DAILY REACH
    # --------------------------------------------------------------------------
    def test_at_average_daily_reach(self):
        """AVERAGE_DAILY_REACH compares daily averages and is never relabeled as REACH."""
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("100"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 2),
            metric_value=Decimal("200"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("80"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="REACH",
            period="day",
            period_start=date(2026, 10, 2),
            metric_value=Decimal("120"),
        )

        res = compare_metric_across_platforms(
            client=self.client_a,
            metric="AVERAGE_DAILY_REACH",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )

        self.assertEqual(res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(res.metric, "AVERAGE_DAILY_REACH")
        self.assertEqual(res.value_a, Decimal("150.0000"))
        self.assertEqual(res.value_b, Decimal("100.0000"))
        self.assertEqual(res.delta_absolute, Decimal("50.0000"))
        self.assertEqual(res.delta_relative, Decimal("50.0000"))
        self.assertEqual(res.winner, ComparisonWinner.PLATFORM_A)

    # --------------------------------------------------------------------------
    # AU. ENGAGEMENT TOTAL PARTIAL
    # --------------------------------------------------------------------------
    def test_au_engagement_total_partial(self):
        """When Instagram operates in PARTIAL mode lacking SHARES, ENGAGEMENT_TOTAL is UNAVAILABLE."""
        # Create IG credential without instagram_manage_insights (Basic/Partial mode)
        PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            scope="basic,pages_show_list",
            is_active=True,
        )

        res = compare_metric_across_platforms(
            client=self.client_a,
            metric="ENGAGEMENT_TOTAL",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.COMPONENT_UNAVAILABLE)
        self.assertEqual(res.winner, ComparisonWinner.UNAVAILABLE)

    # --------------------------------------------------------------------------
    # AV. RELATIVE DELTA ZERO BASELINE
    # --------------------------------------------------------------------------
    def test_av_relative_delta_zero_baseline(self):
        """Baseline platform B value of 0 results in relative delta None with ZERO_BASELINE."""
        rel_delta, reason = calculate_relative_delta(Decimal("100"), Decimal("0"))
        self.assertIsNone(rel_delta)
        self.assertEqual(reason, ComparisonReasonCode.ZERO_BASELINE)

    # --------------------------------------------------------------------------
    # AW. PLATFORM ORDER SYMMETRY
    # --------------------------------------------------------------------------
    def test_aw_order_symmetry(self):
        """Order of platform_a and platform_b inverts sign of delta_absolute while preserving winner logic."""
        res_ab = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("100"),
            value_b=Decimal("80"),
        )
        self.assertEqual(res_ab.delta_absolute, Decimal("20.0000"))
        self.assertEqual(res_ab.winner, ComparisonWinner.PLATFORM_A)  # Facebook

        res_ba = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="instagram",
            platform_b="facebook",
            value_a=Decimal("80"),
            value_b=Decimal("100"),
        )
        self.assertEqual(res_ba.delta_absolute, Decimal("-20.0000"))
        self.assertEqual(res_ba.winner, ComparisonWinner.PLATFORM_B)  # Facebook

    # --------------------------------------------------------------------------
    # AX. UNKNOWN METRIC FAIL CLOSED
    # --------------------------------------------------------------------------
    def test_ax_unknown_metric(self):
        """Unknown metric identifiers fail closed."""
        res = compare_metric_across_platforms(
            metric="TOTALLY_UNKNOWN_METRIC_XYZ",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("10"),
            value_b=Decimal("10"),
        )
        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.UNSUPPORTED_METRIC)

    # --------------------------------------------------------------------------
    # AY. UNKNOWN PLATFORM FAIL CLOSED
    # --------------------------------------------------------------------------
    def test_ay_unknown_platform(self):
        """Unmapped platform pair fails closed."""
        res = compare_metric_across_platforms(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="myspace",
            value_a=Decimal("10"),
            value_b=Decimal("10"),
        )
        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.UNSUPPORTED_PLATFORM)

    # --------------------------------------------------------------------------
    # AZ. PROVIDER PARTIAL GATING
    # --------------------------------------------------------------------------
    def test_az_provider_partial(self):
        """Unsupported metric on partial provider returns PROVIDER_PARTIAL."""
        PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            scope="basic",
            is_active=True,
        )

        res = compare_metric_across_platforms(
            client=self.client_a,
            metric="SHARES",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )
        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.PROVIDER_PARTIAL)

    # --------------------------------------------------------------------------
    # BA. AVAILABLE METRIC UNDER PARTIAL PROVIDER
    # --------------------------------------------------------------------------
    def test_ba_available_metric_under_partial_provider(self):
        """Supported metric (COMMENTS) under partial provider is not rejected."""
        PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            scope="basic",
            is_active=True,
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="COMMENTS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("50"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="COMMENTS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("40"),
        )

        res = compare_metric_across_platforms(
            client=self.client_a,
            metric="COMMENTS",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
        )
        self.assertEqual(res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(res.value_a, Decimal("50.0000"))
        self.assertEqual(res.value_b, Decimal("40.0000"))
        self.assertEqual(res.winner, ComparisonWinner.PLATFORM_A)

    # --------------------------------------------------------------------------
    # BB. TENANT ISOLATION
    # --------------------------------------------------------------------------
    def test_bb_tenant_isolation(self):
        """Client A user cannot query client B data via API or comparison engine."""
        url = f"/api/analytics/multichannel/compare/?client_id={self.client_b.id}&metric=REACTIONS"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --------------------------------------------------------------------------
    # BC. ZERO DATABASE WRITES GUARANTEE
    # --------------------------------------------------------------------------
    def test_bc_no_writes(self):
        """Comparing metrics must never create or alter snapshots, rollups, signals, or reports."""
        initial_counts = {
            "snapshots": SocialMetricSnapshot.objects.count(),
            "rollups": SocialMetricRollup.objects.count(),
            "signals": BusinessSignal.objects.count(),
            "reports": ExecutiveReport.objects.count(),
            "narratives": ExecutiveNarrative.objects.count(),
        }

        # Execute multiple comparison queries
        compare_metric_across_platforms(
            client=self.client_a,
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )
        compare_metric_across_platforms(
            metric="COMMENTS",
            platform_a="facebook",
            platform_b="instagram",
            value_a=Decimal("10"),
            value_b=Decimal("20"),
        )

        final_counts = {
            "snapshots": SocialMetricSnapshot.objects.count(),
            "rollups": SocialMetricRollup.objects.count(),
            "signals": BusinessSignal.objects.count(),
            "reports": ExecutiveReport.objects.count(),
            "narratives": ExecutiveNarrative.objects.count(),
        }
        self.assertEqual(initial_counts, final_counts)

    # --------------------------------------------------------------------------
    # COMPLETE 15 CANONICAL METRIC MATRIX AUDIT
    # --------------------------------------------------------------------------
    def test_matrix_all_15_canonical_metrics(self):
        """Every canonical metric must be explicitly registered with unambiguous semantics."""
        expected_15 = [
            "REACH",
            "AVERAGE_DAILY_REACH",
            "IMPRESSIONS",
            "FOLLOWERS_TOTAL",
            "FOLLOWERS_NET_CHANGE",
            "PROFILE_VIEWS",
            "CLICKS_TOTAL",
            "ENGAGEMENT_TOTAL",
            "REACTIONS",
            "COMMENTS",
            "SHARES",
            "SAVES",
            "VIDEO_VIEWS",
            "VIDEO_WATCH_TIME",
            "VIDEO_AVG_WATCH_TIME",
        ]

        for m in expected_15:
            rule = get_metric_comparison_rule(m, "facebook", "instagram")
            self.assertIsNotNone(rule, f"Rule missing for canonical metric {m}")
            self.assertIsInstance(rule.compatibility, ComparisonCompatibility)
            self.assertIsInstance(rule.direction, ComparisonDirection)
            self.assertIsInstance(rule.normalization, NormalizationType)

        # Invariant checks on specific metrics:
        # SAVES and VIDEO_VIEWS must be NON_COMPARABLE
        self.assertEqual(
            get_metric_comparison_rule("SAVES", "facebook", "instagram").compatibility,
            ComparisonCompatibility.NON_COMPARABLE,
        )
        self.assertEqual(
            get_metric_comparison_rule("VIDEO_VIEWS", "facebook", "instagram").compatibility,
            ComparisonCompatibility.NON_COMPARABLE,
        )

        # FOLLOWERS_TOTAL must be NEUTRAL direction and non-rankable
        f_rule = get_metric_comparison_rule("FOLLOWERS_TOTAL", "facebook", "instagram")
        self.assertEqual(f_rule.direction, ComparisonDirection.NEUTRAL)
        self.assertFalse(f_rule.rankable)

    # --------------------------------------------------------------------------
    # BILINGUAL LABELS
    # --------------------------------------------------------------------------
    def test_bilingual_labels(self):
        """Every reason code and status must provide both ES and EN human labels."""
        for code in ComparisonReasonCode:
            labels = get_reason_labels(code)
            self.assertIn("es", labels)
            self.assertIn("en", labels)
            self.assertTrue(len(labels["es"]) > 5)
            self.assertTrue(len(labels["en"]) > 5)

        for s in ComparisonStatus:
            labels = get_status_labels(s)
            self.assertIn("es", labels)
            self.assertIn("en", labels)

        for w in ComparisonWinner:
            labels = get_winner_labels(w)
            self.assertIn("es", labels)
            self.assertIn("en", labels)

    # --------------------------------------------------------------------------
    # API ENDPOINTS
    # --------------------------------------------------------------------------
    def test_api_compatibility_and_compare_endpoints(self):
        """Test the REST API endpoints for compatibility registry and comparison."""
        # 1. Compatibility view
        url_compat = "/api/analytics/multichannel/compatibility/?platform_a=facebook&platform_b=instagram"
        resp_compat = self.api_client.get(url_compat)
        self.assertEqual(resp_compat.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_compat.data["rules_count"], 15)

        # 2. Compare view with synthetic metric
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="REACTIONS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("150"),
        )
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="instagram",
            normalized_metric="REACTIONS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("100"),
        )

        url_compare = (
            f"/api/analytics/multichannel/compare/?client_id={self.client_a.id}&metric=REACTIONS"
            f"&platform_a=facebook&platform_b=instagram&start_date=2026-10-01&end_date=2026-10-01"
        )
        resp_compare = self.api_client.get(url_compare)
        self.assertEqual(resp_compare.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_compare.data["status"], "AVAILABLE")
        self.assertEqual(resp_compare.data["winner"], "PLATFORM_A")
        self.assertEqual(resp_compare.data["delta_absolute"], 50.0)
