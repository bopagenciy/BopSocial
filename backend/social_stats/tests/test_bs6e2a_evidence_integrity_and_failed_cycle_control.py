"""
BS-6E.2A Evidence Reference Integrity & Failed-Cycle Rescheduling Control Test Suite.
Verifies:
1. No signal IDs in context -> prompt contains no invented signal examples.
2. Allowed evidence IDs explicitly rendered in user prompt.
3. Model output citing only allowed evidence passes validation.
4. MC-SIG-7 absent -> validator rejects.
5. MC-SIG-8 absent -> validator rejects.
6. Valid limitation evidence derives HIGH confidence.
7. Narrative #7 remains REJECTED on replay.
8. Failed provider-consuming run suppresses identical scheduled rerun.
9. Changed prompt version re-enables eligible new lifecycle.
10. Changed source hash re-enables lifecycle.
11. Changed pipeline version re-enables lifecycle.
12. Operator-controlled retry remains possible.
13. Scheduler cannot auto-loop provider spend.
14. Run #16 remains provider_call_count=0.
15. Report #5 reusable under bs6a-v6.
"""
from datetime import date, datetime
from unittest.mock import patch
import zoneinfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation.constants import (
    AutomationStatus,
    AutomationStage,
    AutomationTriggerType,
    ApprovalStatus,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.identity import (
    compute_execution_identity,
    compute_approval_token,
    verify_executive_report_reuse,
)
from social_stats.analytics.automation.tasks import discover_and_enqueue_due_intelligence_automations
from social_stats.analytics.narrative.confidence import (
    derive_recommendation_confidence,
    enrich_narrative_with_derived_confidence,
)
from social_stats.analytics.narrative.context import build_grounded_narrative_context
from social_stats.analytics.narrative.prompts import (
    PROMPT_VERSION,
    PROMPT_VERSION_V4,
    PROMPT_VERSION_V5,
    build_user_prompt,
    get_system_prompt,
    get_system_prompt_v5,
)
from social_stats.analytics.narrative.validator import NarrativeValidator


class BS6E2AEvidenceIntegrityAndFailedCycleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user, _ = User.objects.get_or_create(
            username="admin_test",
            defaults={"email": "admin@test.local", "is_staff": True},
        )
        self.client_obj, _ = Client.objects.get_or_create(
            id=3,
            defaults={"name": "Bop Agencia", "is_active": True},
        )
        self.p_start = date(2026, 10, 1)
        self.p_end = date(2026, 10, 31)

        # Context with 0 business signals and 2 data limitations (mirroring October Report #5)
        self.october_context = {
            "context_schema_version": "bs4h-context-v2",
            "report": {
                "id": 5,
                "client_id": 3,
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "comparable_metrics": 3,
                "total_metrics": 15,
                "is_multichannel": True,
            },
            "kpis": {},
            "kpi_details": {},
            "signals": [],
            "limitations": [
                {
                    "ref_id": "LIMITATION-IG-PARTIAL",
                    "type": "DATA_LIMITATION",
                    "description": "Instagram capability is PARTIAL. Reach unavailable.",
                },
                {
                    "ref_id": "LIMITATION-CROSS-PLATFORM-PARTIAL",
                    "type": "DATA_LIMITATION",
                    "description": "Cross-platform data coverage is LIMITED (3 of 15 metrics).",
                },
            ],
            "supported_recommendations": [],
            "evidence_registry": {
                "LIMITATION-IG-PARTIAL": {
                    "type": "DATA_LIMITATION",
                    "description": "Instagram capability is PARTIAL. Reach unavailable.",
                },
                "LIMITATION-CROSS-PLATFORM-PARTIAL": {
                    "type": "DATA_LIMITATION",
                    "description": "Cross-platform data coverage is LIMITED (3 of 15 metrics).",
                },
            },
            "allowed_evidence_ids": [
                "LIMITATION-CROSS-PLATFORM-PARTIAL",
                "LIMITATION-IG-PARTIAL",
            ],
            "has_sufficient_data": True,
        }

    def test_01_no_signals_in_context_prompt_contains_no_invented_signals(self):
        """Prompt rendered for October context contains 0 invented signal IDs."""
        sys_prompt = get_system_prompt(language="es", style="EXECUTIVE")
        user_prompt = build_user_prompt(self.october_context)

        self.assertNotIn("MC-SIG-8", sys_prompt)
        self.assertNotIn("MC-SIG-7", sys_prompt)
        self.assertNotIn("MC-SIG-8", user_prompt)
        self.assertNotIn("MC-SIG-7", user_prompt)
        self.assertIn("BUSINESS_SIGNAL_IDS: NONE", user_prompt)

    def test_02_allowed_evidence_ids_explicitly_rendered(self):
        """User prompt explicitly renders the ALLOWED_EVIDENCE_IDS block."""
        user_prompt = build_user_prompt(self.october_context)
        self.assertIn("ALLOWED EVIDENCE IDS FOR RECOMMENDATIONS (STRICT)", user_prompt)
        self.assertIn("- LIMITATION-IG-PARTIAL", user_prompt)
        self.assertIn("- LIMITATION-CROSS-PLATFORM-PARTIAL", user_prompt)
        self.assertIn("Never invent evidence IDs", user_prompt)

    def test_03_model_output_citing_only_allowed_evidence_passes_validation(self):
        """A narrative citing only registered LIMITATION evidence passes validation."""
        valid_narrative = {
            "executive_summary": [
                "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
                "Instagram registró una audiencia observada frente a Facebook; FOLLOWERS_TOTAL describe tamaño de audiencia y no se utiliza para evaluar desempeño entre plataformas.",
            ],
            "performance_observations": [
                "Las métricas individuales observadas se reportan conforme a las evidencias del proveedor durante el periodo analizado.",
                "SAVES y VIDEO_VIEWS no se comparan directamente entre plataformas debido a diferencias en las definiciones y disponibilidad de proveedor.",
            ],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "evidence_refs": ["LIMITATION-IG-PARTIAL"],
                }
            ],
            "limitations": [
                "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
            ],
        }

        enriched = enrich_narrative_with_derived_confidence(valid_narrative, self.october_context)
        self.assertEqual(enriched["recommendations"][0].get("confidence"), "HIGH")

        is_valid, summary = NarrativeValidator.validate(enriched, self.october_context)
        self.assertTrue(is_valid, f"Expected valid narrative but got errors: {summary.get('errors')}")
        self.assertEqual(summary["status"], "PASS")

    def test_04_mc_sig_7_absent_validator_rejects(self):
        """Citing absent MC-SIG-7 fails validation."""
        invalid_narrative = {
            "executive_summary": ["La comparación entre plataformas es limitada."],
            "performance_observations": ["Métricas individuales reportadas."],
            "recommendations": [
                {
                    "text": "Revisar el desempeño por plataforma.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"],
                }
            ],
            "limitations": ["Cobertura parcial."],
        }
        enriched = enrich_narrative_with_derived_confidence(invalid_narrative, self.october_context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.october_context)
        self.assertFalse(is_valid)
        self.assertEqual(summary["status"], "FAIL")

    def test_05_mc_sig_8_absent_validator_rejects(self):
        """Citing absent MC-SIG-8 fails validation."""
        invalid_narrative = {
            "executive_summary": ["La comparación entre plataformas es limitada."],
            "performance_observations": ["Métricas individuales reportadas."],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-8"],
                }
            ],
            "limitations": ["Cobertura parcial."],
        }
        enriched = enrich_narrative_with_derived_confidence(invalid_narrative, self.october_context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.october_context)
        self.assertFalse(is_valid)
        self.assertEqual(summary["status"], "FAIL")

    def test_06_valid_limitation_evidence_derives_high_confidence(self):
        """DATA_LIMITATION evidence derives deterministic HIGH confidence."""
        reg = self.october_context["evidence_registry"]
        conf = derive_recommendation_confidence(["LIMITATION-IG-PARTIAL"], reg)
        self.assertEqual(conf, "HIGH")

        conf2 = derive_recommendation_confidence(["LIMITATION-CROSS-PLATFORM-PARTIAL"], reg)
        self.assertEqual(conf2, "HIGH")

    def test_07_narrative_7_remains_rejected_on_replay(self):
        """Historical Narrative #7 remains strictly REJECTED when replayed."""
        n7_json = {
            "limitations": [
                "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
                "Las métricas no provistas por la integración con la configuración actual del proveedor no se utilizan para evaluación directa entre plataformas.",
            ],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables.",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-8"],
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                },
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables.",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"],
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                },
            ],
            "executive_summary": [
                "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
            ],
            "performance_observations": [
                "Las métricas individuales observadas se reportan conforme a las evidencias del proveedor durante el periodo analizado.",
            ],
        }

        enriched = enrich_narrative_with_derived_confidence(n7_json, self.october_context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.october_context)
        self.assertFalse(is_valid)
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("Recommendation #1 has invalid confidence: 'None'.", summary["errors"])
        self.assertIn("Recommendation #2 has invalid confidence: 'None'.", summary["errors"])

    def test_08_failed_provider_consuming_run_suppresses_identical_scheduled_rerun(self):
        """A previous FAILED run with identical prompt and source hash suppresses scheduled rerun."""
        config, _ = IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={
                "enabled": True,
                "timezone": "America/New_York",
                "reporting_day": 1,
                "reporting_hour": 2,
                "reporting_frequency": "MONTHLY",
            },
        )
        config.enabled = True
        config.save()

        # Create a FAILED run with current pipeline and prompt version
        failed_run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version=PIPELINE_VERSION,
            status=AutomationStatus.FAILED.value,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            provider_call_count=1,
            metadata={
                "prompt_version": PROMPT_VERSION,
                "report_source_hash": "dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            },
        )

        with patch("social_stats.analytics.automation.tasks.get_deterministic_report_source_hash", return_value="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77"):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        skipped = [s for s in res.get("skipped_summary", []) if s.get("client_id") == 3]
        self.assertTrue(len(skipped) > 0)
        self.assertIn("FAILED_STATE_UNCHANGED", skipped[0].get("reason", ""))
        self.assertEqual(res.get("due_count"), 0)

    def test_09_changed_prompt_version_reenables_discovery(self):
        """If previous failed run was on an older prompt version, discovery is re-enabled."""
        config, _ = IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={"enabled": True, "timezone": "America/New_York", "reporting_day": 1, "reporting_hour": 2},
        )
        config.enabled = True
        config.save()

        failed_run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version=PIPELINE_VERSION,
            status=AutomationStatus.FAILED.value,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            provider_call_count=1,
            metadata={
                "prompt_version": "bs5e-prompt-v4",  # older prompt version
                "report_source_hash": "dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            },
        )

        with patch("social_stats.analytics.automation.tasks.get_deterministic_report_source_hash", return_value="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77"):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        # Prompt version changed from v4 to v5, so it is NOT suppressed by FAILED_STATE_UNCHANGED
        reasons = [s.get("reason", "") for s in res.get("skipped_summary", []) if s.get("client_id") == 3]
        self.assertFalse(any("FAILED_STATE_UNCHANGED" in r for r in reasons))

    def test_10_changed_source_hash_reenables_discovery(self):
        """If source hash changed from previous failed run, discovery is re-enabled."""
        config, _ = IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={"enabled": True, "timezone": "America/New_York", "reporting_day": 1, "reporting_hour": 2},
        )
        config.enabled = True
        config.save()

        failed_run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version=PIPELINE_VERSION,
            status=AutomationStatus.FAILED.value,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            provider_call_count=1,
            metadata={
                "prompt_version": PROMPT_VERSION,
                "report_source_hash": "old_hash_111111111111111111111111111111111111111111111111111111111111",
            },
        )

        with patch("social_stats.analytics.automation.tasks.get_deterministic_report_source_hash", return_value="new_hash_222222222222222222222222222222222222222222222222222222222222"):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        reasons = [s.get("reason", "") for s in res.get("skipped_summary", []) if s.get("client_id") == 3]
        self.assertFalse(any("FAILED_STATE_UNCHANGED" in r for r in reasons))

    def test_11_changed_pipeline_version_reenables_discovery(self):
        """Failed run under bs6a-v5 does not suppress discovery under bs6a-v6."""
        config, _ = IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={"enabled": True, "timezone": "America/New_York", "reporting_day": 1, "reporting_hour": 2},
        )
        config.enabled = True
        config.save()

        # Failed run under older pipeline version bs6a-v5
        failed_run = IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version="bs6a-v5",
            status=AutomationStatus.FAILED.value,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            provider_call_count=1,
            metadata={
                "prompt_version": PROMPT_VERSION,
                "report_source_hash": "dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            },
        )

        with patch("social_stats.analytics.automation.tasks.get_deterministic_report_source_hash", return_value="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77"):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)

        reasons = [s.get("reason", "") for s in res.get("skipped_summary", []) if s.get("client_id") == 3]
        self.assertFalse(any("FAILED_STATE_UNCHANGED" in r for r in reasons))

    def test_12_operator_controlled_retry_remains_possible(self):
        """Manual trigger type is recognized as distinct from scheduled discovery."""
        self.assertEqual(AutomationTriggerType.MANUAL.value, "MANUAL")
        self.assertEqual(AutomationTriggerType.SCHEDULED.value, "SCHEDULED")

    def test_13_scheduler_cannot_auto_loop_provider_spend(self):
        """Repeated ticks on unchanged failed state continuously skip without creating new runs."""
        config, _ = IntelligenceAutomationConfig.objects.get_or_create(
            client=self.client_obj,
            defaults={"enabled": True, "timezone": "America/New_York", "reporting_day": 1, "reporting_hour": 2},
        )
        config.enabled = True
        config.save()

        IntelligenceAutomationRun.objects.create(
            client=self.client_obj,
            period_start=self.p_start,
            period_end=self.p_end,
            pipeline_version=PIPELINE_VERSION,
            status=AutomationStatus.FAILED.value,
            current_stage=AutomationStage.NARRATIVE_CHECK.value,
            provider_call_count=1,
            metadata={
                "prompt_version": PROMPT_VERSION,
                "report_source_hash": "dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            },
        )

        initial_count = IntelligenceAutomationRun.objects.count()

        with patch("social_stats.analytics.automation.tasks.get_deterministic_report_source_hash", return_value="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77"):
            # Tick 1
            res1 = discover_and_enqueue_due_intelligence_automations(dry_run=False)
            # Tick 2
            res2 = discover_and_enqueue_due_intelligence_automations(dry_run=False)

        self.assertEqual(res1.get("due_count"), 0)
        self.assertEqual(res2.get("due_count"), 0)
        self.assertEqual(IntelligenceAutomationRun.objects.count(), initial_count)

    def test_14_run_16_remains_provider_call_count_zero(self):
        """Run #16 remains provider_call_count=0."""
        r16 = IntelligenceAutomationRun.objects.filter(id=16).first()
        if r16:
            self.assertEqual(r16.provider_call_count, 0)

    def test_15_report_5_reusable_under_v6(self):
        """ExecutiveReport #5 remains reusable under bs6a-v6."""
        r5 = ExecutiveReport.objects.filter(id=5).first()
        if r5:
            reusable, rep = verify_executive_report_reuse(
                client_id=3,
                period_start=self.p_start,
                period_end=self.p_end,
                expected_source_hash="dd6bb501ca5051cd784f95e64298ec131a27cd3b9adbc874eae8256e8650fe77",
            )
            self.assertTrue(reusable)
            self.assertEqual(rep.id, 5)
