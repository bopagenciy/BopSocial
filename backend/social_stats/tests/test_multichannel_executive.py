"""
BS-5D Test Suite: Multichannel Executive Intelligence & Cross-Platform Narrative Integration.

Tests:
- AX: Multichannel intelligence section present with schema bs5d-multichannel-executive-v1
- AY: FOLLOWERS_TOTAL non-performance language lock (audience volume only, NO_WINNER)
- AZ: Zero-baseline reactions outperformance (relative_delta=None, forbids fake %, winner=instagram)
- BA: Data coverage limitation surfaces with status LIMITED (3/15 comparable, REVIEW_PROVIDER_PERMISSIONS)
- BB: Non-comparable metrics (SAVES, VIDEO_VIEWS) explicitly marked as semantic limitations
- BC: Strictly NO overall platform winner, composite score, or best-platform claim
- BD: Deterministic executive takeaway engine ordered:
      1. DATA_COVERAGE_WARNING
      2. METRIC_ADVANTAGE
      3. AUDIENCE_CONTEXT
      4. SEMANTIC_COMPARISON_LIMITATION
- BE: Grounded narrative context integration (schema bs4h-context-v2, multichannel_intelligence present)
- BF: Stable evidence refs MC-SIG-6, MC-SIG-7, MC-SIG-8, MC-SIG-9 in evidence registry
- BG: Context hash determinism and change sensitivity
- BH: Source hash determinism and change sensitivity
- BI: Stale signal handling against benchmark hash
- BJ: Narrative validator metric lock
- BK: Narrative validator comparability lock (rejects claims on SAVES, VIDEO_VIEWS)
- BL: Narrative validator zero-baseline lock (rejects fake % claims)
- BM: Narrative validator overall-winner lock (strictly rejects overall winner)
- BN: Clean grounded multichannel narrative passes validation
- BO: Bilingual ES/EN report and takeaways support
- BP: Tenant isolation and zero writes
"""
from datetime import date, timedelta
from decimal import Decimal
import json

from django.contrib.auth.models import User
from django.test import TestCase

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    BusinessSignal,
    ExecutiveReport,
)
from social_stats.analytics.reporting.builder import (
    MULTICHANNEL_EXECUTIVE_SCHEMA_VERSION,
    TEMPLATE_VERSION,
    build_executive_report_data,
    compute_source_hash,
)
from social_stats.analytics.reporting.templates import get_report_strings
from social_stats.analytics.narrative.schemas import (
    CONTEXT_SCHEMA_VERSION,
    PROMPT_VERSION,
)
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.validator import NarrativeValidator


