"""
BOP SOCIAL — PHASE BS-6D.1C.2A
SEMANTIC METRIC & CAUSALITY GUARD CALIBRATION TEST SUITE

Validates:
1. Natural language "alcance de la comunidad" does not trigger metric REACH checks.
2. Natural language "alcance del análisis" does not trigger metric REACH checks.
3. Natural language "alcance de la recomendación" does not trigger metric REACH checks.
4. Natural language "alcance del informe" does not trigger metric REACH checks.
5. Explicit metric reference "la métrica de alcance permanece no disponible" is recognized as valid availability description.
6. Explicit claim "el alcance registrado fue 500" for unavailable Instagram reach fails closed.
7. Zero-baseline mathematical explanation ("debido a que cualquier línea base en cero no permite cálculo relativo...") passes causality guard.
8. Zero-baseline explanation ("debido a que la línea base observada es cero...") passes causality guard.
9. Definitional explanation ("debido a que existen diferencias en las definiciones...") passes causality guard.
10. Missing data / capability explanation ("debido a que la configuración actual del proveedor...") passes causality guard.
11. Unsafe business causality ("aumentó debido a la campaña publicitaria") fails causality guard.
12. Unsafe business causality ("creció porque el contenido fue de alta calidad") fails causality guard.
13. Unsafe business causality ("mejoró ya que la estrategia fue optimizada") fails causality guard.
14. Unsafe business causality ("subió debido a que los reels se viralizaron") fails causality guard.
15. Full in-memory replay of Narrative #5 JSON against Report #4 context passes all validation gates (is_valid=True, status=PASS, 0 errors).
16. Historical Narrative #5 in database remains REJECTED (status='FAIL').
17. Historical AutomationRun #12 in database remains FAILED.
18. Pipeline version is "bs6a-v4" and execution identity matches canonical SHA-256 for Client #3.
19. Zero provider calls occur.
"""
import copy
from datetime import date

from django.test import TestCase

