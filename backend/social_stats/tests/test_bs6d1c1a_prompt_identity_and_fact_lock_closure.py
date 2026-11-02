"""
BOP SOCIAL — PHASE BS-6D.1C.1A
Test Suite: Prompt Identity & Numeric Fact-Lock Closure
"""
import copy
import hashlib
import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from social_stats.analytics.automation.constants import PIPELINE_VERSION
from social_stats.analytics.automation.identity import (
    compute_execution_identity,
    verify_executive_narrative_reuse,
)
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.prompts import (
    PROMPT_VERSION,
    PROMPT_VERSION_V3,
    PROMPT_VERSION_V4,
    build_user_prompt,
    get_system_prompt,
    get_system_prompt_v3,
    get_system_prompt_v4,
)
from social_stats.analytics.narrative.providers.ollama import compose_ollama_prompt
from social_stats.analytics.narrative.schemas import (
    CONTEXT_SCHEMA_VERSION,
)
from social_stats.analytics.narrative.validator import (
    NarrativeValidator,
    _collect_context_numbers,
    _extract_all_numbers,
    _extract_business_numbers,
    _strip_structural_syntax,
)
from social_stats.models import (
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationRun,
    SyncLog,
)


class PromptIdentityAndFactLockClosureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="factlock_pilot", password="password123")
        self.client_obj = Client.objects.create(
            id=3,
            name="Bop Agencia",
            company="Bop Agencia SAS",
            email="pilot@bopagencia.com",
            owner_user=self.user,
            is_active=True,
        )
        self.p_start = date(2026, 9, 1)
        self.p_end = date(2026, 9, 30)

        self.report = ExecutiveReport.objects.create(
            id=4,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            source_hash="a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
            report_data={
                "client_id": 3,
                "period": {
                    "start": "2026-09-01",
                    "end": "2026-09-30",
                },
                "kpis_summary": {
                    "kpis": [
                        {
                            "metric": "FOLLOWERS_TOTAL",
                            "metric_key": "followers_total",
                            "current_value": None,
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
                            "summary": "Instagram analytics is operating in PARTIAL capability mode.",
                            "explanation": "Instagram analytics is operating in PARTIAL capability mode.",
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

        # Baseline valid document aligned with context
        self.valid_skeleton = {
            "executive_summary": ["El reporte describe la audiencia observada para el periodo."],
            "performance_observations": ["Reacciones observadas registraron 0.0 en el periodo."],
            "recommendations": [
                {
                    "text": "Revisar capacidades del proveedor para ampliar cobertura según el hallazgo SIG-1.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                }
            ],
            "limitations": ["Cobertura limitada en el periodo analizado."],
        }

    # 1. Arbitrary 1 unsupported => rejected as business fact
    def test_01_arbitrary_1_unsupported_rejected_as_business_fact(self):
        doc = copy.deepcopy(self.valid_skeleton)
        doc["performance_observations"] = [
            "Instagram registró 1 seguidor nuevo durante la última semana.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertIn("Fact lock failed: Output contains unsupported numeric facts: [1.0]", summary.get("errors", []))

    # 2. Arbitrary 3 unsupported => rejected
    def test_02_arbitrary_3_unsupported_rejected(self):
        doc = copy.deepcopy(self.valid_skeleton)
        doc["performance_observations"] = [
            "Se registraron 3 publicaciones destacadas durante el periodo.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertIn("Fact lock failed: Output contains unsupported numeric facts: [3.0]", summary.get("errors", []))

    # 3. Arbitrary 6 unsupported => rejected
    def test_03_arbitrary_6_unsupported_rejected(self):
        doc = copy.deepcopy(self.valid_skeleton)
        doc["performance_observations"] = [
            "Instagram registró 6 reacciones frente a 0.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("6.0" in err for err in summary.get("errors", [])))

    # 4. Arbitrary 10 unsupported => rejected
    def test_04_arbitrary_10_unsupported_rejected(self):
        doc = copy.deepcopy(self.valid_skeleton)
        doc["performance_observations"] = [
            "La cuenta publicó 10 historias durante el periodo.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, self.context)
        self.assertFalse(is_valid)
        self.assertIn("Fact lock failed: Output contains unsupported numeric facts: [10.0]", summary.get("errors", []))

    # 5. Grounded small integer => accepted
    def test_05_grounded_small_integer_accepted(self):
        context_with_grounded_int = copy.deepcopy(self.context)
        context_with_grounded_int["kpis"]["posts_count"] = 5.0
        doc = copy.deepcopy(self.valid_skeleton)
        doc["performance_observations"] = [
            "Instagram registró 5.0 publicaciones confirmadas durante el periodo.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, context_with_grounded_int)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    # 6. Structural index does not become business fact
    def test_06_structural_index_does_not_become_business_fact(self):
        doc = copy.deepcopy(self.valid_skeleton)
        doc["recommendations"] = [
            {
                "text": "1. Recomendación 1: según SIG-1 mantener estrategia actual de publicación.",
                "recommendation_type": "MAINTAIN_CURRENT_STRATEGY",
                "strength": "OBSERVE",
                "confidence": "HIGH",
                "evidence_refs": ["SIG-1"],
            }
        ]
        is_valid, summary = NarrativeValidator.validate(doc, self.context)
        self.assertTrue(is_valid, f"Structural markers caused fact lock failure: {summary.get('errors')}")

    # 7. total_metrics=15 current context can be used semantically
    def test_07_total_metrics_15_context_used_semantically(self):
        context_with_cov = copy.deepcopy(self.context)
        context_with_cov["coverage_summary"] = {"total_metrics": 15, "comparable_metrics": 0}
        doc = copy.deepcopy(self.valid_skeleton)
        doc["limitations"] = [
            "El catálogo canónico evalúa 15 métricas en total.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, context_with_cov)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    # 8. 3-of-15 against 0 comparable rejected
    def test_08_three_of_15_against_zero_comparable_rejected(self):
        context_with_cov = copy.deepcopy(self.context)
        context_with_cov["coverage_summary"] = {"total_metrics": 15, "comparable_metrics": 0}
        doc = copy.deepcopy(self.valid_skeleton)
        doc["limitations"] = [
            "Solo 3 de 15 métricas son comparables en este periodo.",
        ]
        is_valid, summary = NarrativeValidator.validate(doc, context_with_cov)
        self.assertFalse(is_valid)
        self.assertTrue(any("3.0" in err for err in summary.get("errors", [])))

    # 9. Prompt v3 artifact rejected under prompt v4 reuse
    def test_09_prompt_v3_artifact_rejected_under_prompt_v4_reuse(self):
        narrative_v3 = ExecutiveNarrative.objects.create(
            id=101,
            client=self.client_obj,
            executive_report=self.report,
            language="es",
            status="VALIDATED",
            narrative_json=self.valid_skeleton,
            source_hash=self.report.source_hash,
            context_hash=compute_context_hash(self.context),
            prompt_version="bs5e-prompt-v3",
            context_schema_version=CONTEXT_SCHEMA_VERSION,
        )
        is_reusable, reason, _ = verify_executive_narrative_reuse(
            narrative=narrative_v3,
            report=self.report,
            client_id=3,
            period_start=self.p_start,
            period_end=self.p_end,
            expected_prompt_version=PROMPT_VERSION_V4,
        )
        self.assertFalse(is_reusable)
        self.assertIn("PROMPT_VERSION_MISMATCH", reason)

    # 10. Matching prompt version/context/source can reuse
    def test_10_matching_prompt_version_context_source_can_reuse(self):
        narrative_v4 = ExecutiveNarrative.objects.create(
            id=102,
            client=self.client_obj,
            executive_report=self.report,
            language="es",
            status="VALIDATED",
            narrative_json=self.valid_skeleton,
            source_hash=self.report.source_hash,
            context_hash=compute_context_hash(self.context),
            prompt_version=PROMPT_VERSION_V4,
            context_schema_version=CONTEXT_SCHEMA_VERSION,
        )
        is_reusable, reason, exp_chash = verify_executive_narrative_reuse(
            narrative=narrative_v4,
            report=self.report,
            client_id=3,
            period_start=self.p_start,
            period_end=self.p_end,
            expected_prompt_version=PROMPT_VERSION_V4,
        )
        self.assertTrue(is_reusable)
        self.assertEqual(reason, "REUSABLE")
        self.assertEqual(exp_chash, compute_context_hash(self.context))

    # 11. Narrative #4 remains rejected and immutable
    def test_11_narrative_4_remains_rejected_and_immutable(self):
        narrative4 = ExecutiveNarrative.objects.create(
            id=104,
            client=self.client_obj,
            executive_report=self.report,
            language="es",
            status="REJECTED",
            provider="ollama",
            model_name="qwen3.5:9b",
            prompt_version="bs5e-prompt-v3",
            context_schema_version=CONTEXT_SCHEMA_VERSION,
            source_hash="hist_hash",
            context_hash="hist_chash",
            validation_status="FAIL",
            validation_results={
                "status": "FAIL",
                "errors": ["Fact lock failed: Output contains unsupported numeric facts: [15.0, 50.0, 20.0]"],
            },
        )
        is_reusable, reason, _ = verify_executive_narrative_reuse(
            narrative=narrative4,
            report=self.report,
            client_id=3,
            period_start=self.p_start,
            period_end=self.p_end,
        )
        self.assertFalse(is_reusable)
        self.assertIn("NARRATIVE_STATUS_NOT_VALIDATED", reason)

    # 12. Run #11 remains failed and immutable
    def test_12_run_11_remains_failed_and_immutable(self):
        run11 = IntelligenceAutomationRun.objects.create(
            id=111,
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version="bs6a-v2",
            execution_identity="b5d8d4d66f6ca9b44724bd7278feff201d02936074bec22f360dc36bd9cb8766",
            status="FAILED",
            provider_call_count=1,
            error_code="NARRATIVE_VALIDATION_FAILED",
            error_message_safe="Narrative validation failed: Unsupported numeric facts [15.0, 50.0, 20.0]",
        )
        run11.refresh_from_db()
        self.assertEqual(run11.status, "FAILED")
        self.assertEqual(run11.pipeline_version, "bs6a-v2")
        self.assertEqual(run11.provider_call_count, 1)

    # 13. Clean prompt has no stale tenant examples
    def test_13_clean_prompt_has_no_stale_tenant_examples(self):
        sys_prompt = get_system_prompt_v4(language="es", style="EXECUTIVE")
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

    # 14. Failed audit records preserved (not delete-to-restore)
    def test_14_failed_audit_records_preserved_not_delete_to_restore(self):
        initial_synclogs = SyncLog.objects.count()
        failed_log = SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            sync_scope="CURRENT",
            status="failed",
            records_synced=0,
            error_message="Meta API timeout during operational sync.",
        )
        self.assertEqual(SyncLog.objects.count(), initial_synclogs + 1)
        persisted = SyncLog.objects.get(id=failed_log.id)
        self.assertEqual(persisted.status, "failed")
        self.assertIn("timeout", persisted.error_message)

    # 15. Zero provider calls
    @patch("requests.post")
    def test_15_zero_provider_calls(self, mock_post):
        NarrativeValidator.validate(self.valid_skeleton, self.context)
        compute_execution_identity(3, self.p_start, self.p_end, PIPELINE_VERSION)
        get_system_prompt(language="es", style="EXECUTIVE")
        mock_post.assert_not_called()
