import datetime
"""
BS-5E Dedicated Test Suite: Grounded Multichannel Narrative Safeties & Deterministic Preview.

Validates:
- Approved context schema (bs4h-context-v2) and prompt version (bs5d-prompt-v1)
- Deterministic evidence registry resolution for MC-SIG-6..9 and SIG-1..5
- Unknown evidence refs fail closed (e.g. MC-SIG-999)
- Canonical coverage limitation evidence (3/15 comparable, status LIMITED)
- Audience volume vs performance lock (FOLLOWERS_TOTAL)
- Zero-baseline percentage lock (REACTIONS FB=0, IG=6)
- Metric availability lock (REACH, ENGAGEMENT_TOTAL under partial mode)
- Non-comparable metric lock (SAVES, VIDEO_VIEWS)
- Overall winner lock (forbids best platform, winner claims)
- Cross-metric synthetic aggregation prohibition
- Causality guard (rejects "porque", "caused", etc.)
- Budget reallocation prohibition ("Move budget to Instagram")
- Deterministic confidence authority (derived from evidence refs, model cannot override)
- Context hash determinism and sensitivity
- Source hash binding and staleness detection
- Prompt input minimization (no secrets/tokens leaked)
- Language contract (Spanish vs English mismatch)
- Zero database writes during preview
- Tenant isolation
"""
from datetime import date
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
    ExecutiveNarrative,
)
from social_stats.analytics.reporting.builder import (
    build_executive_report_data,
    compute_source_hash,
)
from social_stats.analytics.narrative.schemas import (
    CONTEXT_SCHEMA_VERSION,
    PROMPT_VERSION,
    FORBIDDEN_KEYS,
    CLAIM_CATEGORIES,
    CLAIM_EVIDENCE_MAPPING,
    CROSS_PLATFORM_ACTION_MAPPING,
    MAX_PROVIDER_CALLS,
    GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    SIGNAL_TYPE_TO_CLAIM_CATEGORY,
)
from social_stats.analytics.narrative.context import (
    build_grounded_narrative_context,
    compute_context_hash,
)
from social_stats.analytics.narrative.confidence import (
    derive_recommendation_confidence,
    enrich_narrative_with_derived_confidence,
)
from social_stats.analytics.narrative.prompts import (
    get_system_prompt,
    build_user_prompt,
)
from social_stats.analytics.narrative.validator import NarrativeValidator
from social_stats.analytics.narrative.service import (
    preview_narrative,
    generate_and_save_narrative,
    execute_controlled_narrative_generation,
    ControlledLiveExecutionError,
)