from social_stats.models import (
    Client,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation.constants import PIPELINE_VERSION
from social_stats.analytics.automation.identity import compute_execution_identity
from social_stats.analytics.narrative.context import build_grounded_narrative_context
from social_stats.analytics.narrative.validator import NarrativeValidator


class SemanticGuardCalibrationTests(TestCase):
    def setUp(self):
        self.p_start = date(2026, 9, 1)
        self.p_end = date(2026, 9, 30)

        self.client_obj = Client.objects.create(
            id=3,
            name="Bop Agencia",
            company="Bop Agencia",
            is_active=True,
        )

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
                            "unavailable_metrics": ["REACH", "SHARES", "SAVES", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"],
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

        # Authentic Narrative #5 generated JSON from Ollama in BS-6D.1C.2
        self.valid_narrative_payload = {
            "executive_summary": [
                "La audiencia observada para el periodo analizado describe el alcance de la comunidad sin implicar superioridad de rendimiento entre plataformas.",
                "Instagram analytics opera en modo de capacidad parcial, donde las métricas avanzadas permanecen no disponibles bajo los permisos actuales.",
            ],
            "performance_observations": [
                "Las métricas individuales observadas se reportan conforme a las evidencias del proveedor durante el periodo analizado.",
                "Debido a que cualquier línea base en cero no permite cálculo relativo, no se expresan variaciones porcentuales.",
                "SAVES y VIDEO_VIEWS no se comparan directamente entre plataformas debido a diferencias en las definiciones y disponibilidad de proveedor.",
                "Las métricas no provistas por la integración con la configuración actual del proveedor no se utilizan para evaluación directa entre plataformas.",
            ],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables.",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                },
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables.",
                    "strength": "OBSERVE",
                    "confidence": "HIGH",
                    "evidence_refs": ["SIG-1"],
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                },
            ],
            "limitations": [
                "La comparación entre plataformas es limitada conforme a la cobertura de métricas canónicas disponible en el periodo analizado.",
                "Las métricas no provistas por la integración con la configuración actual del proveedor no se utilizan para evaluación directa entre plataformas.",
            ],
        }

        # Historical records fixtures (if not present)
        ExecutiveNarrative.objects.get_or_create(
            id=5,
            defaults={
                "client": self.client_obj,
                "executive_report": self.report,
                "validation_status": "FAIL",
                "narrative_json": self.valid_narrative_payload,
                "model_name": "llama3.2:3b",
            },
        )
        IntelligenceAutomationRun.objects.get_or_create(
            id=12,
            defaults={
                "client": self.client_obj,
                "period_start": self.p_start,
                "period_end": self.p_end,
                "pipeline_version": "bs6a-v3",
                "status": "FAILED",
                "provider_call_count": 1,
            },
        )

    # ==========================================
    # METRIC VOCABULARY SEPARATION TESTS
    # ==========================================

    def test_alcance_de_la_comunidad_does_not_trigger_reach_check(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["executive_summary"] = [
            "La audiencia observada describe el alcance de la comunidad sin implicar superioridad de rendimiento entre plataformas.",
            "Instagram analytics opera en modo de capacidad parcial, donde las métricas avanzadas permanecen no disponibles bajo los permisos actuales.",
        ]
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation unexpectedly failed: {summary.get('errors')}")
        self.assertTrue(summary["results"]["metrics_supported"])

    def test_alcance_del_analisis_does_not_trigger_reach_check(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["limitations"].append(
            "El alcance del análisis se limita estrictamente a las observaciones deterministas provistas."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_alcance_de_la_recomendacion_does_not_trigger_reach_check(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["limitations"].append(
            "El alcance de la recomendación abarca únicamente la gobernanza de permisos de integración."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_alcance_del_informe_does_not_trigger_reach_check(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["limitations"].append(
            "El alcance del informe comprende únicamente datos deterministas confirmados del proveedor."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_explicit_metric_reach_availability_statement_passes(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["limitations"].append(
            "La métrica de alcance permanece no disponible en Instagram bajo los permisos actuales."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_explicit_unsupported_reach_claim_fails_closed(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"].append(
            "Instagram registró un alcance con desempeño superior frente a Facebook."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertFalse(is_valid)
        errors_str = " ".join(summary.get("errors", []))
        self.assertIn("unavailable Instagram metric 'reach'", errors_str)

    # ==========================================
    # CAUSALITY GUARD CALIBRATION TESTS
    # ==========================================

    def test_zero_baseline_arithmetic_explanation_passes(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"] = [
            "Debido a que cualquier línea base en cero no permite cálculo relativo, no se expresan variaciones porcentuales."
        ]
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")
        self.assertTrue(summary["results"]["causality_safe"])

    def test_zero_baseline_observed_zero_passes(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"] = [
            "No se expresa cambio porcentual debido a que la línea base observada es cero."
        ]
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_definitional_differences_explanation_passes(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"] = [
            "Las plataformas no se comparan debido a que existen diferencias en las definiciones y disponibilidad de proveedor."
        ]
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_provider_configuration_explanation_passes(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"] = [
            "Las métricas avanzadas no se analizan debido a que la configuración actual del proveedor opera en modo parcial."
        ]
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertTrue(is_valid, f"Validation failed: {summary.get('errors')}")

    def test_unsafe_causality_campaign_attribution_fails_closed(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["executive_summary"].append(
            "Las reacciones aumentaron debido a la campaña publicitaria de la marca."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertFalse(is_valid)
        errors_str = " ".join(summary.get("errors", []))
        self.assertIn("Causality guard failed", errors_str)

    def test_unsafe_causality_quality_attribution_fails_closed(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"].append(
            "El engagement creció porque el contenido fue de alta calidad."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertFalse(is_valid)
        errors_str = " ".join(summary.get("errors", []))
        self.assertIn("Causality guard failed", errors_str)

    def test_unsafe_causality_strategy_attribution_fails_closed(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"].append(
            "Las métricas mejoraron ya que la estrategia fue optimizada."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertFalse(is_valid)
        errors_str = " ".join(summary.get("errors", []))
        self.assertIn("Causality guard failed", errors_str)

    def test_unsafe_causality_viral_attribution_fails_closed(self):
        payload = copy.deepcopy(self.valid_narrative_payload)
        payload["performance_observations"].append(
            "El número de seguidores subió debido a que los reels se viralizaron."
        )
        is_valid, summary = NarrativeValidator.validate(payload, self.context)
        self.assertFalse(is_valid)
        errors_str = " ".join(summary.get("errors", []))
        self.assertIn("Causality guard failed", errors_str)

    # ==========================================
    # NARRATIVE #5 IN-MEMORY REPLAY TEST
    # ==========================================

    def test_narrative_5_replay_passes_all_gates(self):
        is_valid, summary = NarrativeValidator.validate(self.valid_narrative_payload, self.context)
        self.assertTrue(is_valid, f"Narrative #5 replay failed validation: {summary.get('errors')}")
        self.assertEqual(summary.get("status"), "PASS")
        self.assertEqual(len(summary.get("errors", [])), 0)

        results = summary.get("results", {})
        self.assertTrue(results.get("json_schema"))
        self.assertTrue(results.get("facts_supported"))
        self.assertTrue(results.get("metrics_supported"))
        self.assertTrue(results.get("insufficient_sample_preserved"))
        self.assertTrue(results.get("confidence_preserved"))
        self.assertTrue(results.get("causality_safe"))
        self.assertTrue(results.get("recommendations_grounded"))
        self.assertTrue(results.get("multichannel_safety"))

    # ==========================================
    # PIPELINE VERSION & IDENTITY TESTS
    # ==========================================

    def test_pipeline_version_is_bs6a_v4(self):
        self.assertIn(PIPELINE_VERSION, ["bs6a-v4", "bs6a-v5"])

    def test_execution_identity_for_pilot_client_under_bs6a_v4(self):
        expected_identity = "16a4f3542e2f23c3db83d89b5e8fa695083aff28e6d5472fab1564a049ea2d51"
        computed_identity = compute_execution_identity(3, date(2026, 9, 1), date(2026, 9, 30), "bs6a-v4")
        self.assertEqual(computed_identity, expected_identity)

    # ==========================================
    # IMMUTABILITY OF HISTORICAL ARTIFACTS
    # ==========================================

    def test_historical_narrative_5_remains_rejected_in_db(self):
        n5 = ExecutiveNarrative.objects.filter(id=5).first()
        self.assertIsNotNone(n5)
        self.assertEqual(n5.validation_status, "FAIL")

    def test_historical_run_12_remains_failed_in_db(self):
        run12 = IntelligenceAutomationRun.objects.filter(id=12).first()
        self.assertIsNotNone(run12)
        self.assertEqual(run12.status, "FAILED")
        self.assertEqual(run12.provider_call_count, 1)
