"""
BS-6E.2C: Dynamic Multichannel Coverage Contract Calibration Test Suite.

Verifies:
1. Pipeline version bumped to bs6a-v7.
2. Prompt version bumped to bs5e-prompt-v6.
3. Context builder includes multichannel_comparison_contract.
4. Multichannel contract extracts correct October ratios (3/15, LIMITED).
5. Limitations section interpolates dynamic counts.
6. Canonical fact FACT-MC-1 interpolates dynamic counts.
7. System prompt & few-shot templates are clean of hardcoded ratio literals.
8. User prompt injects dynamic limitation disclosure when must_disclose_ratio is True.
9. User prompt omits disclosure when multichannel coverage is complete.
10. Validator passes when narrative preserves dynamic ratio ("3 de 15").
11. Validator fails when ratio is omitted despite qualitative paraphrase (Narrative #8 failure mode).
12. Validator fails when ratio contradicts contract ("4 de 15").
13. Validator evaluates synthetic generic ratios dynamically (e.g. 4/12 context accepts "4 de 12", rejects "3 de 15").
14. Execution identity differs between bs6a-v6 and bs6a-v7.
15. Reusable October ExecutiveReport #5 retains canonical source hash.
"""

from datetime import date
from unittest.mock import MagicMock
from django.test import TestCase

from social_stats.models import Client, ExecutiveReport
from social_stats.analytics.automation.constants import PIPELINE_VERSION
from social_stats.analytics.automation.identity import compute_execution_identity
from social_stats.analytics.narrative.schemas import PROMPT_VERSION, PROMPT_VERSION_V6
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.prompts import (
    get_system_prompt,
    build_user_prompt,
)
from social_stats.analytics.narrative.validator import NarrativeValidator


