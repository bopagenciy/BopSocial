"""
BOP SOCIAL — PHASE BS-6D.1B
ARTIFACT REUSE INTEGRITY & ZERO-LEAKAGE REGENERATION PREFLIGHT TEST MATRIX

Validates:
1. Strict-contained signal included
2. Left-overlap signal excluded
3. Right-overlap signal excluded
4. Outside signal excluded
5. Exact-boundary signal included
6. Old BS-5 signals cannot enter September report
7. Report #3 source identity fails current reuse
8. Correct report source identity passes reuse
9. Narrative #3 context identity fails current reuse
10. Correct context identity passes reuse
11. 0/15 vs 3/15 rejected by validator
12. 0 comparable + cross-platform performance claim rejected by validator
13. Wrong-period evidence reference rejected by validator
14. Clean September context contains no historical evidence
15. Dry-run plans CREATE_NEW report and narrative
16. Zero provider calls occur
"""
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    SyncLog,
    BusinessSignal,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation.identity import (
    get_deterministic_report_source_hash,
    verify_executive_report_reuse,
    verify_executive_narrative_reuse,
)
from social_stats.analytics.automation.eligibility import (
    evaluate_intelligence_automation_eligibility,
)
from social_stats.analytics.automation.orchestrator import (
    preview_intelligence_automation,
)
from social_stats.analytics.reporting.builder import (
    build_executive_report_data,
)
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.validator import (
    NarrativeValidator,
)


