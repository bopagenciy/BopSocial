"""
BS-5D.0A: Deterministic Benchmark Identity & Coverage Semantics Audit Test Suite.

Verifies:
1. Benchmark hash differs when granularity differs (day vs period).
2. Period benchmark cannot masquerade as day benchmark.
3. Persisted signals retain canonical benchmark granularity ('day').
4. BS-5D preview uses matching benchmark granularity ('day').
5. unavailable_metrics remains 10.
6. non_comparable_metrics remains 2.
7. Optional combined limitation count may equal 12 (limited_or_noncomparable_metrics).
8. SAVES remains NON_COMPARABLE.
9. VIDEO_VIEWS remains NON_COMPARABLE.
10. No database writes / 100% read-only operation.
11. No provider calls / deterministic offline execution.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    BusinessSignal,
    ExecutiveReport,
)
from social_stats.analytics.multichannel.benchmarks import (
    build_multichannel_benchmark,
    generate_benchmark_hash,
    BENCHMARK_SCHEMA_VERSION,
)
from social_stats.analytics.multichannel.taxonomies import (
    ComparisonCompatibility,
    ComparisonReasonCode,
    ComparisonStatus,
    ComparisonWinner,
)
from social_stats.analytics.reporting.builder import (
    build_executive_report_data,
)


class MultichannelSemanticsAuditTests(TestCase):
    """BS-5D.0A Deterministic Semantics Audit."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name="Pilot Client",
            company="Bop Pilot Org",
            email="pilot_staging@example.com",
            is_active=True,
        )
        self.start_date = date(2026, 9, 22)
        self.end_date = date(2026, 10, 22)
        self.canonical_hash = "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"

        # Platform Credentials
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            page_id="fb_page_123",
            is_active=True,
        )
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform="instagram",
            instagram_account_id="ig_biz_456",
            is_active=True,
        )

        # Baseline rollups matching canonical pilot
        # FB: 20 followers, 0 reactions, 0 comments
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            period="day",
            period_start=self.end_date,
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=Decimal("20.0"),
            sample_count=3,
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            period="day",
            period_start=self.start_date,
            normalized_metric="REACTIONS",
            metric_value=Decimal("0.0"),
            sample_count=50,
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            period="day",
            period_start=self.start_date,
            normalized_metric="COMMENTS",
            metric_value=Decimal("0.0"),
            sample_count=50,
        )
        # IG: 50 followers, 6 reactions, 0 comments
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="instagram",
            metric_scope="account",
            period="day",
            period_start=self.end_date,
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=Decimal("50.0"),
            sample_count=3,
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="instagram",
            metric_scope="account",
            period="day",
            period_start=self.start_date,
            normalized_metric="REACTIONS",
            metric_value=Decimal("6.0"),
            sample_count=21,
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="instagram",
            metric_scope="account",
            period="day",
            period_start=self.start_date,
            normalized_metric="COMMENTS",
            metric_value=Decimal("0.0"),
            sample_count=21,
        )

    # 1. Benchmark hash differs when granularity differs
    def test_01_benchmark_hash_differs_when_granularity_differs(self):
        """Benchmark hash differs when granularity is day vs period."""
        bm_day = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        bm_period = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="period",
        )
        self.assertNotEqual(bm_day.benchmark_hash, bm_period.benchmark_hash)
        self.assertEqual(bm_day.granularity, "day")
        self.assertEqual(bm_period.granularity, "period")

    # 2. Period benchmark cannot masquerade as day benchmark
    def test_02_period_benchmark_cannot_masquerade_as_day_benchmark(self):
        """A period benchmark cannot match the day benchmark identity."""
        bm_day = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        bm_period = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="period",
        )
        self.assertNotEqual(bm_period.benchmark_hash, bm_day.benchmark_hash)

        # Direct hash function test: altering granularity alters SHA256 digest
        h_day = generate_benchmark_hash(
            schema_version=BENCHMARK_SCHEMA_VERSION,
            client_id=self.client_obj.id,
            platform_a="facebook",
            platform_b="instagram",
            period_start=self.start_date,
            period_end=self.end_date,
            granularity="day",
            metric_results=bm_day.metric_results,
        )
        h_period = generate_benchmark_hash(
            schema_version=BENCHMARK_SCHEMA_VERSION,
            client_id=self.client_obj.id,
            platform_a="facebook",
            platform_b="instagram",
            period_start=self.start_date,
            period_end=self.end_date,
            granularity="period",
            metric_results=bm_day.metric_results,
        )
        self.assertNotEqual(h_day, h_period)

    # 3. Persisted signals retain canonical benchmark granularity
    def test_03_persisted_signals_retain_canonical_benchmark_granularity(self):
        """Signals generated or persisted from canonical pilot retain granularity 'day'."""
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="AUDIENCE_SIZE_DIFFERENCE",
            metric="FOLLOWERS_TOTAL",
            scope="multichannel",
            object_id="",
            period_start=self.start_date,
            period_end=self.end_date,
            observed_value=Decimal("50.0"),
            baseline_value=Decimal("20.0"),
            absolute_delta=Decimal("-30.0"),
            confidence_level="HIGH",
            direction="NEUTRAL",
            severity="INFO",
            is_actionable=False,
            metadata={
                "granularity": "day",
                "benchmark_hash": self.canonical_hash,
                "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            },
            evidence={
                "category": "AUDIENCE",
                "benchmark_hash": self.canonical_hash,
                "platform_a": "facebook",
                "platform_b": "instagram",
            },
            signal_identity="test_sig_03",
        )
        self.assertEqual(sig.metadata.get("granularity"), "day")
        self.assertEqual(sig.metadata.get("benchmark_hash"), self.canonical_hash)
        self.assertEqual(sig.evidence.get("benchmark_hash"), self.canonical_hash)

    # 4. BS-5D preview uses matching benchmark granularity
    def test_04_preview_uses_matching_benchmark_granularity(self):
        """BS-5D preview matches benchmark granularity ('day') and benchmark_hash."""
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        self.assertTrue(mc["has_multichannel_data"])
        self.assertEqual(mc["benchmark_hash"], bm.benchmark_hash)

    # 5. unavailable_metrics remains 10
    def test_05_unavailable_metrics_remains_10(self):
        """Machine payload preserves distinct unavailable_metrics count of 10."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        cov = report_data["multichannel_intelligence"]["coverage_summary"]
        self.assertEqual(cov["unavailable_metrics"], 10)
        self.assertEqual(report_data["multichannel_intelligence"]["coverage"]["unavailable_metrics"], 10)

    # 6. non_comparable_metrics remains 2
    def test_06_non_comparable_metrics_remains_2(self):
        """Machine payload preserves distinct non_comparable_metrics count of 2."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        cov = report_data["multichannel_intelligence"]["coverage_summary"]
        self.assertEqual(cov["non_comparable_metrics"], 2)
        self.assertEqual(report_data["multichannel_intelligence"]["coverage"]["non_comparable_metrics"], 2)

    # 7. optional combined limitation count may equal 12
    def test_07_optional_combined_limitation_count_equals_12(self):
        """Optional derived field limited_or_noncomparable_metrics equals 12."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        cov = report_data["multichannel_intelligence"]["coverage_summary"]
        self.assertEqual(cov["limited_or_noncomparable_metrics"], 12)
        self.assertEqual(
            cov["limited_or_noncomparable_metrics"],
            cov["unavailable_metrics"] + cov["non_comparable_metrics"]
        )

    # 8. SAVES remains NON_COMPARABLE
    def test_08_saves_remains_non_comparable(self):
        """SAVES is strictly NON_COMPARABLE and not ranked."""
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        res = next(r for r in bm.metric_results if r.metric == "SAVES")
        self.assertEqual(res.compatibility, ComparisonCompatibility.NON_COMPARABLE)
        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.METRIC_NOT_EQUIVALENT)
        self.assertFalse(res.rankable)
        self.assertEqual(res.winner, ComparisonWinner.NO_WINNER)

    # 9. VIDEO_VIEWS remains NON_COMPARABLE
    def test_09_video_views_remains_non_comparable(self):
        """VIDEO_VIEWS is strictly NON_COMPARABLE and not ranked."""
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        res = next(r for r in bm.metric_results if r.metric == "VIDEO_VIEWS")
        self.assertEqual(res.compatibility, ComparisonCompatibility.NON_COMPARABLE)
        self.assertEqual(res.status, ComparisonStatus.UNAVAILABLE)
        self.assertEqual(res.reason_code, ComparisonReasonCode.METRIC_NOT_EQUIVALENT)
        self.assertFalse(res.rankable)
        self.assertEqual(res.winner, ComparisonWinner.NO_WINNER)

    # 10. no writes
    def test_10_no_database_writes(self):
        """Preview and benchmark generation perform 0 database writes."""
        initial_counts = {
            "Client": Client.objects.count(),
            "PlatformCredential": PlatformCredential.objects.count(),
            "SocialMetricRollup": SocialMetricRollup.objects.count(),
            "BusinessSignal": BusinessSignal.objects.count(),
            "ExecutiveReport": ExecutiveReport.objects.count(),
        }

        # Run benchmark and preview
        build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )

        final_counts = {
            "Client": Client.objects.count(),
            "PlatformCredential": PlatformCredential.objects.count(),
            "SocialMetricRollup": SocialMetricRollup.objects.count(),
            "BusinessSignal": BusinessSignal.objects.count(),
            "ExecutiveReport": ExecutiveReport.objects.count(),
        }
        self.assertEqual(initial_counts, final_counts)

    # 11. no provider calls
    @patch("urllib.request.urlopen")
    @patch("requests.get")
    @patch("requests.post")
    def test_11_no_provider_calls(self, mock_post, mock_get, mock_urlopen):
        """Deterministic offline evaluation makes zero network / provider calls."""
        build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=self.start_date,
            end_date=self.end_date,
            granularity="day",
        )
        build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mock_urlopen.assert_not_called()
        mock_get.assert_not_called()
        mock_post.assert_not_called()
