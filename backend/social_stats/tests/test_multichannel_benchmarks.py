"""
Unit and Integration Test Suite for BS-5B:
Cross-Platform Benchmark and Comparison Engine.

Tests:
- AP: Bounded query count test (no N+1 query explosion)
- AQ: Full 15-metric benchmark evaluation
- AR: Deterministic benchmark_hash calculation
- AS: Hash change upon source data shift
- AT: Reach non-summation safety enforcement
- AU: Engagement total partial component gating
- AV: Followers total neutral non-rankability (NO_WINNER)
- AW: Observed zero preservation
- AX: Unavailable data preservation (no fake zeros)
- AY: Same platform comparison rejection
- AZ: Invalid period bounds rejection
- BA: Tenant isolation verification
- BB: Zero database writes guarantee
- BC: Canonical 15-metric output ordering
- BD: Platform order symmetry and hash orientation
- BE: Content cohort insufficient sample gating (n < 3)
- API endpoint GET /api/analytics/multichannel/benchmark/
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection, reset_queries
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.analytics.multichannel import (
    BENCHMARK_SCHEMA_VERSION,
    CANONICAL_METRIC_ORDER,
    ComparisonCompatibility,
    ComparisonDirection,
    ComparisonReasonCode,
    ComparisonStatus,
    ComparisonWinner,
    CoverageSummary,
    MultichannelBenchmarkResult,
    WinnerSummary,
    build_multichannel_benchmark,
    generate_benchmark_hash,
)
from social_stats.models import (
    BusinessSignal,
    Client,
    DailyMetric,
    ExecutiveNarrative,
    ExecutiveReport,
    PlatformCredential,
    PlatformPublishLog,
    PostMetric,
    PostQueue,
    QueuedItem,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
    UnifiedPost,
)


class MultichannelBenchmarksTests(TestCase):
    """Exhaustive test suite for BS-5B multichannel benchmark engine."""

    def setUp(self):
        self.user = User.objects.create_user(username="bs5b_user", password="password123")
        self.other_user = User.objects.create_user(username="bs5b_other", password="password123")

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
    # AP. BOUNDED QUERY COUNT TEST (NO N+1)
    # --------------------------------------------------------------------------
    @override_settings(DEBUG=True)
    def test_ap_bounded_query_count(self):
        """Full 15-metric benchmark executes in bounded queries (no N+1 query loop)."""
        # Create credentials and rollups for client_a
        PlatformCredential.objects.create(
            client=self.client_a, platform="facebook", scope="pages_show_list", is_active=True
        )
        PlatformCredential.objects.create(
            client=self.client_a, platform="instagram", scope="basic", is_active=True
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="REACTIONS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("100")
        )

        reset_queries()
        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            granularity="day",
        )

        # Bulk loading should execute <= 4 queries for the entire 15-metric benchmark
        query_count = len(connection.queries)
        self.assertLessEqual(query_count, 4, f"Too many queries issued ({query_count}). Potential N+1.")
        self.assertEqual(len(benchmark.metric_results), 15)

    # --------------------------------------------------------------------------
    # AQ. FULL 15-METRIC BENCHMARK EVALUATION
    # --------------------------------------------------------------------------
    def test_aq_full_15_metric_benchmark(self):
        """Synthetic aligned dataset evaluates all 15 canonical metrics with zero omissions."""
        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            granularity="day",
        )

        self.assertEqual(benchmark.schema_version, BENCHMARK_SCHEMA_VERSION)
        self.assertEqual(len(benchmark.metric_results), 15)
        evaluated_keys = [r.metric for r in benchmark.metric_results]
        self.assertEqual(evaluated_keys, CANONICAL_METRIC_ORDER)
        self.assertEqual(benchmark.coverage_summary.total_metrics, 15)

    # --------------------------------------------------------------------------
    # AR. DETERMINISTIC BENCHMARK HASH
    # --------------------------------------------------------------------------
    def test_ar_deterministic_hash(self):
        """Same input and underlying data produces identical benchmark hash."""
        b1 = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )
        b2 = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertEqual(b1.benchmark_hash, b2.benchmark_hash)
        self.assertEqual(len(b1.benchmark_hash), 64)

    # --------------------------------------------------------------------------
    # AS. HASH CHANGES WITH SOURCE DATA SHIFT
    # --------------------------------------------------------------------------
    def test_as_hash_changes_with_source(self):
        """Modifying underlying telemetry produces an altered benchmark hash."""
        b_before = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        # Insert new rollup
        SocialMetricRollup.objects.create(
            client=self.client_a,
            platform="facebook",
            normalized_metric="COMMENTS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("42"),
        )

        b_after = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        self.assertNotEqual(b_before.benchmark_hash, b_after.benchmark_hash)

    # --------------------------------------------------------------------------
    # AT. REACH DAILY SUM REJECTED
    # --------------------------------------------------------------------------
    def test_at_reach_daily_sum_rejected(self):
        """Benchmark orchestration rejects arithmetic summation of multi-day reach."""
        # Create daily reach rollups
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="REACH",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("100")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="REACH",
            period="day", period_start=date(2026, 10, 2), metric_value=Decimal("120")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="instagram", normalized_metric="REACH",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("90")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="instagram", normalized_metric="REACH",
            period="day", period_start=date(2026, 10, 2), metric_value=Decimal("110")
        )

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )

        reach_res = next(r for r in benchmark.metric_results if r.metric == "REACH")
        self.assertEqual(reach_res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(reach_res.reason_code, ComparisonReasonCode.NON_AGGREGATABLE_SUMMATION_REJECTED)

    # --------------------------------------------------------------------------
    # AU. ENGAGEMENT TOTAL PARTIAL COMPONENT GATING
    # --------------------------------------------------------------------------
    def test_au_engagement_total_partial(self):
        """When Instagram operates in PARTIAL mode lacking SHARES, ENGAGEMENT_TOTAL is UNAVAILABLE."""
        PlatformCredential.objects.create(
            client=self.client_a, platform="instagram", scope="basic", is_active=True
        )

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )

        eng_res = next(r for r in benchmark.metric_results if r.metric == "ENGAGEMENT_TOTAL")
        self.assertEqual(eng_res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(eng_res.reason_code, ComparisonReasonCode.COMPONENT_UNAVAILABLE)

    # --------------------------------------------------------------------------
    # AV. FOLLOWERS TOTAL NON-RANKABLE
    # --------------------------------------------------------------------------
    def test_av_followers_non_rankable(self):
        """FOLLOWERS_TOTAL gauge values are exposed, but winner is strictly NO_WINNER."""
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="FOLLOWERS_TOTAL",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("5000")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="instagram", normalized_metric="FOLLOWERS_TOTAL",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("2000")
        )

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
        )

        fol_res = next(r for r in benchmark.metric_results if r.metric == "FOLLOWERS_TOTAL")
        self.assertEqual(fol_res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(fol_res.winner, ComparisonWinner.NO_WINNER)
        self.assertFalse(fol_res.rankable)
        self.assertEqual(fol_res.value_a, Decimal("5000.0000"))
        self.assertEqual(fol_res.value_b, Decimal("2000.0000"))

    # --------------------------------------------------------------------------
    # AW. OBSERVED ZERO PRESERVATION
    # --------------------------------------------------------------------------
    def test_aw_zero_preservation(self):
        """Observed 0 values are preserved as valid numerics and participate in deltas."""
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="COMMENTS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("10")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="instagram", normalized_metric="COMMENTS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("0")
        )

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
        )

        comm_res = next(r for r in benchmark.metric_results if r.metric == "COMMENTS")
        self.assertEqual(comm_res.status, ComparisonStatus.AVAILABLE)
        self.assertEqual(comm_res.value_a, Decimal("10.0000"))
        self.assertEqual(comm_res.value_b, Decimal("0.0000"))
        self.assertEqual(comm_res.winner, ComparisonWinner.PLATFORM_A)
        self.assertIsNone(comm_res.delta_relative)
        self.assertEqual(comm_res.reason_code, ComparisonReasonCode.ZERO_BASELINE)

    # --------------------------------------------------------------------------
    # AX. UNAVAILABLE PRESERVATION
    # --------------------------------------------------------------------------
    def test_ax_unavailable_preservation(self):
        """Missing data evaluates to UNAVAILABLE and never converts into fake zeros."""
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="REACTIONS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("50")
        )
        # No instagram record created for REACTIONS

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
        )

        react_res = next(r for r in benchmark.metric_results if r.metric == "REACTIONS")
        self.assertEqual(react_res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(react_res.winner, ComparisonWinner.UNAVAILABLE)
        self.assertEqual(react_res.reason_code, ComparisonReasonCode.SOURCE_UNAVAILABLE)

    # --------------------------------------------------------------------------
    # AY. SAME PLATFORM COMPARISON REJECTED
    # --------------------------------------------------------------------------
    def test_ay_same_platform_rejected(self):
        """Comparing a platform to itself is strictly rejected."""
        with self.assertRaises(ValueError):
            build_multichannel_benchmark(
                client=self.client_a,
                platform_a="facebook",
                platform_b="facebook",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 7),
            )

    # --------------------------------------------------------------------------
    # AZ. INVALID PERIOD BOUNDS REJECTED
    # --------------------------------------------------------------------------
    def test_az_invalid_period_rejected(self):
        """Period where start_date > end_date is strictly rejected."""
        with self.assertRaises(ValueError):
            build_multichannel_benchmark(
                client=self.client_a,
                platform_a="facebook",
                platform_b="instagram",
                start_date=date(2026, 10, 10),
                end_date=date(2026, 10, 1),
            )

    # --------------------------------------------------------------------------
    # BA. TENANT ISOLATION
    # --------------------------------------------------------------------------
    def test_ba_tenant_isolation(self):
        """User for Client A cannot run benchmarks on Client B via API (returns 404)."""
        url = (
            f"/api/analytics/multichannel/benchmark/?client_id={self.client_b.id}"
            f"&platform_a=facebook&platform_b=instagram&start_date=2026-10-01&end_date=2026-10-07"
        )
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --------------------------------------------------------------------------
    # BB. ZERO DATABASE WRITES GUARANTEE
    # --------------------------------------------------------------------------
    def test_bb_no_writes(self):
        """Executing benchmarks leaves database row counts completely unmodified."""
        initial_counts = {
            "snapshots": SocialMetricSnapshot.objects.count(),
            "rollups": SocialMetricRollup.objects.count(),
            "signals": BusinessSignal.objects.count(),
            "reports": ExecutiveReport.objects.count(),
            "narratives": ExecutiveNarrative.objects.count(),
        }

        build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            include_cohorts=True,
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
    # BC. CANONICAL 15-METRIC OUTPUT ORDERING
    # --------------------------------------------------------------------------
    def test_bc_metric_ordering(self):
        """Output metric order is strictly canonical across all executions."""
        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
        )
        self.assertEqual([r.metric for r in benchmark.metric_results], CANONICAL_METRIC_ORDER)

    # --------------------------------------------------------------------------
    # BD. PLATFORM ORDER SYMMETRY & ORIENTED IDENTITY
    # --------------------------------------------------------------------------
    def test_bd_platform_order_symmetry(self):
        """FB↔IG and IG↔FB produce logically symmetric winners while hash is orientation-specific."""
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="facebook", normalized_metric="REACTIONS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("100")
        )
        SocialMetricRollup.objects.create(
            client=self.client_a, platform="instagram", normalized_metric="REACTIONS",
            period="day", period_start=date(2026, 10, 1), metric_value=Decimal("80")
        )

        b_ab = build_multichannel_benchmark(
            client=self.client_a, platform_a="facebook", platform_b="instagram",
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 1)
        )
        b_ba = build_multichannel_benchmark(
            client=self.client_a, platform_a="instagram", platform_b="facebook",
            start_date=date(2026, 10, 1), end_date=date(2026, 10, 1)
        )

        res_ab = next(r for r in b_ab.metric_results if r.metric == "REACTIONS")
        res_ba = next(r for r in b_ba.metric_results if r.metric == "REACTIONS")

        # In both, Facebook is the winner (as PLATFORM_A in b_ab, and as PLATFORM_B in b_ba)
        self.assertEqual(res_ab.winner, ComparisonWinner.PLATFORM_A)
        self.assertEqual(res_ba.winner, ComparisonWinner.PLATFORM_B)

        # Hashes differ because platform orientation is part of identity
        self.assertNotEqual(b_ab.benchmark_hash, b_ba.benchmark_hash)

    # --------------------------------------------------------------------------
    # BE. CONTENT COHORT INSUFFICIENT SAMPLE GATING
    # --------------------------------------------------------------------------
    def test_be_cohort_insufficient_sample(self):
        """Cohorts with sample size < 3 return INSUFFICIENT_SAMPLE and NO_WINNER."""
        # Create only 1 published post
        UnifiedPost.objects.create(
            client=self.client_a,
            title="Test Post",
            content="Test content",
            media_type="image",
            target_platforms=["facebook"],
            status="published",
            published_at=timezone.now(),
        )

        benchmark = build_multichannel_benchmark(
            client=self.client_a,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 7),
            include_cohorts=True,
        )

        self.assertIsNotNone(benchmark.cohort_results)
        img_cohort = next(c for c in benchmark.cohort_results if c["cohort_value"] == "IMAGE")
        self.assertEqual(img_cohort["status"], ComparisonStatus.UNAVAILABLE.value)
        self.assertEqual(img_cohort["winner"], ComparisonWinner.NO_WINNER.value)
        self.assertEqual(img_cohort["reason_code"], ComparisonReasonCode.INSUFFICIENT_SAMPLE.value)

    # --------------------------------------------------------------------------
    # REST API TEST
    # --------------------------------------------------------------------------
    def test_api_benchmark_endpoint(self):
        """GET /api/analytics/multichannel/benchmark/ returns valid 200 payload with stable structure."""
        url = (
            f"/api/analytics/multichannel/benchmark/?client_id={self.client_a.id}"
            f"&platform_a=facebook&platform_b=instagram&start_date=2026-10-01&end_date=2026-10-07"
            f"&granularity=day&include_cohorts=true"
        )
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["schema_version"], BENCHMARK_SCHEMA_VERSION)
        self.assertEqual(len(resp.data["benchmark_hash"]), 64)
        self.assertEqual(resp.data["coverage_summary"]["total_metrics"], 15)
        self.assertIn("platform_a_wins", resp.data["winner_summary"])
        self.assertEqual(len(resp.data["metric_results"]), 15)
        self.assertTrue(len(resp.data["cohort_results"]) > 0)