class ArtifactReuseIntegrityTests(TestCase):
    """
    Complete 16-point test matrix enforcing BS-6D.1B artifact reuse integrity,
    deterministic identity verification, and period containment.
    """

    def setUp(self):
        self.p_start = date(2026, 9, 1)
        self.p_end = date(2026, 9, 30)

        self.client_obj, _ = Client.objects.get_or_create(
            id=3,
            defaults={
                "name": "Pilot Agency",
                "company": "Bop Agencia",
                "is_active": True,
                "email": "pilot_client3_integrity@example.com",
            },
        )

        # Baseline telemetry to ensure eligibility passes in test db
        PlatformCredential.objects.get_or_create(
            client=self.client_obj,
            platform="facebook",
            defaults={
                "is_active": True,
                "access_token": "token_fb_123",
                "expires_at": timezone.now() + timedelta(days=60),
            },
        )
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=1),
        )
        SocialMetricSnapshot.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=100.0,
            bucket_period="DAY",
            bucket_timestamp=timezone.now() - timedelta(hours=2),
            dimensions_hash="snap_hash_test_1b",
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=100.0,
            period="day",
            period_start=self.p_start,
        )
        IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={
                "enabled": True,
                "reporting_frequency": "MONTHLY",
                "generate_report": True,
                "generate_narrative": True,
                "minimum_period_coverage_percent": 0,
                "max_data_staleness_hours": 24,
            },
        )

    # 1. Strict-contained signal included
    def test_01_strict_contained_signal_included(self):
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook",
            signal_type="CONTENT_FORMAT_SHIFT",
            period_start=date(2026, 9, 5),
            period_end=date(2026, 9, 20),
            sample_size=10,
            signal_identity="contained_sig_123",
        )
        qs = BusinessSignal.objects.filter(
            client=self.client_obj,
            period_start__gte=self.p_start,
            period_end__lte=self.p_end,
        )
        self.assertIn(sig, qs)

    # 2. Left-overlap signal excluded
    def test_02_left_overlap_signal_excluded(self):
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook",
            signal_type="CONTENT_FORMAT_SHIFT",
            period_start=date(2026, 8, 25),
            period_end=date(2026, 9, 5),
            sample_size=10,
            signal_identity="left_overlap_sig_123",
        )
        qs = BusinessSignal.objects.filter(
            client=self.client_obj,
            period_start__gte=self.p_start,
            period_end__lte=self.p_end,
        )
        self.assertNotIn(sig, qs)

    # 3. Right-overlap signal excluded
    def test_03_right_overlap_signal_excluded(self):
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook",
            signal_type="CONTENT_FORMAT_SHIFT",
            period_start=date(2026, 9, 25),
            period_end=date(2026, 10, 5),
            sample_size=10,
            signal_identity="right_overlap_sig_123",
        )
        qs = BusinessSignal.objects.filter(
            client=self.client_obj,
            period_start__gte=self.p_start,
            period_end__lte=self.p_end,
        )
        self.assertNotIn(sig, qs)

    # 4. Outside signal excluded
    def test_04_outside_signal_excluded(self):
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook",
            signal_type="CONTENT_FORMAT_SHIFT",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            sample_size=10,
            signal_identity="outside_sig_123",
        )
        qs = BusinessSignal.objects.filter(
            client=self.client_obj,
            period_start__gte=self.p_start,
            period_end__lte=self.p_end,
        )
        self.assertNotIn(sig, qs)

    # 5. Exact-boundary signal included
    def test_05_exact_boundary_signal_included(self):
        sig = BusinessSignal.objects.create(
            client=self.client_obj,
            platform="facebook",
            signal_type="CONTENT_FORMAT_SHIFT",
            period_start=self.p_start,
            period_end=self.p_end,
            sample_size=10,
            signal_identity="exact_boundary_sig_123",
        )
        qs = BusinessSignal.objects.filter(
            client=self.client_obj,
            period_start__gte=self.p_start,
            period_end__lte=self.p_end,
        )
        self.assertIn(sig, qs)

    # 6. Old BS-5 signals cannot enter September report
    def test_06_old_bs5_signals_cannot_enter_september_report(self):
        # Create an overlapping October BS-5 signal
        BusinessSignal.objects.create(
            id=999,
            client=self.client_obj,
            platform="facebook:instagram",
            signal_type="AUDIENCE_SIZE_DIFFERENCE",
            period_start=date(2026, 9, 22),
            period_end=date(2026, 10, 22),
            sample_size=10,
            signal_identity="bs5_october_sig_leak",
        )
        report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.p_start,
            date_to=self.p_end,
            language="es",
        )
        signals_section = report_data.get("business_intelligence_signals", {})
        sig_list = signals_section.get("signals", []) if isinstance(signals_section, dict) else signals_section
        attached_ids = [s.get("id") for s in sig_list]
        self.assertNotIn(999, attached_ids)

    # 7. Report #3 source identity fails current reuse
    def test_07_report3_source_identity_fails_current_reuse(self):
        r3 = ExecutiveReport.objects.create(
            id=9993,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash="b944a480ddc2cf986a1db68ee463bc303d389831841a720cbb7105b7ee8f3b44",
            title="Contaminated Historical Report",
            language="es",
        )
        is_reusable, reason, expected_hash = verify_executive_report_reuse(
            r3, self.client_obj.id, self.p_start, self.p_end
        )
        self.assertFalse(is_reusable)
        self.assertIn("SOURCE_HASH_MISMATCH", reason)

    # 8. Correct report source identity passes reuse
    def test_08_correct_report_source_identity_passes_reuse(self):
        expected_hash = get_deterministic_report_source_hash(
            self.client_obj.id, self.p_start, self.p_end
        )
        clean_rep = ExecutiveReport(
            id=9991,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash=expected_hash,
            language="es",
        )
        is_reusable, reason, exp = verify_executive_report_reuse(
            clean_rep, self.client_obj.id, self.p_start, self.p_end
        )
        self.assertTrue(is_reusable)
        self.assertEqual(reason, "REUSABLE")

    # 9. Narrative #3 context identity fails current reuse
    def test_09_narrative3_context_identity_fails_current_reuse(self):
        r3 = ExecutiveReport.objects.create(
            id=9994,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash="b944a480ddc2cf986a1db68ee463bc303d389831841a720cbb7105b7ee8f3b44",
            title="Report 3",
            language="es",
        )
        n3 = ExecutiveNarrative.objects.create(
            id=9994,
            client=self.client_obj,
            executive_report=r3,
            status="VALIDATED",
            source_hash="b944a480ddc2cf986a1db68ee463bc303d389831841a720cbb7105b7ee8f3b44",
            context_hash="d1b28c8a784148bd735e98b165b2bd8db6683a9240ddb4a7d68e22acde7bb6f1",
        )
        is_reusable, reason, _ = verify_executive_narrative_reuse(
            n3, r3, self.client_obj.id, self.p_start, self.p_end
        )
        self.assertFalse(is_reusable)

    # 10. Correct context identity passes reuse
    def test_10_correct_context_identity_passes_reuse(self):
        expected_src_hash = get_deterministic_report_source_hash(
            self.client_obj.id, self.p_start, self.p_end
        )
        rep_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.p_start,
            date_to=self.p_end,
            language="es",
        )
        clean_rep = ExecutiveReport(
            id=9992,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash=expected_src_hash,
            report_data=rep_data,
            language="es",
        )
        clean_ctx = build_grounded_narrative_context(clean_rep)
        clean_ctx_hash = compute_context_hash(clean_ctx)

        clean_narrative = ExecutiveNarrative(
            id=9992,
            client=self.client_obj,
            executive_report=clean_rep,
            status="VALIDATED",
            source_hash=expected_src_hash,
            context_hash=clean_ctx_hash,
        )
        is_reusable, reason, _ = verify_executive_narrative_reuse(
            clean_narrative, clean_rep, self.client_obj.id, self.p_start, self.p_end
        )
        self.assertTrue(is_reusable)
        self.assertEqual(reason, "REUSABLE")

    # 11. 0/15 vs 3/15 rejected by validator
    def test_11_contradictory_ratio_rejected(self):
        context = {
            "multichannel_intelligence": {
                "coverage": {"comparable_metrics": 0, "total_metrics": 15, "coverage_ratio": "0/15"},
                "coverage_summary": {"comparable_metrics": 0, "total_metrics": 15, "coverage_ratio": "0/15"},
            },
            "evidence_registry": {},
            "report": {"period_start": "2026-09-01", "period_end": "2026-09-30"},
        }
        bad_narrative = {
            "executive_summary": ["Resumen general del periodo."],
            "performance_observations": ["Observación válida del periodo."],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son comparables."
            ],
            "recommendations": [],
        }
        is_valid, summary = NarrativeValidator.validate(bad_narrative, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Limitation preservation lock failed" in e for e in summary["errors"]))

    # 12. 0 comparable + cross-platform performance claim rejected by validator
    def test_12_zero_comparable_cross_platform_claim_rejected(self):
        context = {
            "multichannel_intelligence": {
                "coverage": {"comparable_metrics": 0, "total_metrics": 15, "coverage_ratio": "0/15"},
                "coverage_summary": {"comparable_metrics": 0, "total_metrics": 15, "coverage_ratio": "0/15"},
            },
            "evidence_registry": {},
            "report": {"period_start": "2026-09-01", "period_end": "2026-09-30"},
        }
        bad_narrative = {
            "executive_summary": [
                "Instagram registró 6 reacciones frente a 0 en Facebook."
            ],
            "performance_observations": ["Observación de rendimiento."],
            "limitations": ["Sin comparabilidad multicanal."],
            "recommendations": [],
        }
        is_valid, summary = NarrativeValidator.validate(bad_narrative, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Comparability lock failed" in e for e in summary["errors"]))

    # 13. Wrong-period evidence reference rejected by validator
    def test_13_wrong_period_evidence_reference_rejected(self):
        context = {
            "multichannel_intelligence": {
                "coverage": {"comparable_metrics": 0, "total_metrics": 15, "coverage_ratio": "0/15"},
            },
            "evidence_registry": {
                "MC-SIG-7": {
                    "type": "BUSINESS_SIGNAL",
                    "period_start": "2026-09-22",
                    "period_end": "2026-10-22",
                    "confidence": "HIGH",
                }
            },
            "report": {"period_start": "2026-09-01", "period_end": "2026-09-30"},
        }
        narrative_with_wrong_period_ref = {
            "executive_summary": ["Resumen regular sin comparaciones cruzadas."],
            "performance_observations": ["Observación regular de periodo."],
            "limitations": ["Cobertura cero."],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["MC-SIG-7"],
                }
            ],
        }
        is_valid, summary = NarrativeValidator.validate(narrative_with_wrong_period_ref, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Evidence period mismatch failed" in e for e in summary["errors"]))

    # 14. Clean September context contains no historical evidence
    def test_14_clean_september_context_contains_no_historical_evidence(self):
        rep_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.p_start,
            date_to=self.p_end,
            language="es",
        )
        rep = ExecutiveReport(
            id=9995,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash=rep_data["metadata"]["source_hash"],
            report_data=rep_data,
            language="es",
        )
        clean_context = build_grounded_narrative_context(rep)
        context_json = json.dumps(clean_context)

        forbidden_terms = [
            "3/15", "3 de 15", "50.0", "20.0", "MC-SIG-7", "MC-SIG-8",
            "CROSS_PLATFORM_METRIC_NON_COMPARABLE", "AUDIENCE_SIZE_DIFFERENCE",
            "PLATFORM_METRIC_OUTPERFORMANCE", "2026-10-22"
        ]
        for term in forbidden_terms:
            self.assertEqual(context_json.count(term), 0, f"Found contaminated term: {term}")

    # 15. Dry-run plans CREATE_NEW report and narrative
    def test_15_dry_run_plans_create_new_report_and_narrative(self):
        # Create an existing report and narrative with stale source hash
        stale_rep = ExecutiveReport.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash="stale_historical_hash_9999",
            title="Stale Report",
            language="es",
        )
        ExecutiveNarrative.objects.create(
            client=self.client_obj,
            executive_report=stale_rep,
            status="VALIDATED",
            source_hash="stale_historical_hash_9999",
            context_hash="stale_context_hash_9999",
        )
        preview = preview_intelligence_automation(
            client_id=self.client_obj.id,
            period_start=self.p_start,
            period_end=self.p_end,
        )
        self.assertTrue(preview["eligible"])
        self.assertIn("REPORT_CHECK", preview["planned_stages"])
        self.assertIn("NARRATIVE_CHECK", preview["planned_stages"])
        self.assertIn("CREATE_NEW", preview["reuse_decisions"]["report"])
        self.assertIn("CREATE_NEW", preview["reuse_decisions"]["narrative"])

    # 16. Zero provider calls occur
    def test_16_zero_provider_calls_occur(self):
        with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
            preview = preview_intelligence_automation(
                client_id=self.client_obj.id,
                period_start=self.p_start,
                period_end=self.p_end,
            )
            self.assertEqual(mock_post.call_count, 0)
            self.assertEqual(mock_get.call_count, 0)
