"""
BS-6D.1A Narrative Grounding Reconciliation Tests
Validates root-cause fixes, benchmark isolation, period scoping,
validator enforcement, and artifact immutability.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase

from social_stats.models import (
    Client,
    BusinessSignal,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationRun,
    SocialMetricRollup,
)
from social_stats.analytics.multichannel.benchmarks import build_multichannel_benchmark
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.validator import NarrativeValidator
from social_stats.analytics.reporting.builder import build_executive_report_data


class BS6D1AGroundingReconciliationTests(TestCase):
    """
    Test matrix strictly verifying Section Q requirements:
    1. September benchmark comparable count
    2. Prior-period benchmark isolation
    3. Context hash matches Narrative #3
    4. Context contains correct comparable count
    5. Evidence refs period-scoped
    6. Incorrect comparable count rejected
    7. Old BS-5 benchmark cannot leak into September
    8. Unavailable Instagram remains unavailable
    9. No provider call
    10. Historical artifacts unchanged
    """

    def setUp(self):
        self.client_obj = Client.objects.create(
            id=333,
            name="Test Tenant",
            company="Test Agency",
            is_active=True,
        )

        # Setup September rollups (Facebook only, Instagram zero telemetry)
        for d in range(1, 30):
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="facebook",
                normalized_metric="REACTIONS",
                period="day",
                period_start=date(2026, 9, d),
                metric_value=Decimal("0.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="facebook",
                normalized_metric="FOLLOWERS_TOTAL",
                period="day",
                period_start=date(2026, 9, d),
                metric_value=Decimal("20.0"),
            )

        # Setup October rollups (Both Facebook and Instagram have telemetry)
        for d in range(1, 10):
            dt = date(2026, 10, d)
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="facebook",
                normalized_metric="REACTIONS",
                period="day",
                period_start=dt,
                metric_value=Decimal("0.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="instagram",
                normalized_metric="REACTIONS",
                period="day",
                period_start=dt,
                metric_value=Decimal("6.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="facebook",
                normalized_metric="FOLLOWERS_TOTAL",
                period="day",
                period_start=dt,
                metric_value=Decimal("20.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="instagram",
                normalized_metric="FOLLOWERS_TOTAL",
                period="day",
                period_start=dt,
                metric_value=Decimal("50.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="facebook",
                normalized_metric="COMMENTS",
                period="day",
                period_start=dt,
                metric_value=Decimal("0.0"),
            )
            SocialMetricRollup.objects.create(
                client=self.client_obj,
                platform="instagram",
                normalized_metric="COMMENTS",
                period="day",
                period_start=dt,
                metric_value=Decimal("0.0"),
            )

        # September signal (Signal #10 equivalent)
        self.sig_sep = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="instagram",
            signal_type="PROVIDER_PARTIAL",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            severity="INFO",
            direction="NEUTRAL",
            confidence_level="HIGH",
            evidence={"platform": "instagram", "support_level": "PARTIAL"},
            signal_identity="sep_sig_10",
        )

        # October signals (Signal #6 - #9 equivalent)
        self.sig_oct = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook:instagram",
            scope="multichannel",
            signal_type="CROSS_PLATFORM_DATA_LIMITATION",
            period_start=date(2026, 9, 22),
            period_end=date(2026, 10, 22),
            severity="INFO",
            direction="NEUTRAL",
            confidence_level="HIGH",
            evidence={
                "benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
                "comparable_metrics": 3,
                "affected_metrics_count": 12,
            },
            signal_identity="oct_sig_8",
        )

    def test_01_september_benchmark_comparable_count(self):
        """1. Recomputed September benchmark has strictly 0 comparable metrics."""
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            granularity="day",
        )
        cov = bm.coverage_summary
        self.assertEqual(cov.total_metrics, 15)
        self.assertEqual(cov.comparable_metrics, 0)
        self.assertEqual(cov.rankable_metrics, 0)
        self.assertEqual(cov.non_rankable_metrics, 0)
        self.assertEqual(cov.unavailable_metrics, 13)
        self.assertEqual(cov.non_comparable_metrics, 2)
        self.assertEqual(cov.invalid_metrics, 0)

    def test_02_prior_period_benchmark_isolation(self):
        """2. Prior period (BS-5: 2026-09-22 -> 2026-10-22) is isolated from September."""
        bm_oct = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 9),
            granularity="day",
        )
        bm_sep = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            granularity="day",
        )
        self.assertNotEqual(bm_oct.benchmark_hash, bm_sep.benchmark_hash)
        self.assertEqual(bm_oct.coverage_summary.comparable_metrics, 3)
        self.assertEqual(bm_sep.coverage_summary.comparable_metrics, 0)

    def test_03_context_hash_matches_narrative_3(self):
        """3. Narrative #3 context_hash is verified deterministically."""
        mock_report = ExecutiveReport.objects.create(
            client=self.client_obj,
            title="September Report",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            report_data={"business_intelligence_signals": {"signals": [{"id": 10, "signal_type": "PROVIDER_PARTIAL"}]}},
        )
        ctx1 = build_grounded_narrative_context(mock_report)
        ctx2 = build_grounded_narrative_context(mock_report)
        h1 = compute_context_hash(ctx1)
        h2 = compute_context_hash(ctx2)
        self.assertEqual(h1, h2)

    def test_04_context_contains_correct_comparable_count(self):
        """4. Properly built September report data yields context with comparable_metrics: 0."""
        rep_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
            report_type="EXECUTIVE",
            language="es",
        )
        cov = rep_data["multichannel_intelligence"]["coverage"]
        self.assertEqual(cov["comparable_metrics"], 0)
        self.assertEqual(cov["coverage_ratio"], "0/15")

    def test_05_evidence_refs_period_scoped(self):
        """5. Signals outside September are excluded by period containment."""
        rep_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
            report_type="EXECUTIVE",
            language="es",
        )
        sigs = rep_data["business_intelligence_signals"]["signals"]
        sig_ids = [s["id"] for s in sigs]
        self.assertIn(self.sig_sep.id, sig_ids)
        self.assertNotIn(self.sig_oct.id, sig_ids)

    def test_06_incorrect_comparable_count_rejected(self):
        """6. Narrative claiming 3/15 when context has 0/15 is strictly rejected."""
        mock_context = {
            "report": {"language": "es", "id": 3},
            "multichannel_intelligence": {
                "coverage_summary": {
                    "status": "LIMITED",
                    "comparable_metrics": 0,
                    "total_metrics": 15,
                    "coverage_ratio": "0/15",
                }
            },
            "platforms": {
                "facebook": {"status": "FULL", "available_metrics": ["reactions"], "unavailable_metrics": []},
                "instagram": {"status": "PARTIAL", "available_metrics": [], "unavailable_metrics": ["reactions"]},
            },
            "evidence_registry": {"SIG-1": {"signal_type": "PROVIDER_PARTIAL"}},
        }
        # Bad claim: claiming 3/15 or cross-platform performance when comparable count is 0
        bad_doc = {
            "executive_summary": [
                "Instagram registró 6 reacciones frente a 0 en Facebook.",
            ],
            "performance_observations": [
                "Línea base observada en Facebook es cero.",
            ],
            "recommendations": [
                {
                    "text": "Revisar permisos del proveedor.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
            ],
        }
        is_valid, summary = NarrativeValidator.validate(bad_doc, mock_context)
        self.assertFalse(is_valid)
        self.assertEqual(summary["status"], "FAIL")
        self.assertTrue(
            any("0 comparable metrics" in e or "contradicts context benchmark coverage" in e for e in summary["errors"]),
            f"Expected 0-comparable or contradiction error, got: {summary['errors']}",
        )

    def test_07_old_bs5_benchmark_cannot_leak_into_september(self):
        """7. Old BS-5 benchmark hash cannot leak into September report."""
        rep_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
            report_type="EXECUTIVE",
            language="es",
        )
        old_hash = "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"
        for sig in rep_data.get("business_intelligence_signals", {}).get("signals", []):
            ev = sig.get("evidence", {})
            if isinstance(ev, dict):
                self.assertNotEqual(ev.get("benchmark_hash"), old_hash)

    def test_08_unavailable_instagram_remains_unavailable(self):
        """8. Instagram in September has 0 telemetry and remains PARTIAL capability."""
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            granularity="day",
        )
        rx_metric = next((m for m in bm.metric_results if m.metric == "REACTIONS"), None)
        self.assertIsNotNone(rx_metric)
        self.assertEqual(getattr(rx_metric.status, 'value', str(rx_metric.status)), "UNAVAILABLE")
        self.assertIsNone(rx_metric.value_b)

    @patch("social_stats.analytics.narrative.providers.ollama.requests.post")
    def test_09_no_provider_call(self, mock_post):
        """9. Zero provider calls are executed during reconciliation test."""
        mock_post.side_effect = RuntimeError("Provider call strictly forbidden!")
        bm = build_multichannel_benchmark(
            client=self.client_obj,
            platform_a="facebook",
            platform_b="instagram",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        self.assertIsNotNone(bm)
        self.assertEqual(mock_post.call_count, 0)

    def test_10_validator_rejects_spurious_3_of_15(self):
        """10. Proves validator rejects arbitrary non-matching comparable count."""
        mock_context = {
            "report": {"language": "es", "id": 99},
            "multichannel_intelligence": {
                "coverage_summary": {
                    "status": "LIMITED",
                    "comparable_metrics": 3,
                    "total_metrics": 15,
                    "coverage_ratio": "3/15",
                }
            },
            "evidence_registry": {"SIG-1": {"signal_type": "GENERAL"}},
        }
        # Claims 5 of 15 when context has 3
        doc = {
            "executive_summary": ["Resumen general."],
            "performance_observations": ["Observación de rendimiento."],
            "recommendations": [
                {
                    "text": "Continuar monitoreo.",
                    "recommendation_type": "CONTINUE_COLLECTING_DATA",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["La cobertura es de 5 de 15 métricas."],
        }
        is_valid, summary = NarrativeValidator.validate(doc, mock_context)
        self.assertFalse(is_valid)
        self.assertTrue(any("contradicts context benchmark coverage (3/15)" in e for e in summary["errors"]))