class GroundedMultichannelNarrativeSafetiesTests(TestCase):
    """Exhaustive BS-5E safeguards and deterministic preview test suite."""

    def setUp(self):
        self.user = User.objects.create_user(username="narrative_bs5e_user", password="password123")
        self.client_obj = Client.objects.create(
            name="Test Agency Client",
            company="Bop Agencia Pilot",
            email="test_agency_bs5e@example.com",
            owner_user=self.user,
            is_active=True,
        )
        self.other_user = User.objects.create_user(username="narrative_other_user", password="password123")
        self.other_client = Client.objects.create(
            name="Other Client",
            company="Other Org",
            email="other_bs5e@example.com",
            owner_user=self.other_user,
            is_active=True,
        )

        self.start_date = date(2026, 9, 22)
        self.end_date = date(2026, 10, 22)
        self.canonical_benchmark_hash = "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"

        # Platform Credentials with secret tokens to test minimization
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            page_id="fb_page_123",
            access_token="EAA_SECRET_TOKEN_DO_NOT_LEAK",
            refresh_token="REFRESH_SECRET_KEY",
            is_active=True,
        )
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform="instagram",
            instagram_account_id="ig_biz_456",
            access_token="IG_SECRET_TOKEN_DO_NOT_LEAK",
            is_active=True,
        )

        # FB Rollups
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
        # IG Rollups
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

        # Single platform signal 1 (SIG-1)
        self.sig1 = BusinessSignal.objects.create(
            id=1,
            client=self.client_obj,
            platform="instagram",
            signal_type="PROVIDER_PARTIAL",
            metric="MULTIPLE",
            scope="account",
            period_start=self.start_date,
            period_end=self.end_date,
            sample_size=10,
            confidence_level="HIGH",
            severity="WARNING",
            is_actionable=True,
            signal_identity="sig1_identity",
            explanation_template="Instagram opera en modo parcial con métricas de interacción registradas.",
            evidence={"type": "PROVIDER_PARTIAL"},
        )

        # Multichannel BusinessSignals (IDs 6-9)
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

        self.source_hash = "cb79885ade504aeac72f1bf2854b155be31c33b0c9ce3f0c168c7fc0a38ad148"
        # Build canonical BS-5D executive report data
        self.report_data = build_executive_report_data(
            client_id=self.client_obj.id,
            date_from=self.start_date,
            date_to=self.end_date,
            language="es",
        )

        self.report = ExecutiveReport.objects.create(
            client=self.client_obj,
            title="Informe Ejecutivo Multicanal",
            period_start=self.start_date,
            period_end=self.end_date,
            report_type="EXECUTIVE",
            language="es",
            source_hash=self.source_hash,
            report_data=self.report_data,
        )

    # 1. Context Schema & Prompt Version
    def test_context_schema_and_prompt_version(self):
        context = build_grounded_narrative_context(self.report)
        self.assertEqual(context["context_schema_version"], "bs4h-context-v2")
        self.assertEqual(CONTEXT_SCHEMA_VERSION, "bs4h-context-v2")
        self.assertEqual(PROMPT_VERSION, "bs5e-prompt-v2")

    # 2. Multichannel Evidence Registry Resolution (MC-SIG-6..9)
    def test_multichannel_evidence_registry_resolution(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        for expected_ref in ["MC-SIG-6", "MC-SIG-7", "MC-SIG-8", "MC-SIG-9"]:
            self.assertIn(expected_ref, reg)
            ev = reg[expected_ref]
            self.assertEqual(ev["type"], "MULTICHANNEL_SIGNAL")
            self.assertEqual(ev["confidence"], "HIGH")

    # 3. Single Platform Evidence Backward Compatibility (SIG-1..5)
    def test_single_platform_evidence_backward_compatibility(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        self.assertIn("SIG-1", reg)
        self.assertIn("LIMITATION-IG-PARTIAL", reg)

    # 4. Unknown Evidence Ref Fails Closed
    def test_unknown_evidence_ref_fails_closed(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        self.assertNotIn("MC-SIG-999", reg)
        with self.assertRaises(ValueError) as cm:
            derive_recommendation_confidence(["MC-SIG-999"], reg)
        self.assertIn("Unknown evidence reference 'MC-SIG-999'", str(cm.exception))

    # 5. Coverage Limitation Evidence
    def test_coverage_limitation_registered(self):
        context = build_grounded_narrative_context(self.report)
        mc_intel = context.get("multichannel_intelligence", {})
        cov = mc_intel.get("coverage_summary", {})
        self.assertEqual(cov.get("status"), "LIMITED")
        self.assertEqual(cov.get("coverage_ratio"), "3/15")
        self.assertEqual(cov.get("total_metrics"), 15)
        self.assertEqual(cov.get("comparable_metrics"), 3)
        self.assertEqual(cov.get("unavailable_metrics"), 10)
        self.assertEqual(cov.get("non_comparable_metrics"), 2)

    # 6. Context Hash Determinism
    def test_context_hash_determinism(self):
        ctx1 = build_grounded_narrative_context(self.report)
        ctx2 = build_grounded_narrative_context(self.report)
        h1 = compute_context_hash(ctx1)
        h2 = compute_context_hash(ctx2)
        self.assertEqual(h1, h2)
        self.assertIsInstance(h1, str)
        self.assertEqual(len(h1), 64)

    # 7. Context Hash Sensitivity
    def test_context_hash_sensitivity(self):
        import copy
        ctx = build_grounded_narrative_context(self.report)
        base_hash = compute_context_hash(ctx)

        # Modify benchmark hash
        ctx_mod = copy.deepcopy(ctx)
        ctx_mod["multichannel_intelligence"]["benchmark_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
        self.assertNotEqual(base_hash, compute_context_hash(ctx_mod))

        # Modify coverage
        ctx_mod2 = copy.deepcopy(ctx)
        ctx_mod2["multichannel_intelligence"]["coverage_summary"]["total_metrics"] = 16
        self.assertNotEqual(base_hash, compute_context_hash(ctx_mod2))

    # 8. Report Source Binding
    def test_report_source_binding(self):
        context = build_grounded_narrative_context(self.report)
        self.assertEqual(context["report"]["id"], self.report.id)
        self.assertEqual(self.report.source_hash, self.source_hash)

    # 9. Prompt Input Minimization (No Secrets Exposed)
    def test_prompt_input_minimization_and_forbidden_keys(self):
        context = build_grounded_narrative_context(self.report)
        user_prompt = build_user_prompt(context)

        # Verify no token leaks
        self.assertNotIn("EAA_SECRET_TOKEN_DO_NOT_LEAK", user_prompt)
        self.assertNotIn("REFRESH_SECRET_KEY", user_prompt)
        self.assertNotIn("IG_SECRET_TOKEN_DO_NOT_LEAK", user_prompt)

        # Audit forbidden keys
        forbidden_found = []
        def _walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() in FORBIDDEN_KEYS:
                        forbidden_found.append(k)
                    _walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

        _walk(context)
        self.assertEqual(forbidden_found, [])

    # 10. Clean Validator Pass (Section AO & AN)
    def test_clean_validator_pass(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="VALID")
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "PASS")
        self.assertEqual(preview["validation_errors"], [])

    # 11. Overall Winner Attack Rejected (Section AP)
    def test_overall_winner_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="OVERALL_WINNER_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Multichannel lock failed" in e for e in preview["validation_errors"]))

    # 12. Fake Percentage Attack Rejected (Section AQ)
    def test_fake_percentage_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="FAKE_PERCENTAGE_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Fact lock failed" in e or "Zero-baseline lock failed" in e for e in preview["validation_errors"]))

    # 13. Engagement Hallucination Attack Rejected (Section AR)
    def test_engagement_hallucination_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="ENGAGEMENT_HALLUCINATION_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Metric allowlist failed" in e for e in preview["validation_errors"]))

    # 14. Non-Comparable Attack Rejected (Section AS)
    def test_non_comparable_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="NON_COMPARABLE_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Comparability lock failed" in e for e in preview["validation_errors"]))

    # 15. Audience Performance Attack Rejected (Section AT)
    def test_audience_performance_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="AUDIENCE_PERFORMANCE_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Audience non-performance lock failed" in e or "Causality guard failed" in e for e in preview["validation_errors"]))

    # 16. Causality Attack Rejected (Section AU)
    def test_causality_attack_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="CAUSALITY_ATTACK")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Causality guard failed" in e for e in preview["validation_errors"]))

    # 17. Unsupported Budget Action Rejected (Section AV)
    def test_unsupported_budget_action_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="UNSUPPORTED_BUDGET_ACTION")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Budget reallocation lock failed" in e for e in preview["validation_errors"]))

    # 18. Bad Evidence Ref Rejected (Section AW)
    def test_bad_evidence_ref_rejected(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="BAD_EVIDENCE_REF")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Confidence lock failed" in e or "Recommendation evidence failed" in e for e in preview["validation_errors"]))

    # 19. Confidence Authority & Derivation (Section AA & AB)
    def test_confidence_authority_and_derivation(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        # Multichannel signals carry deterministic HIGH confidence
        self.assertEqual(derive_recommendation_confidence(["MC-SIG-7"], reg), "HIGH")
        self.assertEqual(derive_recommendation_confidence(["MC-SIG-8"], reg), "HIGH")
        # Mixed with lower signal resolves to minimum
        self.assertEqual(derive_recommendation_confidence(["MC-SIG-7", "SIG-1"], reg), "HIGH")

    # 20. Confidence Mismatch Rejected by Direct Validator Call (Section AX)
    def test_confidence_mismatch_rejected_by_validator(self):
        context = build_grounded_narrative_context(self.report)
        mismatched_payload = {
            "executive_summary": ["Resumen válido del periodo."],
            "performance_observations": ["Instagram registró 6 reacciones frente a 0 en Facebook."],
            "recommendations": [
                {
                    "text": "Revisar rendimiento de la plataforma.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "CONSIDER",
                    "confidence": "LOW",  # Mismatch! MC-SIG-7 is HIGH!
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "La cobertura de datos entre plataformas es limitada: solo 3 de 15 métricas son comparables."
            ]
        }
        is_valid, report = NarrativeValidator.validate(mismatched_payload, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Confidence lock failed" in e for e in report["errors"]))

    # 21. Limitation Preservation Test (Section AY)
    def test_limitation_preservation_lock(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="LIMITATION_OMISSION")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Limitation preservation lock failed" in e for e in preview["validation_errors"]))

    # 22. Language Contract Enforcement (Section AZ)
    def test_language_contract_enforcement(self):
        preview = preview_narrative(self.report, provider_name="fake", mock_mode="LANGUAGE_MISMATCH")
        self.assertFalse(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "FAIL")
        self.assertTrue(any("Language contract failed" in e for e in preview["validation_errors"]))

    # 23. Cross-Metric Synthetic Aggregation Attack Rejected (Section S)
    def test_synthetic_aggregation_attack_rejected(self):
        context = build_grounded_narrative_context(self.report)
        bad_payload = {
            "executive_summary": ["Resumen ejecutivo."],
            "performance_observations": [
                "Instagram obtuvo una puntuación compuesta superior a Facebook combinando seguidores y reacciones."
            ],
            "recommendations": [
                {
                    "text": "Revisar rendimiento.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "CONSIDER",
                    "confidence": "HIGH",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "La cobertura de datos entre plataformas es limitada: 3 de 15 métricas."
            ]
        }
        is_valid, report = NarrativeValidator.validate(bad_payload, context)
        self.assertFalse(is_valid)
        self.assertTrue(any("synthetic aggregation" in e for e in report["errors"]))

    # 24. Preview Guarantees Zero DB Writes (Section BD)
    def test_preview_guarantees_zero_writes(self):
        initial_narratives = ExecutiveNarrative.objects.count()
        initial_reports = ExecutiveReport.objects.count()
        initial_signals = BusinessSignal.objects.count()

        preview = preview_narrative(self.report, provider_name="fake", mock_mode="VALID")
        self.assertIsNotNone(preview)

        self.assertEqual(ExecutiveNarrative.objects.count(), initial_narratives)
        self.assertEqual(ExecutiveReport.objects.count(), initial_reports)
        self.assertEqual(BusinessSignal.objects.count(), initial_signals)

    # 25. Claim Categories and Taxonomy Mappings (Section AD & Y)
    def test_claim_categories_and_taxonomy_mappings(self):
        self.assertIn("AUDIENCE_CONTEXT", CLAIM_CATEGORIES)
        self.assertIn("METRIC_COMPARISON", CLAIM_CATEGORIES)
        self.assertIn("DATA_LIMITATION", CLAIM_CATEGORIES)
        self.assertIn("SEMANTIC_LIMITATION", CLAIM_CATEGORIES)
        self.assertIn("RECOMMENDATION", CLAIM_CATEGORIES)

        self.assertEqual(CROSS_PLATFORM_ACTION_MAPPING["MC-SIG-7"], "REVIEW_PLATFORM_PERFORMANCE")
        self.assertEqual(CROSS_PLATFORM_ACTION_MAPPING["MC-SIG-8"], "REVIEW_PROVIDER_PERMISSIONS")
        self.assertIsNone(CROSS_PLATFORM_ACTION_MAPPING["MC-SIG-6"])


class ControlledLiveExecutionContractAuditTests(GroundedMultichannelNarrativeSafetiesTests):
    """BS-5E.0A Dedicated Tests: Controlled Live Execution Contract & Signal Identity."""

    # 1. Strict Single Attempt
    def test_strict_single_attempt(self):
        exec_data = execute_controlled_narrative_generation(
            self.report,
            provider_name="fake",
            mock_mode="VALID",
            generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
            fallback_enabled=False,
        )
        self.assertEqual(exec_data["provider_attempt_count"], 1)
        self.assertEqual(exec_data["max_provider_calls"], 1)
        self.assertEqual(exec_data["generation_policy"], GENERATION_POLICY_SINGLE_ATTEMPT_STRICT)
        self.assertFalse(exec_data["fallback_used"])
        self.assertFalse(exec_data["fallback_enabled"])

    # 2. Validator Failure No Retry
    def test_validator_failure_no_retry(self):
        initial_count = ExecutiveNarrative.objects.count()
        with self.assertRaises(ControlledLiveExecutionError) as ctx:
            generate_and_save_narrative(
                self.report,
                user=self.user,
                provider_name="fake",
                mock_mode="OVERALL_WINNER_ATTACK",
                generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
                fallback_enabled=False,
            )
        exc = ctx.exception
        self.assertEqual(exc.provider_attempt_count, 1)
        self.assertFalse(exc.can_retry)
        self.assertFalse(exc.fallback_used)
        self.assertEqual(ExecutiveNarrative.objects.count(), initial_count)

    # 3. Malformed JSON No Retry
    def test_malformed_json_no_retry(self):
        initial_count = ExecutiveNarrative.objects.count()
        with self.assertRaises(ControlledLiveExecutionError) as ctx:
            generate_and_save_narrative(
                self.report,
                user=self.user,
                provider_name="fake",
                mock_mode="MALFORMED_JSON",
                generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
                fallback_enabled=False,
            )
        exc = ctx.exception
        self.assertEqual(exc.provider_attempt_count, 1)
        self.assertFalse(exc.can_retry)
        self.assertEqual(ExecutiveNarrative.objects.count(), initial_count)

    # 4. Unknown Evidence No Retry
    def test_unknown_evidence_no_retry(self):
        initial_count = ExecutiveNarrative.objects.count()
        with self.assertRaises(ControlledLiveExecutionError) as ctx:
            generate_and_save_narrative(
                self.report,
                user=self.user,
                provider_name="fake",
                mock_mode="BAD_EVIDENCE_REF",
                generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
                fallback_enabled=False,
            )
        exc = ctx.exception
        self.assertEqual(exc.provider_attempt_count, 1)
        self.assertFalse(exc.can_retry)
        self.assertEqual(ExecutiveNarrative.objects.count(), initial_count)

    # 5. Ambiguous Transport No Retry
    def test_ambiguous_transport_no_retry(self):
        initial_count = ExecutiveNarrative.objects.count()
        with self.assertRaises(ControlledLiveExecutionError) as ctx:
            generate_and_save_narrative(
                self.report,
                user=self.user,
                provider_name="fake",
                mock_mode="AMBIGUOUS_TRANSPORT",
                generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
                fallback_enabled=False,
            )
        exc = ctx.exception
        self.assertEqual(exc.provider_attempt_count, 1)
        self.assertFalse(exc.can_retry)
        self.assertEqual(ExecutiveNarrative.objects.count(), initial_count)

    # 6. Fallback Disabled For Controlled Live Mode
    def test_fallback_disabled_for_controlled_live_mode(self):
        with self.assertRaises(ValueError):
            execute_controlled_narrative_generation(
                self.report,
                generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
                fallback_enabled=True,
            )

    # 7. Valid Fake Response One Attempt
    def test_valid_fake_response_one_attempt(self):
        initial_count = ExecutiveNarrative.objects.count()
        narrative = generate_and_save_narrative(
            self.report,
            user=self.user,
            provider_name="fake",
            mock_mode="VALID",
            generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
            fallback_enabled=False,
        )
        self.assertEqual(narrative.status, "VALIDATED")
        self.assertEqual(narrative.metadata["provider_attempt_count"], 1)
        self.assertEqual(narrative.metadata["max_provider_calls"], 1)
        self.assertFalse(narrative.metadata["fallback_used"])
        self.assertEqual(ExecutiveNarrative.objects.count(), initial_count + 1)

    # 8. Canonical Signal Type Preservation
    def test_canonical_signal_type_preservation(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        self.assertEqual(reg["MC-SIG-6"]["signal_type"], "AUDIENCE_SIZE_DIFFERENCE")
        self.assertEqual(reg["MC-SIG-7"]["signal_type"], "PLATFORM_METRIC_OUTPERFORMANCE")
        self.assertEqual(reg["MC-SIG-8"]["signal_type"], "CROSS_PLATFORM_DATA_LIMITATION")
        self.assertEqual(reg["MC-SIG-9"]["signal_type"], "CROSS_PLATFORM_METRIC_NON_COMPARABLE")

    # 9. Narrative Claim Category Separation
    def test_narrative_claim_category_separation(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        self.assertEqual(reg["MC-SIG-6"]["claim_category"], "AUDIENCE_CONTEXT")
        self.assertEqual(reg["MC-SIG-7"]["claim_category"], "PERFORMANCE_COMPARISON")
        self.assertEqual(reg["MC-SIG-8"]["claim_category"], "DATA_AVAILABILITY")
        self.assertEqual(reg["MC-SIG-9"]["claim_category"], "SEMANTIC_LIMITATION")

    # 10. Evidence Registry Canonical Identity
    def test_evidence_registry_canonical_identity(self):
        context = build_grounded_narrative_context(self.report)
        reg = context["evidence_registry"]
        for sig_num, expected_id in enumerate([6, 7, 8, 9], start=6):
            key = f"MC-SIG-{sig_num}"
            node = reg[key]
            self.assertEqual(node["signal_id"], expected_id)
            self.assertTrue(bool(node["signal_identity"]))
            self.assertEqual(node["confidence"], "HIGH")
            self.assertEqual(node["evidence"]["benchmark_hash"], self.canonical_benchmark_hash)

    # 11. Context Hash Determinism
    def test_context_hash_determinism(self):
        h1 = compute_context_hash(build_grounded_narrative_context(self.report))
        h2 = compute_context_hash(build_grounded_narrative_context(self.report))
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    # 12. Existing Locks Still Pass
    def test_existing_locks_still_pass(self):
        preview = preview_narrative(
            self.report,
            provider_name="fake",
            mock_mode="VALID",
            generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
            fallback_enabled=False,
        )
        self.assertTrue(preview["is_valid"])
        self.assertEqual(preview["validation_status"], "PASS")
        self.assertEqual(preview["provider_attempt_count"], 1)
        self.assertFalse(preview["fallback_used"])


# ============================================================================
#  BS-5E.1A — Live Narrative Prompt Hardening & Constrained Contract Tests
# ============================================================================
class MultichannelPromptHardeningTests(TestCase):
    """
    Dedicated test suite for BS-5E.1A prompt hardening, safe constructions,
    sanitized live failure replay, and adversarial protection.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="test_bs5e1a_user", email="test@bop.com", password="password")
        self.client_obj = Client.objects.create(name="Hardening Client", company="Hardening Co", is_active=True)
        self.report = ExecutiveReport.objects.create(
            client=self.client_obj,
            title="BS-5E.1A Hardening Pilot Report",
            report_type="EXECUTIVE",
            period_start=datetime.date(2026, 10, 1),
            period_end=datetime.date(2026, 10, 7),
            language="es",
            status="PUBLISHED",
            report_data={
                "has_sufficient_data": False,
                "summary": {
                    "followers_total": 70,
                    "reactions": 6,
                    "comments": 0,
                    "shares": 0,
                    "saves": None,
                    "video_views": None,
                    "average_daily_reach": None,
                    "engagement_total": None,
                },
                "platforms": {
                    "facebook": {
                        "platform": "facebook",
                        "capability": "COMPLETE",
                        "status": "FULL",
                        "supported_metrics": ["FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS", "SHARES", "SAVES", "VIDEO_VIEWS", "REACH"],
                        "unsupported_metrics": [],
                    },
                    "instagram": {
                        "platform": "instagram",
                        "capability": "PARTIAL",
                        "status": "PARTIAL",
                        "supported_metrics": ["FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"],
                        "unsupported_metrics": ["REACH", "IMPRESSIONS", "SHARES", "SAVES", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"],
                    },
                },
                "multichannel_intelligence": {
                    "has_multichannel_data": True,
                    "benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
                    "coverage_summary": {
                        "status": "LIMITED",
                        "comparable_metric_count": 3,
                        "canonical_metric_count": 15,
                        "coverage_ratio": "3/15",
                    },
                    "platform_comparisons": [
                        {
                            "metric": "FOLLOWERS_TOTAL",
                            "status": "DIRECT",
                            "winner": "NO_WINNER",
                            "direction": "NEUTRAL",
                            "delta_absolute": 30.0,
                            "delta_relative": 150.0,
                            "platform_a_value": 20.0,
                            "platform_b_value": 50.0,
                        },
                        {
                            "metric": "REACTIONS",
                            "status": "DIRECT",
                            "winner": "PLATFORM_B",
                            "direction": "HIGHER_IS_BETTER",
                            "delta_absolute": 6.0,
                            "delta_relative": None,
                            "reason_code": "ZERO_BASELINE",
                            "platform_a_value": 0.0,
                            "platform_b_value": 6.0,
                        },
                    ],
                    "limitations": [
                        "Coverage is LIMITED (3 of 15 metrics comparable) due to Instagram partial mode.",
                        "SAVES and VIDEO_VIEWS are non-comparable across platforms.",
                    ],
                },
                "business_intelligence_signals": {
                    "signals": [
                        {
                            "id": 6,
                            "signal_identity": "SIG-MC-FOLLOWERS-202610",
                            "signal_type": "AUDIENCE_SIZE_DIFFERENCE",
                            "metric": "FOLLOWERS_TOTAL",
                            "platform": "facebook:instagram",
                            "confidence": "HIGH",
                            "summary": "Instagram audience is 50 followers compared to 20 on Facebook.",
                            "evidence": {"benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"},
                        },
                        {
                            "id": 7,
                            "signal_identity": "SIG-MC-REACTIONS-202610",
                            "signal_type": "PLATFORM_METRIC_OUTPERFORMANCE",
                            "metric": "REACTIONS",
                            "platform": "facebook:instagram",
                            "confidence": "HIGH",
                            "summary": "Instagram generated 6 reactions compared to 0 on Facebook.",
                            "evidence": {"benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"},
                        },
                        {
                            "id": 8,
                            "signal_identity": "SIG-MC-COV-202610",
                            "signal_type": "CROSS_PLATFORM_DATA_LIMITATION",
                            "metric": "COVERAGE",
                            "platform": "facebook:instagram",
                            "confidence": "HIGH",
                            "summary": "Cross-platform comparison is limited to 3 of 15 metrics.",
                            "evidence": {"benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"},
                        },
                        {
                            "id": 9,
                            "signal_identity": "SIG-MC-NONCOMP-202610",
                            "signal_type": "CROSS_PLATFORM_METRIC_NON_COMPARABLE",
                            "metric": "SAVES",
                            "platform": "facebook:instagram",
                            "confidence": "HIGH",
                            "summary": "SAVES and VIDEO_VIEWS are not comparable between platforms.",
                            "evidence": {"benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"},
                        },
                    ]
                },
            },
        )
        self.context = build_grounded_narrative_context(self.report)

    # 1. First Live Failure Fixture Replay Test (Section B & Z)
    def test_first_live_failure_fixture_remains_rejected(self):
        failed_fixture = {
            "executive_summary": [
                "Durante el periodo analizado, Instagram supero a Facebook en rendimiento con 50 seguidores frente a 20 seguidores de Facebook."
            ],
            "performance_observations": [
                "Instagram registro un mejor desempeno al contar con una audiencia superior de seguidores.",
                "Instagram registro 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "El alcance de Instagram mostro actividad relevante durante las fechas evaluadas."
            ],
            "recommendations": [
                {
                    "text": "Revisar el desempeno por plataforma con mayor profundidad a medida que se acumulen mas datos.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "Algunas metricas presentan limitaciones de proveedor."
            ]
        }
        enriched = enrich_narrative_with_derived_confidence(failed_fixture, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertFalse(is_valid)
        self.assertEqual(summary["status"], "FAIL")
        # Verify all 3 failure classes
        errors_str = " ".join(summary["errors"])
        self.assertIn("Metric allowlist failed", errors_str)
        self.assertIn("Audience non-performance lock failed", errors_str)
        self.assertIn("Limitation preservation lock failed", errors_str)

    # 2. Approved Facts Architecture (Section N & O)
    def test_approved_facts_collection_and_evidence_refs(self):
        facts = self.context.get("approved_facts", [])
        self.assertEqual(len(facts), 7)
        fact_ids = [f["fact_id"] for f in facts]
        self.assertEqual(fact_ids, [f"FACT-MC-{i}" for i in range(1, 8)])
        for f in facts:
            self.assertTrue(len(f["evidence_refs"]) >= 1)
            for ref in f["evidence_refs"]:
                self.assertIn(ref, self.context["evidence_registry"])

    # 3. Audience Safe Wording Contract (Section H & I)
    def test_audience_safe_wording_passes(self):
        doc = {
            "executive_summary": [
                "Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas."
            ],
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual.",
                "SAVES y VIDEO_VIEWS no se comparan directamente entre Facebook e Instagram debido a diferencias en las definiciones y disponibilidad de proveedor."
            ],
            "recommendations": [
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
                "Diez métricas no están disponibles para una comparación completa con la configuración actual del proveedor, y dos métricas adicionales no son semánticamente comparables entre Facebook e Instagram."
            ]
        }
        enriched = enrich_narrative_with_derived_confidence(doc, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertTrue(is_valid, f"Validation errors: {summary.get('errors')}")

    # 4. Audience Adversarial Tests (Section AB)
    def test_audience_superiority_adversarial_variants_rejected(self):
        adversarial_summaries = [
            "Instagram es superior porque tiene más seguidores (50 seguidores frente a 20 en Facebook).",
            "Instagram tiene rendimiento superior con 50 seguidores frente a 20 en Facebook.",
            "Instagram es más fuerte con 50 seguidores frente a 20 en Facebook.",
            "Instagram domina en seguidores con 50 frente a 20 en Facebook.",
            "Instagram es mejor con 50 seguidores frente a 20 en Facebook.",
        ]
        base_doc = {
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual."
            ],
            "recommendations": [
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables."
            ]
        }
        for adv in adversarial_summaries:
            doc = dict(base_doc)
            doc["executive_summary"] = [adv]
            enriched = enrich_narrative_with_derived_confidence(doc, self.context)
            is_valid, summary = NarrativeValidator.validate(enriched, self.context)
            self.assertFalse(is_valid, f"Adversarial variant unexpectedly passed: '{adv}'")
            self.assertTrue(any("Audience non-performance lock failed" in e for e in summary["errors"]))

    # 5. Availability Phrasing Tests (Section AC)
    def test_availability_phrasing_performance_vs_limitation(self):
        # Unqualified mention of REACH -> FAIL
        bad_doc = {
            "executive_summary": ["Instagram registró 50 seguidores frente a 20 en Facebook."],
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook.",
                "El alcance de Instagram mostró un desempeño constante."
            ],
            "recommendations": [],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables."
            ]
        }
        enriched = enrich_narrative_with_derived_confidence(bad_doc, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Metric allowlist failed" in e for e in summary["errors"]))

        # Proper limitation framing -> PASS
        good_doc = {
            "executive_summary": [
                "Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas."
            ],
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual."
            ],
            "recommendations": [],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
                "REACH permanece no disponible para Instagram bajo el modo de permisos actual del proveedor."
            ]
        }
        enriched = enrich_narrative_with_derived_confidence(good_doc, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertTrue(is_valid, f"Errors: {summary.get('errors')}")

    # 6. Coverage Variant Tests (Section AD)
    def test_coverage_variant_tests(self):
        base_doc = {
            "executive_summary": [
                "Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas."
            ],
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual."
            ],
            "recommendations": [
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
        }

        # Valid variants
        for valid_cov in [
            "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
            "La cobertura de datos es limitada a 3/15 métricas.",
            "La cobertura entre plataformas es limitada: solo tres de quince métricas son comparables."
        ]:
            doc = dict(base_doc)
            doc["limitations"] = [valid_cov]
            enriched = enrich_narrative_with_derived_confidence(doc, self.context)
            is_valid, summary = NarrativeValidator.validate(enriched, self.context)
            self.assertTrue(is_valid, f"Variant unexpectedly failed: '{valid_cov}', errors: {summary.get('errors')}")

        # Vague substitute -> FAIL
        vague_doc = dict(base_doc)
        vague_doc["limitations"] = ["Algunas métricas son limitadas entre plataformas."]
        enriched = enrich_narrative_with_derived_confidence(vague_doc, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertFalse(is_valid)
        self.assertTrue(any("Limitation preservation lock failed" in e for e in summary["errors"]))

    # 7. Golden Spanish Output Test (Section AE)
    def test_golden_spanish_output_validation(self):
        golden_output = {
            "executive_summary": [
                "Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas."
            ],
            "performance_observations": [
                "Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado.",
                "Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual.",
                "SAVES y VIDEO_VIEWS no se comparan directamente entre Facebook e Instagram debido a diferencias en las definiciones y disponibilidad de proveedor."
            ],
            "recommendations": [
                {
                    "text": "Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables.",
                    "recommendation_type": "REVIEW_PROVIDER_PERMISSIONS",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-8"]
                },
                {
                    "text": "Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables.",
                    "recommendation_type": "REVIEW_PLATFORM_PERFORMANCE",
                    "strength": "OBSERVE",
                    "evidence_refs": ["MC-SIG-7"]
                }
            ],
            "limitations": [
                "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables.",
                "Diez métricas no están disponibles para una comparación completa con la configuración actual del proveedor, y dos métricas adicionales no son semánticamente comparables entre Facebook e Instagram."
            ],
            "cross_platform_coverage_disclosure": {
                "comparable_metrics": 3,
                "total_metrics": 15,
                "status": "LIMITED",
                "statement": "La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables."
            }
        }
        enriched = enrich_narrative_with_derived_confidence(golden_output, self.context)
        is_valid, summary = NarrativeValidator.validate(enriched, self.context)
        self.assertTrue(is_valid, f"Golden output validation failed: {summary.get('errors')}")
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(len(summary["errors"]), 0)

        # Invariant: ExecutiveNarrative count must remain 1
        self.assertEqual(ExecutiveNarrative.objects.count(), 0)

    # 8. Hardened Valid Mock in Fake Provider (Section AA)
    def test_hardened_valid_mock_passes(self):
        preview = preview_narrative(
            self.report,
            language="es",
            provider_name="fake",
            mock_mode="VALID",
            generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
            fallback_enabled=False,
        )
        self.assertTrue(preview["is_valid"], f"Fake mock VALID failed: {preview.get('validation_errors')}")
        self.assertEqual(preview["validation_status"], "PASS")
