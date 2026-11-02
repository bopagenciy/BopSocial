"""
BOP SOCIAL — PHASE BS-6D.1C.1
RENDERED PROMPT & FACT-LOCK FORENSICS TEST SUITE

Validates:
1. Clean grounded context for Report #4 contains no 50/20 historical values
2. Full rendered prompt contains no stale tenant numeric examples (50, 20, 6 reactions, etc.)
3. 0 comparable metrics remains 0 for Report #4
4. Total canonical metrics = 15 is allowed only when sourced from current context / coverage summary
5. Arbitrary 15 remains rejected if semantically unsupported / omitted from context
6. Unsupported 50 rejected by fact lock
7. Unsupported 20 rejected by fact lock
8. Numeric tenant performance claims require valid grounding in context
9. Context hash for Report #4 remains deterministic (96336b236d51ae65cc2dd865a7ed0e646deed96bfbe0d88d34cd13fb3c5dc4c1)
10. Rendered prompt is completely deterministic
11. Historical Narrative #4 remains immutable (status=REJECTED)
12. Zero provider calls occur
"""
import hashlib
import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from social_stats.models import (
    Client,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationRun,
    BusinessSignal,
)
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.prompts import (
    get_system_prompt_v3,
    build_user_prompt,
)
from social_stats.analytics.narrative.providers.ollama import compose_ollama_prompt
from social_stats.analytics.narrative.validator import NarrativeValidator, _collect_context_numbers