class MultichannelExecutiveIntelligenceTests(TestCase):
    """Exhaustive test suite for BS-5D Multichannel Executive Intelligence."""

    def setUp(self):
        # Create test client
        self.client_obj = Client.objects.create(
            name="Test Agency Client",
            company="Bop Agencia Staging",
            email="test_agency_staging@example.com",
            is_active=True,
        )
        self.other_client = Client.objects.create(
            name="Other Client",
            company="Other Org",
            email="other_agency_staging@example.com",
            is_active=True,
        )

        self.start_date = date(2026, 9, 22)
        self.end_date = date(2026, 10, 22)
        self.canonical_benchmark_hash = "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"

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

        # Create Rollups representing pilot baseline (FB 20 followers, 0 reactions, 0 comments; IG 50 followers, 6 reactions, 0 comments)
        # FB
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
        # IG
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

        # Canonical Multichannel Business Signals (IDs 6-9)
        self.sig6 = BusinessSignal.objects.create(
            id=6,
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="AUDIENCE_SIZE_DIFFERENCE",
            metric="FOLLOWERS_TOTAL",
            scope="multichannel",
            period_start=self.start_date,
            period_end=self.end_date,
            observed_value=Decimal("50.0"),
            baseline_value=Decimal("20.0"),
            absolute_delta=Decimal("-30.0"),
            relative_delta=Decimal("-60.0"),
            sample_size=6,
            confidence_level="HIGH",
            severity="INFO",
            is_actionable=False,
            signal_identity="4ec63b2d694607643cc58ade2db37d04afc998db88072fd8c05c9d8e997a4a0d",
            explanation_template="Instagram cuenta con 50.0 seguidores frente a 20.0 en Facebook (métrica de volumen de audiencia, no de rendimiento).",
            evidence={
                "metric": "FOLLOWERS_TOTAL",
                "winner": "NO_WINNER",
                "category": "AUDIENCE",
                "platform_a": "facebook",
                "platform_b": "instagram",
                "reason_code": "NON_RANKABLE_METRIC",
                "benchmark_hash": self.canonical_benchmark_hash,
                "delta_absolute": -30.0,
                "delta_relative": -60.0,
                "platform_values": {"facebook": 20.0, "instagram": 50.0},
            },
        )

        self.sig7 = BusinessSignal.objects.create(
            id=7,
            client=self.client_obj,
            platform="instagram",
            signal_type="PLATFORM_METRIC_OUTPERFORMANCE",
            metric="REACTIONS",
            scope="multichannel",
            period_start=self.start_date,
            period_end=self.end_date,
            observed_value=Decimal("6.0"),
            baseline_value=Decimal("0.0"),
            absolute_delta=Decimal("-6.0"),
            relative_delta=None,  # Zero baseline
            sample_size=71,
            confidence_level="HIGH",
            severity="POSITIVE",
            is_actionable=True,
            signal_identity="3fbc828c4354c7630e9a627ab21327bcded2e8aa0ac80bd542e7661402b1c14d",
            explanation_template="Instagram registró 6.0 reacciones frente a 0 en Facebook durante el período.",
            evidence={
                "metric": "REACTIONS",
                "winner": "PLATFORM_B",
                "category": "PERFORMANCE",
                "platform_a": "facebook",
                "platform_b": "instagram",
                "reason_code": "DIRECTLY_COMPARABLE",
                "zero_baseline": True,
                "benchmark_hash": self.canonical_benchmark_hash,
                "delta_absolute": -6.0,
                "delta_relative": None,
                "platform_values": {"facebook": 0.0, "instagram": 6.0},
                "winner_platform": "instagram",
                "baseline_platform": "facebook",
            },
        )

        self.sig8 = BusinessSignal.objects.create(
            id=8,
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="CROSS_PLATFORM_DATA_LIMITATION",
            metric="MULTIPLE",
            scope="multichannel",
            period_start=self.start_date,
            period_end=self.end_date,
            sample_size=15,
            confidence_level="HIGH",
            severity="WARNING",
            is_actionable=True,
            signal_identity="57c995a6aeb519ee26e7015a87c2e7d4377a1bbe584071d4a1ce5ec46e7ffe32",
            explanation_template="Limitación de datos entre plataformas: 12 de 15 métricas no están disponibles debido a capacidades parciales del proveedor (Instagram).",
            evidence={
                "category": "CAPABILITY",
                "total_metrics": 15,
                "comparable_metrics": 3,
                "coverage_ratio": "3/15",
                "benchmark_hash": self.canonical_benchmark_hash,
                "affected_metrics_count": 12,
            },
        )

        self.sig9 = BusinessSignal.objects.create(
            id=9,
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="CROSS_PLATFORM_METRIC_NON_COMPARABLE",
            metric="MULTIPLE",
            scope="multichannel",
            period_start=self.start_date,
            period_end=self.end_date,
            sample_size=2,
            confidence_level="HIGH",
            severity="INFO",
            is_actionable=False,
            signal_identity="f6e5e9965419ddac12d4a043e1092c61352dac207883bf9af0a9cd0d926e2d29",
            explanation_template="Métricas no comparables entre plataformas: SAVES, VIDEO_VIEWS tienen definiciones semánticas o de agregación estructuralmente dispares.",
            evidence={
                "count": 2,
                "category": "DATA_QUALITY",
                "benchmark_hash": self.canonical_benchmark_hash,
                "affected_metrics": ["SAVES", "VIDEO_VIEWS"],
            },
        )

        # Baseline single-platform executive report
        self.report = ExecutiveReport.objects.create(
            client=self.client_obj,
            report_type="EXECUTIVE",
            period_start=self.start_date,
            period_end=self.end_date,
            language="es",
            title="Informe Ejecutivo Staging",
            source_hash="staging_source_hash_initial",
            report_data={},
        )

    # ── Test AX: Multichannel Section in ExecutiveReport ─────────────────────
    def test_ax_multichannel_intelligence_section_present(self):
        """Test AX: Verify multichannel_intelligence section with schema bs5d-multichannel-executive-v1."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.assertIn("multichannel_intelligence", report_data)
        mc = report_data["multichannel_intelligence"]
        self.assertEqual(mc["schema_version"], MULTICHANNEL_EXECUTIVE_SCHEMA_VERSION)
        self.assertEqual(mc["schema_version"], "bs5d-multichannel-executive-v1")
        self.assertTrue(mc["has_multichannel_data"])
        self.assertIsNotNone(mc["benchmark_hash"])

    # ── Test AY: FOLLOWERS_TOTAL Non-Performance Lock ─────────────────────────
    def test_ay_followers_total_non_performance_language(self):
        """Test AY: Audience size difference is volume only, winner NO_WINNER, not performance superiority."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        fol_comp = next((c for c in mc["platform_comparisons"] if c["metric"] == "FOLLOWERS_TOTAL"), None)
        self.assertIsNotNone(fol_comp)
        self.assertEqual(fol_comp["winner"], "NO_WINNER")
        self.assertFalse(fol_comp["is_rankable"])
        self.assertIsNone(fol_comp["delta_relative"])
        self.assertIn("volumen", fol_comp["note"].lower())
        self.assertIn("no representa superioridad", fol_comp["note"].lower())

    # ── Test AZ: Reactions Outperformance with Zero Baseline ──────────────────
    def test_az_reactions_zero_baseline_outperformance(self):
        """Test AZ: REACTIONS outperformance has zero baseline, relative_delta=None, winner=instagram."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        reac_comp = next((c for c in mc["platform_comparisons"] if c["metric"] == "REACTIONS"), None)
        self.assertIsNotNone(reac_comp)
        self.assertEqual(reac_comp["winner"], "instagram")
        self.assertTrue(reac_comp["is_rankable"])
        self.assertEqual(reac_comp["delta_absolute"], -6.0)
        self.assertIsNone(reac_comp["delta_relative"])
        self.assertIn("línea base cero", reac_comp["note"].lower())

    # ── Test BA: Data Coverage Limitation ────────────────────────────────────
    def test_ba_data_coverage_limitation_surface(self):
        """Test BA: Coverage limitations (3/15) surface with status LIMITED and REVIEW_PROVIDER_PERMISSIONS."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        cov = mc["coverage_summary"]
        self.assertEqual(cov["total_metrics"], 15)
        self.assertEqual(cov["comparable_metrics"], 3)
        self.assertEqual(cov["coverage_ratio"], "3/15")
        self.assertEqual(cov["status"], "LIMITED")
        self.assertEqual(cov["unavailable_metrics"], 10)
        self.assertEqual(cov["non_comparable_metrics"], 2)
        self.assertEqual(cov["limited_or_noncomparable_metrics"], 12)
        self.assertEqual(mc["coverage"]["unavailable_metrics"], 10)
        self.assertEqual(mc["coverage"]["non_comparable_metrics"], 2)
        self.assertEqual(mc["coverage"]["limited_or_noncomparable_metrics"], 12)
        # Check takeaway
        t1 = mc["executive_takeaways"][0]
        self.assertEqual(t1["takeaway_type"], "DATA_COVERAGE_WARNING")
        self.assertEqual(t1["action_code"], "REVIEW_PROVIDER_PERMISSIONS")

    # ── Test BB: Non-Comparable Metrics Semantic Distinction ──────────────────
    def test_bb_non_comparable_metrics_semantic_limitations(self):
        """Test BB: SAVES, VIDEO_VIEWS are explicitly semantic limitations, not ties or zeros."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        lim_non_comp = next((l for l in mc["limitations"] if l["type"] == "METRIC_NOT_EQUIVALENT"), None)
        self.assertIsNotNone(lim_non_comp)
        self.assertIn("SAVES", lim_non_comp["affected_metrics"])
        self.assertIn("VIDEO_VIEWS", lim_non_comp["affected_metrics"])
        self.assertIn("no admiten una comparación directa", lim_non_comp["description"])

    # ── Test BC: Strictly No Overall Platform Winner ──────────────────────────
    def test_bc_strictly_no_overall_platform_winner(self):
        """Test BC: Strictly NO overall platform winner or composite score."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        self.assertIsNone(mc["overall_winner"])
        self.assertIn("disclaimer", mc)
        self.assertIn("No se declaran ganadores globales", mc["disclaimer"])

    # ── Test BD: Deterministic Takeaway Engine Ordering ──────────────────────
    def test_bd_deterministic_executive_takeaways_ordering(self):
        """Test BD: Takeaways ordered: 1. Limitations, 2. Outperformance, 3. Audience, 4. Non-comparable."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        takeaways = report_data["multichannel_intelligence"]["executive_takeaways"]
        self.assertEqual(len(takeaways), 4)
        self.assertEqual(takeaways[0]["takeaway_type"], "DATA_COVERAGE_WARNING")
        self.assertEqual(takeaways[1]["takeaway_type"], "METRIC_ADVANTAGE")
        self.assertEqual(takeaways[2]["takeaway_type"], "AUDIENCE_CONTEXT")
        self.assertEqual(takeaways[3]["takeaway_type"], "SEMANTIC_COMPARISON_LIMITATION")

    # ── Test BE: Grounded Narrative Context Integration ──────────────────────
    def test_be_grounded_narrative_context_integration(self):
        """Test BE: Context schema is bs4h-context-v2 and contains multichannel_intelligence."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        self.report.save()

        context = build_grounded_narrative_context(self.report)
        self.assertEqual(context["context_schema_version"], CONTEXT_SCHEMA_VERSION)
        self.assertEqual(context["context_schema_version"], "bs4h-context-v2")
        self.assertIn("multichannel_intelligence", context)
        self.assertIn("benchmark_hash", context["multichannel_intelligence"])

    # ── Test BF: Stable Evidence Refs ────────────────────────────────────────
    def test_bf_stable_evidence_refs(self):
        """Test BF: Stable evidence refs MC-SIG-6, MC-SIG-7, MC-SIG-8, MC-SIG-9 in evidence_registry."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        self.report.save()

        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        self.assertIn("MC-SIG-6", reg)
        self.assertIn("MC-SIG-7", reg)
        self.assertIn("MC-SIG-8", reg)
        self.assertIn("MC-SIG-9", reg)
        self.assertEqual(reg["MC-SIG-7"]["metric"], "REACTIONS")
        self.assertEqual(reg["MC-SIG-7"]["confidence"], "HIGH")

    # ── Test BG: Context Hash Determinism and Sensitivity ────────────────────
    def test_bg_context_hash_determinism_and_sensitivity(self):
        """Test BG: compute_context_hash is deterministic and sensitive to multichannel intelligence."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        self.report.save()

        ctx1 = build_grounded_narrative_context(self.report)
        ctx2 = build_grounded_narrative_context(self.report)
        hash1 = compute_context_hash(ctx1)
        hash2 = compute_context_hash(ctx2)
        self.assertEqual(hash1, hash2)

        # Mutate multichannel evidence
        ctx3 = build_grounded_narrative_context(self.report)
        ctx3["multichannel_intelligence"]["benchmark_hash"] = "altered_benchmark_hash_123"
        hash3 = compute_context_hash(ctx3)
        self.assertNotEqual(hash1, hash3)

    # ── Test BH: Source Hash Determinism and Sensitivity ─────────────────────
    def test_bh_source_hash_determinism_and_sensitivity(self):
        """Test BH: compute_source_hash alters deterministically when multichannel signals/benchmarks present."""
        hash_no_bm = compute_source_hash(
            client_id=self.client_obj.id,
            period_start=self.start_date,
            period_end=self.end_date,
            platform=None,
            language="es",
            template_version=TEMPLATE_VERSION,
            rollup_count=10,
            signal_identities=["sig_1", "sig_2"],
        )
        hash_with_bm = compute_source_hash(
            client_id=self.client_obj.id,
            period_start=self.start_date,
            period_end=self.end_date,
            platform=None,
            language="es",
            template_version=TEMPLATE_VERSION,
            rollup_count=10,
            signal_identities=["sig_1", "sig_2"],
            benchmark_hash=self.canonical_benchmark_hash,
        )
        self.assertNotEqual(hash_no_bm, hash_with_bm)

        # Idempotence
        hash_with_bm_again = compute_source_hash(
            client_id=self.client_obj.id,
            period_start=self.start_date,
            period_end=self.end_date,
            platform=None,
            language="es",
            template_version=TEMPLATE_VERSION,
            rollup_count=10,
            signal_identities=["sig_1", "sig_2"],
            benchmark_hash=self.canonical_benchmark_hash,
        )
        self.assertEqual(hash_with_bm, hash_with_bm_again)

    # ── Test BI: Stale Signal Handling ───────────────────────────────────────
    def test_bi_stale_signal_handling(self):
        """Test BI: Multichannel signals with mismatched benchmark hash are excluded as stale."""
        # Create stale signal
        BusinessSignal.objects.create(
            id=99,
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="PLATFORM_METRIC_OUTPERFORMANCE",
            metric="COMMENTS",
            scope="multichannel",
            period_start=self.start_date,
            period_end=self.end_date,
            signal_identity="stale_identity_12345",
            evidence={"benchmark_hash": "outdated_benchmark_hash_xyz"},
        )
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        mc = report_data["multichannel_intelligence"]
        # Stale COMMENTS outperformance should not be in platform_comparisons
        comm_comp = next((c for c in mc["platform_comparisons"] if c["metric"] == "COMMENTS"), None)
        self.assertEqual(comm_comp["winner"], "TIE")  # Still legitimate tie, not stale outperformance

    # ── Test BJ: Validator Metric Lock ───────────────────────────────────────
    def test_bj_validator_metric_lock(self):
        """Test BJ: Narrative claiming unavailable metric across platforms fails validation."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        context = build_grounded_narrative_context(self.report)

        bad_output = {
            "executive_summary": ["El engagement total aumentó fuertemente en Instagram frente a Facebook."],
            "performance_observations": ["Las interacciones totales crecieron un 20%."],
            "recommendations": [],
            "limitations": ["Instagram opera con permisos parciales."],
        }
        is_valid, report = NarrativeValidator.validate(bad_output, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Metric allowlist failed" in e for e in report["errors"]))

    # ── Test BK: Validator Comparability Lock ─────────────────────────────────
    def test_bk_validator_comparability_lock(self):
        """Test BK: Narrative claiming superiority on SAVES or VIDEO_VIEWS fails comparability lock."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        context = build_grounded_narrative_context(self.report)

        bad_output = {
            "executive_summary": ["Instagram superó a Facebook en guardados durante este período."],
            "performance_observations": ["Los guardados registraron un mejor desempeño."],
            "recommendations": [],
            "limitations": ["Datos parciales disponibles."],
        }
        is_valid, report = NarrativeValidator.validate(bad_output, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Comparability lock failed" in e for e in report["errors"]))

    # ── Test BL: Validator Zero-Baseline Lock ─────────────────────────────────
    def test_bl_validator_zero_baseline_lock(self):
        """Test BL: Narrative claiming percentage variation when baseline is zero fails validation."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        context = build_grounded_narrative_context(self.report)

        bad_output = {
            "executive_summary": ["Instagram obtuvo un incremento de 600% en reacciones frente a Facebook."],
            "performance_observations": ["El volumen fue superior."],
            "recommendations": [],
            "limitations": ["Cobertura acotada."],
        }
        is_valid, report = NarrativeValidator.validate(bad_output, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Zero-baseline lock failed" in e or "Fact lock failed" in e for e in report["errors"]))

    # ── Test BM: Validator Overall-Winner Lock ────────────────────────────────
    def test_bm_validator_overall_winner_lock(self):
        """Test BM: Narrative claiming overall platform winner strictly fails validation."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        context = build_grounded_narrative_context(self.report)

        bad_output = {
            "executive_summary": ["Instagram fue la plataforma ganadora en general este mes."],
            "performance_observations": ["Superó a los demás canales."],
            "recommendations": [],
            "limitations": ["Métricas parciales registradas."],
        }
        is_valid, report = NarrativeValidator.validate(bad_output, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Multichannel lock failed" in e for e in report["errors"]))

    # ── Test BN: Clean Grounded Narrative Passes ──────────────────────────────
    def test_bn_clean_grounded_multichannel_narrative_passes(self):
        """Test BN: Compliant grounded narrative citing MC-SIG-7 passes all gates."""
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.report.report_data = report_data
        self.report.save()
        context = build_grounded_narrative_context(self.report)

        clean_output = {
            "executive_summary": [
                "Los datos de este período muestran actividad acotada en las plataformas analizadas.",
                "Instagram registró 6 reacciones frente a 0 en Facebook."
            ],
            "performance_observations": [
                "Instagram cuenta con 50 seguidores frente a 20 en Facebook según la medición puntual."
            ],
            "recommendations": [
                {
                    "text": "Revisar el rendimiento en Instagram manteniendo la cadencia de publicación actual.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["MC-SIG-7"],
                }
            ],
            "limitations": [
                "Instagram opera bajo capacidad analítica parcial en métricas avanzadas."
            ],
        }
        is_valid, report = NarrativeValidator.validate(clean_output, context)
        self.assertTrue(is_valid, msg=f"Validation failed with errors: {report.get('errors')}")
        self.assertEqual(report["status"], "PASS")

    # ── Test BO: Bilingual Support ───────────────────────────────────────────
    def test_bo_bilingual_templates_es_and_en(self):
        """Test BO: Deterministic report strings in ES and EN render properly."""
        es_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        en_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="en",
        )
        self.assertEqual(es_data["multichannel_intelligence"]["coverage_summary"]["status_label"], "COBERTURA LIMITADA")
        self.assertEqual(en_data["multichannel_intelligence"]["coverage_summary"]["status_label"], "LIMITED COVERAGE")
        self.assertIn("No se declaran ganadores globales", es_data["multichannel_intelligence"]["disclaimer"])
        self.assertIn("Overall platform winners are strictly not declared", en_data["multichannel_intelligence"]["disclaimer"])

    # ── Test BP: Tenant Isolation and Zero Writes ────────────────────────────
    def test_bp_tenant_isolation_and_zero_writes(self):
        """Test BP: Cross-tenant data isolation and zero database writes."""
        initial_reports = ExecutiveReport.objects.count()
        initial_signals = BusinessSignal.objects.count()

        # Build report for client_obj
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.assertEqual(ExecutiveReport.objects.count(), initial_reports)
        self.assertEqual(BusinessSignal.objects.count(), initial_signals)

        # Other client with no rollups or signals should have 0 multichannel data
        other_report_data = build_executive_report_data(
            client_id=self.other_client.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )
        self.assertFalse(other_report_data["multichannel_intelligence"]["has_multichannel_data"])
        self.assertEqual(other_report_data["multichannel_intelligence"]["coverage_summary"]["comparable_metrics"], 0)