class TestDynamicMultichannelCoverageContract(TestCase):
    """BS-6E.2C dynamic multichannel coverage contract calibration."""

    @classmethod
    def setUpTestData(cls):
        # Create test client
        cls.client_obj = Client.objects.create(
            name="Test Client",
            timezone="America/New_York",
        )
        # Create mock report with realistic October multichannel data matching Report #5
        cls.report_data_limited = {
            "kpis": {"impressions": 10000, "engagements": 500},
            "platforms": {
                "instagram": {"posts": 10, "interactions": 300},
                "facebook": {"posts": 5, "interactions": 200},
            },
            "multichannel_intelligence": {
                "has_multichannel_data": True,
                "coverage_summary": {
                    "status": "LIMITED",
                    "comparable_metrics": 3,
                    "total_metrics": 15,
                    "coverage_ratio": "3/15",
                    "rankable_metrics": 2,
                    "non_comparable_metrics": 2,
                    "unavailable_metrics": 10,
                },
                "coverage": {
                    "status": "LIMITED",
                    "comparable_metrics": 3,
                    "total_metrics": 15,
                    "coverage_ratio": "3/15",
                },
                "limitations": [
                    {
                        "type": "PROVIDER_PARTIAL",
                        "platform": "instagram",
                        "title": "Capacidad Parcial de Proveedor (Instagram)",
                        "description": "Instagram opera bajo capacidad analítica PARCIAL.",
                    },
                    {
                        "type": "METRIC_NOT_EQUIVALENT",
                        "platform": "facebook:instagram",
                        "title": "Métricas No Comparables",
                        "description": "Métricas no comparables entre plataformas.",
                    }
                ],
                "platform_comparisons": [
                    {
                        "metric": "REACTIONS",
                        "category": "PERFORMANCE",
                        "platform_values": {"facebook": 0.0, "instagram": 6.0},
                    }
                ],
                "multichannel_complete": False,
            },
        }
        cls.report_limited = ExecutiveReport.objects.create(
            client=cls.client_obj,
            title="October 2026 Executive Report",
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            report_data=cls.report_data_limited,
            source_hash="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            status="GENERATED",
        )

        cls.base_valid_narrative = {
            "executive_summary": ["Rendimiento multicanal con cobertura parcial en octubre."],
            "performance_observations": ["Instagram registró actividad frente a Facebook durante el periodo analizado."],
            "recommendations": [
                {
                    "text": "Estandarizar recoleccion de metricas en todos los canales.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["LIMITATION-CROSS-PLATFORM-PARTIAL"]
                }
            ],
            "limitations": [
                "La comparacion entre plataformas es limitada: solo 3 de 15 metricas canonicas son comparables en este periodo.",
                "Datos de Instagram parcialmente disponibles."
            ]
        }

    def test_pipeline_version_is_bs6a_v7(self):
        """1. Pipeline version is explicitly bs6a-v7."""
        self.assertEqual(PIPELINE_VERSION, "bs6a-v7")

    def test_prompt_version_is_bs5e_prompt_v6(self):
        """2. Prompt version is explicitly bs5e-prompt-v6."""
        self.assertEqual(PROMPT_VERSION, "bs5e-prompt-v6")
        self.assertEqual(PROMPT_VERSION_V6, "bs5e-prompt-v6")

    def test_context_includes_multichannel_comparison_contract(self):
        """3. build_grounded_narrative_context populates multichannel_comparison_contract."""
        ctx = build_grounded_narrative_context(self.report_limited)
        self.assertIn("multichannel_comparison_contract", ctx)
        contract = ctx["multichannel_comparison_contract"]
        self.assertIsInstance(contract, dict)

    def test_multichannel_contract_extracts_correct_october_ratios(self):
        """4. Contract reflects 3/15 coverage, status LIMITED, must_disclose_ratio True."""
        ctx = build_grounded_narrative_context(self.report_limited)
        contract = ctx["multichannel_comparison_contract"]
        self.assertEqual(contract["comparable_metrics_count"], 3)
        self.assertEqual(contract["total_canonical_metrics"], 15)
        self.assertEqual(contract["coverage_ratio"], "3/15")
        self.assertFalse(contract["multichannel_complete"])
        self.assertTrue(contract["must_disclose_ratio"])

        cov = ctx.get("multichannel_intelligence", {}).get("coverage_summary", {})
        self.assertEqual(cov.get("status"), "LIMITED")
        self.assertEqual(cov.get("rankable_metrics"), 2)

    def test_limitation_entry_interpolates_dynamic_counts(self):
        """5. Context limitation entry has dynamic counts interpolated."""
        ctx = build_grounded_narrative_context(self.report_limited)
        lims = ctx.get("limitations", [])
        mc_lim = next((l for l in lims if l.get("ref_id") == "LIMITATION-CROSS-PLATFORM-PARTIAL"), None)
        self.assertIsNotNone(mc_lim)
        desc = mc_lim.get("description", "")
        self.assertIn("3 of 15", desc)

    def test_fact_mc1_interpolates_dynamic_counts(self):
        """6. Canonical fact FACT-MC-1 has dynamic counts interpolated."""
        ctx = build_grounded_narrative_context(self.report_limited)
        approved_facts = ctx.get("approved_facts", [])
        fact_1 = next((f for f in approved_facts if f.get("fact_id") == "FACT-MC-1"), None)
        self.assertIsNotNone(fact_1)
        self.assertIn("3 de 15", fact_1.get("text_es", ""))

    def test_prompt_templates_clean_of_hardcoded_ratios(self):
        """7. Static prompt template contains no literal ratios."""
        forbidden_literals = ["3 de 15", "3/15", "6 reactions", "6 reacciones"]
        for lang in ["es", "en"]:
            sys_prompt = get_system_prompt(language=lang)
            for lit in forbidden_literals:
                self.assertNotIn(lit, sys_prompt, f"Found '{lit}' in system prompt ({lang})")

    def test_user_prompt_injects_dynamic_disclosure_when_required(self):
        """8. User prompt injects dynamic limitation disclosure when must_disclose_ratio is True."""
        ctx = build_grounded_narrative_context(self.report_limited)
        user_prompt = build_user_prompt(ctx)
        self.assertIn("REQUIRED MULTICHANNEL LIMITATION DISCLOSURE", user_prompt)
        self.assertIn("3 de 15", user_prompt)
        self.assertIn("3/15", user_prompt)
        self.assertIn("MANDATORY LIMITATION PRESERVATION RULE", user_prompt)

    def test_user_prompt_omits_disclosure_when_coverage_complete(self):
        """9. User prompt omits limitation disclosure when coverage is complete."""
        report_complete_data = {
            "kpis": {},
            "platforms": {},
            "multichannel_intelligence": {
                "has_multichannel_data": True,
                "multichannel_complete": True,
                "coverage_summary": {
                    "status": "COMPLETE",
                    "comparable_metrics": 15,
                    "total_metrics": 15,
                    "coverage_ratio": "15/15",
                },
                "status": "COMPLETE",
                "comparable_metrics": ["m" + str(i) for i in range(15)],
                "total_canonical_metrics": 15,
                "coverage_ratio": "15/15",
                "rankable_metrics": ["m" + str(i) for i in range(15)],
            }
        }
        rep_complete = ExecutiveReport.objects.create(
            client=self.client_obj,
            title="Complete Coverage Report",
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 30),
            report_data=report_complete_data,
            source_hash="synthetic_complete_hash",
            status="GENERATED",
        )
        ctx = build_grounded_narrative_context(rep_complete)
        self.assertFalse(ctx["multichannel_comparison_contract"]["must_disclose_ratio"])
        user_prompt = build_user_prompt(ctx)
        self.assertNotIn("REQUIRED MULTICHANNEL LIMITATION DISCLOSURE", user_prompt)

    def test_validator_passes_when_narrative_preserves_dynamic_ratio(self):
        """10. Validator passes when narrative preserves dynamic ratio (3 de 15)."""
        ctx = build_grounded_narrative_context(self.report_limited)
        is_valid, summary = NarrativeValidator.validate(self.base_valid_narrative, ctx)
        self.assertTrue(is_valid, f"Validation failed unexpectedly: {summary.get('errors')}")

    def test_validator_fails_when_ratio_omitted_despite_paraphrase(self):
        """11. Validator fails when ratio token is omitted (Narrative #8 reproduction)."""
        ctx = build_grounded_narrative_context(self.report_limited)
        narrative_missing_ratio = dict(self.base_valid_narrative)
        narrative_missing_ratio["limitations"] = [
            "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
            "Datos de Instagram parcialmente disponibles."
        ]
        is_valid, summary = NarrativeValidator.validate(narrative_missing_ratio, ctx)
        self.assertFalse(is_valid)
        self.assertFalse(summary["results"]["multichannel_safety"])
        self.assertTrue(any("Limitation preservation lock failed" in e for e in summary.get("errors", [])))

    def test_validator_fails_when_ratio_contradicts_contract(self):
        """12. Validator fails when narrative contains contradictory ratio (e.g. 4 de 15)."""
        ctx = build_grounded_narrative_context(self.report_limited)
        narrative_wrong_ratio = dict(self.base_valid_narrative)
        narrative_wrong_ratio["limitations"] = [
            "La comparación entre plataformas es limitada: solo 4 de 15 métricas canónicas son comparables.",
            "Datos de Instagram parcialmente disponibles."
        ]
        is_valid, summary = NarrativeValidator.validate(narrative_wrong_ratio, ctx)
        self.assertFalse(is_valid)
        self.assertTrue(any("Limitation preservation lock failed" in e and "contradicts context benchmark" in e for e in summary.get("errors", [])))

    def test_validator_evaluates_synthetic_generic_ratios_dynamically(self):
        """13. Validator evaluates synthetic generic context (4/12): accepts 4 de 12, rejects 3 de 15."""
        synthetic_ctx = build_grounded_narrative_context(self.report_limited)
        synthetic_ctx["multichannel_comparison_contract"] = {
            "status": "LIMITED",
            "comparable_metrics_count": 4,
            "total_canonical_metrics": 12,
            "coverage_ratio": "4/12",
            "rankable_metrics_count": 3,
            "multichannel_complete": False,
            "must_disclose_ratio": True,
        }
        if "multichannel_intelligence" not in synthetic_ctx:
            synthetic_ctx["multichannel_intelligence"] = {}
        synthetic_ctx["multichannel_intelligence"]["coverage_summary"] = {
            "status": "LIMITED",
            "comparable_metrics": 4,
            "total_metrics": 12,
            "coverage_ratio": "4/12",
        }

        # 4 de 12 narrative should PASS
        narrative_4_12 = dict(self.base_valid_narrative)
        narrative_4_12["limitations"] = [
            "La comparación entre plataformas es limitada: 4 de 12 métricas canónicas son comparables.",
            "Datos de Instagram parcialmente disponibles."
        ]
        res_4_12, sum_4_12 = NarrativeValidator.validate(narrative_4_12, synthetic_ctx)
        self.assertTrue(res_4_12, f"Synthetic 4/12 failed unexpectedly: {sum_4_12.get('errors')}")

        # 3 de 15 narrative against 4/12 context should FAIL
        res_3_15, sum_3_15 = NarrativeValidator.validate(self.base_valid_narrative, synthetic_ctx)
        self.assertFalse(res_3_15)
        self.assertTrue(any("Limitation preservation lock failed" in e for e in sum_3_15.get("errors", [])))

    def test_execution_identity_differs_between_bs6a_v6_and_bs6a_v7(self):
        """14. Execution identity differs between bs6a-v6 and bs6a-v7."""
        id_v6 = compute_execution_identity(3, date(2026, 10, 1), date(2026, 10, 31), "bs6a-v6")
        id_v7 = compute_execution_identity(3, date(2026, 10, 1), date(2026, 10, 31), "bs6a-v7")
        self.assertNotEqual(id_v6, id_v7)
        self.assertEqual(id_v6, "14a1e02803da929b6e7dbac2e05bdeb7fe2c1452d52952934d0795ad7630513a")

    def test_reusable_october_report_retains_canonical_source_hash(self):
        """15. ExecutiveReport #5 retains canonical source hash."""
        self.assertEqual(
            self.report_limited.source_hash,
            "dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77"
        )
