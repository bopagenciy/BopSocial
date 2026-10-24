"""
Comprehensive Test Suite for BS-5C: Multichannel Business Signal Engine.

Tests:
- AT: Outperformance signal generation (REACTIONS FB=10, IG=20 -> IG wins)
- AU: Zero-baseline outperformance (FB=0, IG=6 -> relative_delta is None, no fake %)
- AV: Followers total audience difference (FB=20, IG=50 -> AUDIENCE_SIZE_DIFFERENCE, NO_WINNER)
- AW: Zero/zero tie suppression (COMMENTS 0 vs 0 -> suppressed as low-information)
- AX: Consolidated data limitation signal (multiple unavailable metrics -> ONE signal)
- AY: Consolidated non-comparable signal (SAVES, VIDEO_VIEWS -> ONE signal)
- AZ: Engagement total component limitation (SHARES unavailable -> limitation, no winner)
- BA: Insufficient format sample gating (n < 3 -> INSUFFICIENT_CROSS_PLATFORM_SAMPLE)
- BB: Adequate format sample advantage (n >= 3 both platforms -> FORMAT_PLATFORM_ADVANTAGE)
- BC: Deterministic identity reproducibility (same benchmark -> same SHA256 hashes)
- BD: Benchmark change alters identity
- BE: Duplicate prevention on persist=True (idempotent update_or_create)
- BF: Preview mode guarantees 0 database writes
- BG: Unknown benchmark schema version fails closed
- BH: Overall platform winner strictly prohibited
- BI: Tenant isolation verification (cross-tenant returns 404)
- BJ: Bilingual templates (ES & EN deterministic strings, identical machine identity)
- BK: Confidence determinism
- BL: Actionability consistency (audience gauge non-actionable, provider partial actionable)
- API: GET/POST /api/analytics/multichannel/signals/preview/
- API: POST /api/analytics/multichannel/signals/ fail-closed persistence protection
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
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
    NormalizationType,
    ConfidenceTier,
    CoverageSummary,
    FORBIDDEN_SIGNAL_TYPES,
    MultichannelBenchmarkResult,
    MultichannelSignalType,
    MultichannelSignalValidationError,
    RecommendedActionCode,
    SignalCategory,
    SignalSeverity,
    WinnerSummary,
    build_multichannel_benchmark,
    compute_multichannel_signal_identity,
    format_signal_description,
    generate_benchmark_hash,
    generate_multichannel_signals,
    validate_signal_candidate,
)
from social_stats.analytics.multichannel.comparison import ComparisonResult
from social_stats.models import (
    BusinessSignal,
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
)


class MultichannelSignalEngineTests(TestCase):
    """Exhaustive test suite for BS-5C multichannel business signal engine."""

    def setUp(self):
        self.user = User.objects.create_user(username="bs5c_user", password="password123")
        self.other_user = User.objects.create_user(username="bs5c_other", password="password123")

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

        self.cred_fb = PlatformCredential.objects.create(
            client=self.client_a,
            platform="facebook",
            page_id="fb_page_123",
            page_name="Alpha FB",
            access_token="FB_SECRET_TOKEN",
            is_active=True,
        )

        self.cred_ig = PlatformCredential.objects.create(
            client=self.client_a,
            platform="instagram",
            instagram_account_id="ig_act_123",
            access_token="IG_SECRET_TOKEN",
            is_active=True,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def _build_synthetic_benchmark(
        self,
        *,
        results_map=None,
        client_id=None,
        cohort_results=None,
        schema_version=BENCHMARK_SCHEMA_VERSION,
    ):
        """Builds a deterministic MultichannelBenchmarkResult envelope with mock or custom results."""
        c_id = client_id or self.client_a.id
        results_map = results_map or {}
        metric_results = []

        total_m = len(CANONICAL_METRIC_ORDER)
        comp_m = 0
        rank_m = 0
        unavail_m = 0
        non_comp_m = 0

        p_a_wins = 0
        p_b_wins = 0
        ties = 0

        for m in CANONICAL_METRIC_ORDER:
            if m in results_map:
                res = results_map[m]
            else:
                # Default to unavailable
                res = ComparisonResult(
                    metric=m,
                    platform_a="facebook",
                    platform_b="instagram",
                    status=ComparisonStatus.UNAVAILABLE,
                    compatibility=ComparisonCompatibility.DIRECT,
                    direction=ComparisonDirection.HIGHER_IS_BETTER,
                    normalization=NormalizationType.NONE,
                    rankable=True,
                    value_a=None,
                    value_b=None,
                    normalized_value_a=None,
                    normalized_value_b=None,
                    delta_absolute=None,
                    delta_relative=None,
                    winner=ComparisonWinner.UNAVAILABLE,
                    period_start=date(2026, 10, 1),
                    period_end=date(2026, 10, 7),
                    sample_a=0,
                    sample_b=0,
                    reason_code=ComparisonReasonCode.PROVIDER_PARTIAL,
                )
            metric_results.append(res)

            if res.status == ComparisonStatus.AVAILABLE:
                comp_m += 1
                if res.rankable:
                    rank_m += 1
                if res.winner == ComparisonWinner.PLATFORM_A:
                    p_a_wins += 1
                elif res.winner == ComparisonWinner.PLATFORM_B:
                    p_b_wins += 1
                elif res.winner == ComparisonWinner.TIE:
                    ties += 1
            elif res.status == ComparisonStatus.UNAVAILABLE:
                unavail_m += 1
            if res.compatibility == ComparisonCompatibility.NON_COMPARABLE:
                non_comp_m += 1

        b_hash = generate_benchmark_hash(
            schema_version=schema_version,
            client_id=c_id,
            platform_a="facebook",
            platform_b="instagram",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            granularity="period",
            metric_results=metric_results,
        )

        return MultichannelBenchmarkResult(
            schema_version=schema_version,
            client_id=c_id,
            platform_a="facebook",
            platform_b="instagram",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            granularity="period",
            benchmark_hash=b_hash,
            coverage_summary=CoverageSummary(
                total_metrics=total_m,
                comparable_metrics=comp_m,
                rankable_metrics=rank_m,
                non_rankable_metrics=comp_m - rank_m,
                unavailable_metrics=unavail_m,
                non_comparable_metrics=non_comp_m,
                invalid_metrics=0,
            ),
            winner_summary=WinnerSummary(
                platform_a_wins=p_a_wins,
                platform_b_wins=p_b_wins,
                ties=ties,
                no_winner=0,
                unavailable=unavail_m,
            ),
            metric_results=metric_results,
            cohort_results=cohort_results or [],
        )

    # --------------------------------------------------------------------------
    # AT. TEST — OUTPERFORMANCE SIGNAL
    # --------------------------------------------------------------------------
    def test_at_outperformance_signal(self):
        """Synthetic REACTIONS FB=10, IG=20 emits PLATFORM_METRIC_OUTPERFORMANCE with IG winner."""
        res_reactions = ComparisonResult(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            normalization=NormalizationType.NONE,
            rankable=True,
            value_a=Decimal("10.0000"),
            value_b=Decimal("20.0000"),
            normalized_value_a=Decimal("10.0000"),
            normalized_value_b=Decimal("20.0000"),
            delta_absolute=Decimal("-10.0000"),
            delta_relative=Decimal("-50.0000"),  # FB relative to baseline IG is -50%
            winner=ComparisonWinner.PLATFORM_B,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=5,
            sample_b=5,
            reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"REACTIONS": res_reactions})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        outperf = next((s for s in signals if s["metric"] == "REACTIONS"), None)
        self.assertIsNotNone(outperf)
        self.assertEqual(outperf["signal_type"], MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE)
        self.assertEqual(outperf["platform"], "instagram")
        self.assertEqual(outperf["confidence_level"], ConfidenceTier.HIGH)
        self.assertTrue(outperf["is_actionable"])
        self.assertEqual(outperf["severity"], SignalSeverity.POSITIVE)
        self.assertEqual(outperf["evidence"]["winner"], ComparisonWinner.PLATFORM_B.value)

    # --------------------------------------------------------------------------
    # AU. TEST — ZERO BASELINE HANDLING
    # --------------------------------------------------------------------------
    def test_au_zero_baseline(self):
        """FB=0, IG=6 sets relative_delta to None and prevents fake percentage claims."""
        res_reactions = ComparisonResult(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            normalization=NormalizationType.NONE,
            rankable=True,
            value_a=Decimal("0.0000"),
            value_b=Decimal("6.0000"),
            normalized_value_a=Decimal("0.0000"),
            normalized_value_b=Decimal("6.0000"),
            delta_absolute=Decimal("-6.0000"),
            delta_relative=None,  # Zero baseline
            winner=ComparisonWinner.PLATFORM_B,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=5,
            sample_b=5,
            reason_code=ComparisonReasonCode.ZERO_BASELINE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"REACTIONS": res_reactions})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        outperf = next((s for s in signals if s["metric"] == "REACTIONS"), None)
        self.assertIsNotNone(outperf)
        self.assertIsNone(outperf["relative_delta"])
        self.assertTrue(outperf["evidence"]["zero_baseline"])
        self.assertNotIn("%", outperf["description"])
        self.assertIn("6", outperf["description"])

    # --------------------------------------------------------------------------
    # AV. TEST — FOLLOWERS AUDIENCE SIZE DIFFERENCE
    # --------------------------------------------------------------------------
    def test_av_followers_audience_difference(self):
        """FB=20, IG=50 emits AUDIENCE_SIZE_DIFFERENCE with NO_WINNER and non-actionable."""
        res_followers = ComparisonResult(
            metric="FOLLOWERS_TOTAL",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.NEUTRAL,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=Decimal("20.0000"),
            value_b=Decimal("50.0000"),
            normalized_value_a=Decimal("20.0000"),
            normalized_value_b=Decimal("50.0000"),
            delta_absolute=Decimal("-30.0000"),
            delta_relative=Decimal("-60.0000"),
            winner=ComparisonWinner.NO_WINNER,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=1,
            sample_b=1,
            reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"FOLLOWERS_TOTAL": res_followers})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        aud_sig = next((s for s in signals if s["metric"] == "FOLLOWERS_TOTAL"), None)
        self.assertIsNotNone(aud_sig)
        self.assertEqual(aud_sig["signal_type"], MultichannelSignalType.AUDIENCE_SIZE_DIFFERENCE)
        self.assertEqual(aud_sig["evidence"]["winner"], ComparisonWinner.NO_WINNER.value)
        self.assertFalse(aud_sig["is_actionable"])
        self.assertEqual(aud_sig["severity"], SignalSeverity.INFO)

    # --------------------------------------------------------------------------
    # AW. TEST — ZERO/ZERO TIE SUPPRESSION
    # --------------------------------------------------------------------------
    def test_aw_zero_zero_tie_suppression(self):
        """COMMENTS: 0 vs 0 is suppressed from active candidate signals as low-information."""
        res_comments = ComparisonResult(
            metric="COMMENTS",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            normalization=NormalizationType.NONE,
            rankable=True,
            value_a=Decimal("0.0000"),
            value_b=Decimal("0.0000"),
            normalized_value_a=Decimal("0.0000"),
            normalized_value_b=Decimal("0.0000"),
            delta_absolute=Decimal("0.0000"),
            delta_relative=None,
            winner=ComparisonWinner.TIE,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=2,
            sample_b=2,
            reason_code=ComparisonReasonCode.ZERO_BASELINE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"COMMENTS": res_comments})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        # COMMENTS should NOT be in candidate signals
        cand_metrics = [s.get("metric") for s in engine_res["candidate_signals"]]
        self.assertNotIn("COMMENTS", cand_metrics)

        # Should be in suppressed_candidates
        suppressed_metrics = [s["metric"] for s in engine_res["suppressed_candidates"]]
        self.assertIn("COMMENTS", suppressed_metrics)

    # --------------------------------------------------------------------------
    # AX. TEST — CONSOLIDATED DATA LIMITATION
    # --------------------------------------------------------------------------
    def test_ax_data_limitation_consolidation(self):
        """Unavailable metrics are consolidated into ONE CROSS_PLATFORM_DATA_LIMITATION signal."""
        benchmark = self._build_synthetic_benchmark()  # all 15 metrics unavailable
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        lim_signals = [s for s in signals if s["signal_type"] == MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION]
        self.assertEqual(len(lim_signals), 1)

        lim = lim_signals[0]
        self.assertEqual(lim["evidence"]["affected_metrics_count"], 15)
        self.assertEqual(lim["confidence_level"], ConfidenceTier.HIGH)
        self.assertIn("PROVIDER_PARTIAL", lim["evidence"]["unavailable_by_reason"])

    # --------------------------------------------------------------------------
    # AY. TEST — CONSOLIDATED NON-COMPARABLE METRICS
    # --------------------------------------------------------------------------
    def test_ay_non_comparable_consolidation(self):
        """SAVES and VIDEO_VIEWS are consolidated into ONE CROSS_PLATFORM_METRIC_NON_COMPARABLE signal."""
        res_saves = ComparisonResult(
            metric="SAVES",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=ComparisonCompatibility.NON_COMPARABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.NO_WINNER,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=0,
            sample_b=0,
            reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
        )

        res_video = ComparisonResult(
            metric="VIDEO_VIEWS",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=ComparisonCompatibility.NON_COMPARABLE,
            direction=ComparisonDirection.NOT_APPLICABLE,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=None,
            value_b=None,
            normalized_value_a=None,
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.NO_WINNER,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=0,
            sample_b=0,
            reason_code=ComparisonReasonCode.METRIC_NOT_EQUIVALENT,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"SAVES": res_saves, "VIDEO_VIEWS": res_video})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        non_comp = next((s for s in signals if s["signal_type"] == MultichannelSignalType.CROSS_PLATFORM_METRIC_NON_COMPARABLE), None)
        self.assertIsNotNone(non_comp)
        self.assertIn("SAVES", non_comp["evidence"]["affected_metrics"])
        self.assertIn("VIDEO_VIEWS", non_comp["evidence"]["affected_metrics"])
        self.assertFalse(non_comp["is_actionable"])

    # --------------------------------------------------------------------------
    # AZ. TEST — ENGAGEMENT PARTIAL COMPONENT LIMITATION
    # --------------------------------------------------------------------------
    def test_az_engagement_partial(self):
        """ENGAGEMENT_TOTAL unavailable due to missing SHARES does not declare a false winner."""
        res_eng = ComparisonResult(
            metric="ENGAGEMENT_TOTAL",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.UNAVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            normalization=NormalizationType.NONE,
            rankable=True,
            value_a=Decimal("50.0000"),
            value_b=None,
            normalized_value_a=Decimal("50.0000"),
            normalized_value_b=None,
            delta_absolute=None,
            delta_relative=None,
            winner=ComparisonWinner.UNAVAILABLE,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=5,
            sample_b=0,
            reason_code=ComparisonReasonCode.COMPONENT_UNAVAILABLE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"ENGAGEMENT_TOTAL": res_eng})
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        # Ensure no outperformance signal was generated for ENGAGEMENT_TOTAL
        outperf_metrics = [
            s.get("metric") for s in engine_res["candidate_signals"]
            if s.get("signal_type") == MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE
        ]
        self.assertNotIn("ENGAGEMENT_TOTAL", outperf_metrics)

    # --------------------------------------------------------------------------
    # BA. TEST — INSUFFICIENT FORMAT SAMPLE
    # --------------------------------------------------------------------------
    def test_ba_insufficient_format_sample(self):
        """Format cohort with sample < 3 emits INSUFFICIENT_CROSS_PLATFORM_SAMPLE and no winner."""
        cohorts = [{
            "cohort_value": "IMAGE",
            "sample_a": 1,
            "sample_b": 2,
            "winner": ComparisonWinner.NO_WINNER.value,
        }]

        benchmark = self._build_synthetic_benchmark(cohort_results=cohorts)
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        insuf = next((s for s in signals if s["signal_type"] == MultichannelSignalType.INSUFFICIENT_CROSS_PLATFORM_SAMPLE), None)
        self.assertIsNotNone(insuf)
        self.assertEqual(insuf["confidence_level"], ConfidenceTier.NONE)
        self.assertTrue(insuf["is_actionable"])
        self.assertEqual(insuf["recommended_action_code"], RecommendedActionCode.CONTINUE_COLLECTING_DATA)

    # --------------------------------------------------------------------------
    # BB. TEST — ADEQUATE FORMAT SAMPLE
    # --------------------------------------------------------------------------
    def test_bb_adequate_format_sample(self):
        """Format cohort with sample >= 3 on both sides emits FORMAT_PLATFORM_ADVANTAGE."""
        cohorts = [{
            "cohort_value": "IMAGE",
            "sample_a": 5,
            "sample_b": 5,
            "winner": ComparisonWinner.PLATFORM_B.value,
        }]

        benchmark = self._build_synthetic_benchmark(cohort_results=cohorts)
        engine_res = generate_multichannel_signals(benchmark, persist=False)

        signals = engine_res["candidate_signals"]
        adv = next((s for s in signals if s["signal_type"] == MultichannelSignalType.FORMAT_PLATFORM_ADVANTAGE), None)
        self.assertIsNotNone(adv)
        self.assertEqual(adv["platform"], "instagram")
        self.assertTrue(adv["is_actionable"])
        self.assertEqual(adv["confidence_level"], ConfidenceTier.MEDIUM)

    # --------------------------------------------------------------------------
    # BC. TEST — DETERMINISTIC IDENTITY REPRODUCIBILITY
    # --------------------------------------------------------------------------
    def test_bc_deterministic_identity(self):
        """Identical inputs produce identical SHA256 signal identity digests."""
        id1 = compute_multichannel_signal_identity(
            client_id=3,
            signal_type=MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            benchmark_hash="14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
        )

        id2 = compute_multichannel_signal_identity(
            client_id=3,
            signal_type=MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            benchmark_hash="14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
        )

        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 64)

    # --------------------------------------------------------------------------
    # BD. TEST — BENCHMARK CHANGE ALTERS IDENTITY
    # --------------------------------------------------------------------------
    def test_bd_benchmark_change_alters_identity(self):
        """Altering the benchmark_hash changes the signal identity digest."""
        id1 = compute_multichannel_signal_identity(
            client_id=3,
            signal_type=MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            benchmark_hash="14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
        )

        id2 = compute_multichannel_signal_identity(
            client_id=3,
            signal_type=MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            benchmark_hash="different_benchmark_hash_1234567890abcdef1234567890abcdef12345678",
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
        )

        self.assertNotEqual(id1, id2)

    # --------------------------------------------------------------------------
    # BE. TEST — DUPLICATE PREVENTION
    # --------------------------------------------------------------------------
    def test_be_duplicate_prevention(self):
        """Calling generate_multichannel_signals with persist=True twice creates 0 duplicate rows."""
        benchmark = self._build_synthetic_benchmark()

        initial_count = BusinessSignal.objects.count()

        # First persistence
        res1 = generate_multichannel_signals(benchmark, persist=True, allow_persistence=True)
        persisted_1 = res1["persisted_count"]
        self.assertTrue(persisted_1 > 0)
        count_after_1 = BusinessSignal.objects.count()
        self.assertEqual(count_after_1, initial_count + persisted_1)

        # Second persistence (exact same benchmark)
        res2 = generate_multichannel_signals(benchmark, persist=True, allow_persistence=True)
        count_after_2 = BusinessSignal.objects.count()
        self.assertEqual(count_after_2, count_after_1)  # 0 new rows created!

    # --------------------------------------------------------------------------
    # BF. TEST — PREVIEW MODE GUARANTEES 0 DATABASE WRITES
    # --------------------------------------------------------------------------
    def test_bf_preview_no_writes(self):
        """Preview mode (persist=False) performs 0 database writes."""
        initial_count = BusinessSignal.objects.count()
        benchmark = self._build_synthetic_benchmark()

        res = generate_multichannel_signals(benchmark, persist=False)
        self.assertTrue(res["candidate_count"] > 0)
        self.assertEqual(res["persisted_count"], 0)

        post_count = BusinessSignal.objects.count()
        self.assertEqual(initial_count, post_count)

    # --------------------------------------------------------------------------
    # BG. TEST — UNKNOWN BENCHMARK VERSION FAILS CLOSED
    # --------------------------------------------------------------------------
    def test_bg_unknown_benchmark_version(self):
        """Unknown benchmark schema version fails closed."""
        benchmark = self._build_synthetic_benchmark(schema_version="invalid-version-v999")
        with self.assertRaises(ValueError):
            generate_multichannel_signals(benchmark, persist=False)

    # --------------------------------------------------------------------------
    # BH. TEST — OVERALL PLATFORM WINNER STRICTLY PROHIBITED
    # --------------------------------------------------------------------------
    def test_bh_overall_winner_prohibited(self):
        """Any attempt to validate a signal declaring an overall winner fails closed."""
        benchmark = self._build_synthetic_benchmark()

        forbidden_candidate = {
            "client_id": self.client_a.id,
            "platform": "instagram",
            "signal_type": "OVERALL_PLATFORM_WINNER",
            "metric": "OVERALL",
            "benchmark_hash": benchmark.benchmark_hash,
            "benchmark_schema_version": BENCHMARK_SCHEMA_VERSION,
            "signal_identity": "test_identity_hash_123",
            "is_actionable": True,
            "confidence_level": "HIGH",
            "evidence": {"platform_values": {"facebook": 1, "instagram": 2}},
        }

        is_valid, errors = validate_signal_candidate(forbidden_candidate, benchmark)
        self.assertFalse(is_valid)
        self.assertTrue(any("prohibited" in e.lower() for e in errors))

    # --------------------------------------------------------------------------
    # BI. TEST — TENANT ISOLATION
    # --------------------------------------------------------------------------
    def test_bi_tenant_isolation(self):
        """API client attempting to preview signals for another tenant gets 404."""
        url = (
            f"/api/analytics/multichannel/signals/preview/?client_id={self.client_b.id}"
            f"&platform_a=facebook&platform_b=instagram&start_date=2026-10-01&end_date=2026-10-07"
        )
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --------------------------------------------------------------------------
    # BJ. TEST — BILINGUAL TEMPLATES
    # --------------------------------------------------------------------------
    def test_bj_bilingual_templates(self):
        """Deterministic signal descriptions in ES and EN maintain identical machine identity."""
        evidence = {
            "metric": "REACTIONS",
            "platform_a": "facebook",
            "platform_b": "instagram",
            "winner_platform": "instagram",
            "baseline_platform": "facebook",
            "platform_values": {"facebook": 0, "instagram": 6},
            "zero_baseline": True,
        }

        desc_es = format_signal_description(
            MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            evidence,
            language="es",
        )
        desc_en = format_signal_description(
            MultichannelSignalType.PLATFORM_METRIC_OUTPERFORMANCE,
            evidence,
            language="en",
        )

        self.assertIn("Instagram registró 6 reacciones frente a 0 en Facebook", desc_es)
        self.assertIn("Instagram recorded 6 reactions compared with 0 on Facebook", desc_en)

    # --------------------------------------------------------------------------
    # BK. TEST — CONFIDENCE DETERMINISM
    # --------------------------------------------------------------------------
    def test_bk_confidence_determinism(self):
        """Identical evidence produces identical deterministic confidence without variance."""
        res_reactions = ComparisonResult(
            metric="REACTIONS",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.HIGHER_IS_BETTER,
            normalization=NormalizationType.NONE,
            rankable=True,
            value_a=Decimal("10.0000"),
            value_b=Decimal("20.0000"),
            normalized_value_a=Decimal("10.0000"),
            normalized_value_b=Decimal("20.0000"),
            delta_absolute=Decimal("-10.0000"),
            delta_relative=Decimal("-50.0000"),
            winner=ComparisonWinner.PLATFORM_B,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=10,
            sample_b=10,
            reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"REACTIONS": res_reactions})
        res1 = generate_multichannel_signals(benchmark, persist=False)
        res2 = generate_multichannel_signals(benchmark, persist=False)

        sig1 = next(s for s in res1["candidate_signals"] if s["metric"] == "REACTIONS")
        sig2 = next(s for s in res2["candidate_signals"] if s["metric"] == "REACTIONS")

        self.assertEqual(sig1["confidence_level"], sig2["confidence_level"])
        self.assertEqual(sig1["confidence_level"], ConfidenceTier.HIGH)

    # --------------------------------------------------------------------------
    # BL. TEST — ACTIONABILITY CONSISTENCY
    # --------------------------------------------------------------------------
    def test_bl_actionability_consistency(self):
        """Audience size is non-actionable; provider permission limitation is actionable."""
        res_followers = ComparisonResult(
            metric="FOLLOWERS_TOTAL",
            platform_a="facebook",
            platform_b="instagram",
            status=ComparisonStatus.AVAILABLE,
            compatibility=ComparisonCompatibility.DIRECT,
            direction=ComparisonDirection.NEUTRAL,
            normalization=NormalizationType.NONE,
            rankable=False,
            value_a=Decimal("20.0000"),
            value_b=Decimal("50.0000"),
            normalized_value_a=Decimal("20.0000"),
            normalized_value_b=Decimal("50.0000"),
            delta_absolute=Decimal("-30.0000"),
            delta_relative=Decimal("-60.0000"),
            winner=ComparisonWinner.NO_WINNER,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 7),
            sample_a=1,
            sample_b=1,
            reason_code=ComparisonReasonCode.DIRECTLY_COMPARABLE,
        )

        benchmark = self._build_synthetic_benchmark(results_map={"FOLLOWERS_TOTAL": res_followers})
        res = generate_multichannel_signals(benchmark, persist=False)

        aud_sig = next(s for s in res["candidate_signals"] if s["metric"] == "FOLLOWERS_TOTAL")
        self.assertFalse(aud_sig["is_actionable"])

        lim_sig = next(s for s in res["candidate_signals"] if s["signal_type"] == MultichannelSignalType.CROSS_PLATFORM_DATA_LIMITATION)
        self.assertTrue(lim_sig["is_actionable"])  # PROVIDER_PARTIAL is actionable (fix permissions)

    # --------------------------------------------------------------------------
    # API TESTS
    # --------------------------------------------------------------------------
    def test_api_signal_preview_get_and_post(self):
        """GET and POST /api/analytics/multichannel/signals/preview/ return 200 with candidates."""
        url = (
            f"/api/analytics/multichannel/signals/preview/?client_id={self.client_a.id}"
            f"&platform_a=facebook&platform_b=instagram&start_date=2026-10-01&end_date=2026-10-07"
            f"&granularity=period"
        )
        resp_get = self.api_client.get(url)
        self.assertEqual(resp_get.status_code, status.HTTP_200_OK)
        self.assertIn("candidate_signals", resp_get.data)
        self.assertEqual(resp_get.data["persisted_count"], 0)

        resp_post = self.api_client.post("/api/analytics/multichannel/signals/preview/", {
            "client_id": self.client_a.id,
            "platform_a": "facebook",
            "platform_b": "instagram",
            "start_date": "2026-10-01",
            "end_date": "2026-10-07",
            "granularity": "period",
        }, format="json")
        self.assertEqual(resp_post.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_post.data["persisted_count"], 0)

    def test_api_signal_persist_protection(self):
        """POST /api/analytics/multichannel/signals/ fails closed (403) without allow_persistence."""
        url = "/api/analytics/multichannel/signals/"
        resp = self.api_client.post(url, {
            "client_id": self.client_a.id,
            "platform_a": "facebook",
            "platform_b": "instagram",
            "start_date": "2026-10-01",
            "end_date": "2026-10-07",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