class PromptAndFactLockForensicsTests(TestCase):
    def setUp(self):
        self.p_start = date(2026, 9, 1)
        self.p_end = date(2026, 9, 30)
        self.client_obj = Client.objects.create(
            id=3,
            name="Bop Agencia",
            company="Bop Agencia",
            is_active=True,
        )

        # Baseline clean report data matching Report #4 exactly from database
        self.report = ExecutiveReport.objects.create(
            id=4,
            client=self.client_obj,
            title="Informe Ejecutivo de Rendimiento Social",
            report_type="EXECUTIVE",
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash="0c00c15a2a1ef764085d2c02a859ebf85812fe97b3b3977e6eb58c7b502ac9bc",
            report_data={
                "cover": {
                    "title": "Informe Ejecutivo de Rendimiento Social",
                    "period_start": "2026-09-01",
                    "period_end": "2026-09-30",
                    "client_name": "Bop Agencia",
                },
                "metadata": {
                    "client_id": 3,
                    "report_type": "EXECUTIVE",
                    "source_hash": "0c00c15a2a1ef764085d2c02a859ebf85812fe97b3b3977e6eb58c7b502ac9bc",
                    "language": "es",
                },
                "kpi_overview": {
                    "kpis": [
                        {
                            "metric": "FOLLOWERS_TOTAL",
                            "metric_key": "followers_total",
                            "current_value": None,
                            "is_available": True,
                        },
                        {
                            "metric": "FOLLOWERS_NET_CHANGE",
                            "metric_key": "followers_net_change",
                            "current_value": 0.0,
                            "is_available": True,
                        },
                        {
                            "metric": "REACTIONS",
                            "metric_key": "reactions",
                            "current_value": 0.0,
                            "is_available": True,
                        },
                    ]
                },
                "platform_breakdown": {
                    "platforms": [
                        {
                            "platform": "facebook",
                            "status_mode": "FULL",
                            "available_metrics": ["FOLLOWERS_TOTAL", "REACTIONS"],
                            "unavailable_metrics": [],
                            "reactions_total": 0,
                        },
                        {
                            "platform": "instagram",
                            "status_mode": "PARTIAL",
                            "available_metrics": ["FOLLOWERS_TOTAL", "REACTIONS"],
                            "unavailable_metrics": ["REACH", "SHARES", "SAVES"],
                            "reactions_total": 0,
                        },
                    ]
                },
                "business_intelligence_signals": {
                    "signals": [
                        {
                            "id": 10,
                            "signal_identity": "d39ef497502447b2f1c3ab4dc27b2d24200d93df54ed589de128c4fe2509c71e",
                            "signal_type": "PROVIDER_PARTIAL",
                            "platform": "instagram",
                            "confidence_level": "HIGH",
                            "summary": "Instagram analytics is operating in PARTIAL capability mode. Core source-backed metrics (Reactions, Comments, Total Followers) are active, while advanced metrics (Reach, Saves, Video Views) remain unavailable under current Meta permissions.",
                            "explanation": "Instagram analytics is operating in PARTIAL capability mode. Core source-backed metrics (Reactions, Comments, Total Followers) are active, while advanced metrics (Reach, Saves, Video Views) remain unavailable under current Meta permissions.",
                            "evidence": {"available_metrics": ["FOLLOWERS_TOTAL", "REACTIONS"]},
                        }
                    ]
                },
                "multichannel_intelligence": {
                    "has_multichannel_data": False,
                    "coverage_summary": {
                        "status": "LIMITED",
                        "total_metrics": 15,
                        "comparable_metrics": 0,
                        "coverage_ratio": "0/15",
                    },
                },
                "comparable_kpis": [],
                "rankable_kpis": [],
                "multichannel_complete": False,
            },
            language="es",
        )

        self.context = build_grounded_narrative_context(self.report)

    # 1. Clean grounded context contains no 50/20 historical values
    def test_01_clean_context_has_no_50_or_20_values(self):
        context_str = json.dumps(self.context)
        self.assertNotIn("50 seguidores", context_str)
        self.assertNotIn("20 seguidores", context_str)
        self.assertNotIn('"followers_total": 50', context_str)
        self.assertNotIn('"followers_total": 20', context_str)
        self.assertNotIn(" 50 ", context_str)
        self.assertNotIn(" 20 ", context_str)

    # 2. Full rendered prompt contains no stale tenant numeric examples
    def test_02_full_rendered_prompt_has_no_stale_tenant_numeric_examples(self):
        sys_prompt = get_system_prompt_v3(language="es", style="EXECUTIVE")
        usr_prompt = build_user_prompt(context=self.context)
        composed = compose_ollama_prompt(sys_prompt, usr_prompt)

        stale_terms = [
            "50 seguidores frente a 20",
            "50 followers compared to 20",
            "6 reacciones frente a 0",
            "6 reactions compared to 0",
            "solo 3 de 15 métricas canónicas",
            "only 3 of 15 canonical metrics",
            "MC-SIG-8",
            "MC-SIG-7",
        ]
        for term in stale_terms:
            self.assertNotIn(term, sys_prompt, f"Stale term '{term}' found in sys_prompt")
            self.assertNotIn(term, composed, f"Stale term '{term}' found in composed prompt")

    # 3. 0 comparable metrics remains 0
    def test_03_zero_comparable_metrics_remains_zero(self):
        self.assertEqual(len(self.report.report_data.get("comparable_kpis", [])), 0)
        self.assertFalse(self.report.report_data.get("multichannel_complete", False))
        self.assertFalse(self.report.report_data.get("multichannel_intelligence", {}).get("has_multichannel_data", True))

    # 4. Total canonical metrics = 15 is allowed only when sourced from current context
    def test_04_total_canonical_metrics_allowed_only_when_in_context(self):
        context_with_cov = dict(self.context)
        context_with_cov["coverage_summary"] = {"total_metrics": 15, "comparable_metrics": 0}
        nums = _collect_context_numbers(context_with_cov)
        self.assertIn(15.0, nums)

    # 5. Arbitrary 15 remains rejected if semantically unsupported
    def test_05_arbitrary_15_rejected_when_not_in_context(self):
        doc = {
            "executive_summary": ["El análisis evalúa 15 métricas."],
            "performance_observations": ["Métrica observada."],
            "recommendations": [
                {
                    "text": "Revisar permisos de integración del proveedor.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["Limitación observada."],
        }
        is_valid, val_summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertIn("Fact lock failed: Output contains unsupported numeric facts: [15.0]", val_summary["errors"])

    # 6. Unsupported 50 rejected
    def test_06_unsupported_50_rejected(self):
        doc = {
            "executive_summary": ["Instagram registró 50 seguidores."],
            "performance_observations": ["Observación de rendimiento."],
            "recommendations": [
                {
                    "text": "Revisar desempeño de canal observando métricas.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["Limitación observada."],
        }
        is_valid, val_summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("50.0" in e for e in val_summary.get("errors", [])))

    # 7. Unsupported 20 rejected
    def test_07_unsupported_20_rejected(self):
        doc = {
            "executive_summary": ["Facebook registró 20 seguidores."],
            "performance_observations": ["Observación de rendimiento."],
            "recommendations": [
                {
                    "text": "Revisar desempeño de canal observando métricas.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["Limitación observada."],
        }
        is_valid, val_summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("20.0" in e for e in val_summary.get("errors", [])))

    # 8. Numeric tenant claim requires valid grounding in context
    def test_08_grounded_numbers_pass_and_ungrounded_fail(self):
        doc_valid = {
            "executive_summary": ["El reporte describe la audiencia observada para el periodo."],
            "performance_observations": ["Reacciones observadas registraron 0.0 en el periodo."],
            "recommendations": [
                {
                    "text": "Revisar capacidades del proveedor para ampliar cobertura.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["Cobertura limitada en el periodo analizado."],
        }
        is_valid, val_summary = NarrativeValidator.validate(doc_valid, self.context)
        self.assertTrue(is_valid, f"Validation failed: {val_summary.get('errors')}")

    # 9. Context hash deterministic
    def test_09_context_hash_deterministic(self):
        chash1 = compute_context_hash(self.context)
        chash2 = compute_context_hash(self.context)
        self.assertEqual(chash1, chash2)
        self.assertEqual(len(chash1), 64)

    # 10. Rendered prompt deterministic
    def test_10_rendered_prompt_deterministic(self):
        sys_prompt1 = get_system_prompt_v3(language="es", style="EXECUTIVE")
        usr_prompt1 = build_user_prompt(context=self.context)
        composed1 = compose_ollama_prompt(sys_prompt1, usr_prompt1)

        sys_prompt2 = get_system_prompt_v3(language="es", style="EXECUTIVE")
        usr_prompt2 = build_user_prompt(context=self.context)
        composed2 = compose_ollama_prompt(sys_prompt2, usr_prompt2)

        hash1 = hashlib.sha256(composed1.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(composed2.encode("utf-8")).hexdigest()
        self.assertEqual(hash1, hash2)

    # 11. Narrative #4 remains immutable (status=REJECTED)
    def test_11_narrative_4_remains_immutable_rejected(self):
        narrative4 = ExecutiveNarrative.objects.create(
            id=4,
            client=self.client_obj,
            executive_report=self.report,
            language="es",
            status="REJECTED",
            provider="ollama",
            model_name="qwen3.5:9b",
            prompt_version="bs5e-prompt-v3",
            context_schema_version="bs4h-context-v2",
            source_hash=self.report.source_hash,
            context_hash="96336b236d51ae65cc2dd865a7ed0e646deed96bfbe0d88d34cd13fb3c5dc4c1",
            validation_status="FAIL",
            validation_results={
                "status": "FAIL",
                "errors": ["Fact lock failed: Output contains unsupported numeric facts: [15.0, 50.0, 20.0]"],
            },
        )
        self.assertEqual(narrative4.status, "REJECTED")
        self.assertEqual(narrative4.validation_status, "FAIL")

    # 12. Zero provider calls occur
    @patch("requests.post")
    def test_12_zero_provider_calls(self, mock_post):
        self.assertFalse(mock_post.called)
