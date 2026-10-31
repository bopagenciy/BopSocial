"""
Unit Tests for BS-6A Artifact Reuse and Idempotency (Test Matrix AR).
Verifies that existing BusinessSignals, ExecutiveReport, and ExecutiveNarrative
are deterministically recognized, reused, and not regenerated.
"""
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
    Client,
    ExecutiveNarrative,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation.constants import (
    AutomationStage,
    AutomationStatus,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.eligibility import evaluate_intelligence_automation_eligibility
from social_stats.analytics.automation.orchestrator import preview_intelligence_automation


class IntelligenceAutomationIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="idemp_user", email="idemp@example.com")
        self.client_obj = Client.objects.create(
            name="Canonical Client",
            company="Canonical Co",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client_obj,
            enabled=True,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=False,
            minimum_period_coverage_percent=0,
            provider_call_budget=1,
            max_retry_count=0,
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            is_active=True,
            access_token="test_token_canonical",
        )
        self.period_start = date(2026, 9, 22)
        self.period_end = date(2026, 10, 22)

        # Snapshots and Rollups
        SocialMetricSnapshot.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=12000.0,
            bucket_period="DAY",
            bucket_timestamp=timezone.now() - timedelta(hours=1),
            dimensions_hash="snap_hash_idemp",
        )
        SocialMetricRollup.objects.create(
            client=self.client_obj,
            platform="facebook",
            metric_scope="account",
            normalized_metric="IMPRESSIONS",
            metric_value=350000.0,
            period="CUSTOM",
            period_start=self.period_start,
        )
        SyncLog.objects.create(
            client=self.client_obj,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=1),
        )

        # Compute deterministic source identity (BS-6D.1B)
        from social_stats.analytics.automation.identity import get_deterministic_report_source_hash
        from social_stats.analytics.narrative.context import build_grounded_narrative_context, compute_context_hash

        src_hash = get_deterministic_report_source_hash(
            self.client_obj.id,
            self.period_start,
            self.period_end,
        )

        # Existing ExecutiveReport with deterministic source identity
        self.report = ExecutiveReport.objects.create(
            client=self.client_obj,
            report_type="EXECUTIVE",
            period_start=self.period_start,
            period_end=self.period_end,
            language="es",
            status="GENERATED",
            title="Informe Ejecutivo Canonico",
            source_hash=src_hash,
            report_data={"summary": "Canonical Report"},
        )

        ctx_hash = compute_context_hash(build_grounded_narrative_context(self.report))

        # Existing VALIDATED ExecutiveNarrative with matching context identity
        self.narrative = ExecutiveNarrative.objects.create(
            client=self.client_obj,
            executive_report=self.report,
            language="es",
            status="VALIDATED",
            provider="ollama",
            model_name="qwen3.5:9b",
            prompt_version="bs5e-prompt-v3",
            source_hash=src_hash,
            context_hash=ctx_hash,
            narrative_json={"executive_summary": ["Grounded summary text"]},
            rendered_text="Grounded summary text",
            validation_status="PASS",
        )

    def test_existing_artifacts_reuse_decision(self):
        """When report and narrative already exist and are valid, planned stages are empty and reuse is logged."""
        eligibility = evaluate_intelligence_automation_eligibility(
            client_id=self.client_obj.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )

        self.assertTrue(eligibility.eligible)
        self.assertIn("REPORT_CHECK", eligibility.skipped_stages)
        self.assertIn("NARRATIVE_CHECK", eligibility.skipped_stages)
        self.assertIn(f"REUSE ExecutiveReport #{self.report.id}", eligibility.reuse_decisions["report"])
        self.assertIn(f"REUSE ExecutiveNarrative #{self.narrative.id}", eligibility.reuse_decisions["narrative"])
        self.assertNotIn("REPORT_CHECK", eligibility.planned_stages)
        self.assertNotIn("NARRATIVE_CHECK", eligibility.planned_stages)

    def test_repeated_dry_run_zero_db_mutation(self):
        """Executing preview multiple times produces identical deterministic plan and mutates 0 rows."""
        report_count_before = ExecutiveReport.objects.count()
        narrative_count_before = ExecutiveNarrative.objects.count()
        run_count_before = IntelligenceAutomationRun.objects.count()

        for _ in range(3):
            preview = preview_intelligence_automation(
                client_id=self.client_obj.id,
                period_start=self.period_start,
                period_end=self.period_end,
            )
            self.assertTrue(preview["eligible"])
            self.assertEqual(preview["existing_artifacts"]["matching_report_id"], self.report.id)
            self.assertEqual(preview["existing_artifacts"]["matching_narrative_id"], self.narrative.id)

        self.assertEqual(ExecutiveReport.objects.count(), report_count_before)
        self.assertEqual(ExecutiveNarrative.objects.count(), narrative_count_before)
        self.assertEqual(IntelligenceAutomationRun.objects.count(), run_count_before)
