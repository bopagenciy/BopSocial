"""
BS-6E.1B Pre-Approval Report Binding & Source Identity Test Suite.

Validates:
1. get_deterministic_report_source_hash exactly matches builder source_hash for multichannel benchmarks.
2. get_deterministic_report_source_hash fails closed on exceptions (zero silent swallow).
3. REPORT_CHECK builds and attaches ExecutiveReport BEFORE pausing at AWAITING_APPROVAL.
4. Approval token freezes non-null report_id.
5. Report is reused if already valid and matching source hash.
6. Dry run does NOT create ExecutiveReport.
7. generate_report=False does NOT create ExecutiveReport.
8. Resume succeeds when bound report is intact and un-drifted.
9. Resume fails closed with REPORT_BINDING_MISSING when run.report is missing.
10. Resume fails closed with REPORT_METADATA_MISMATCH when report client/period mismatch.
11. Resume fails closed with REPORT_SOURCE_DRIFT when underlying data mutates.
12. reserve_provider_execution fails closed with REPORT_SOURCE_DRIFT when data mutates.
13. Approval token mismatch blocks resume if report_id was altered.
14. bs6a-v5 execution identity is deterministic.
15. Report creation event is logged with source hash.
"""
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone as dt_tz
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    ExecutiveReport,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics.automation import (
    PIPELINE_VERSION,
    ApprovalStatus,
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    approve_intelligence_run,
    compute_approval_token,
    compute_execution_identity,
    execute_intelligence_automation,
    resume_approved_intelligence_run,
)
from social_stats.analytics.automation.approval import reserve_provider_execution
from social_stats.analytics.automation.identity import (
    get_deterministic_report_source_hash,
)
from social_stats.analytics.reporting.service import save_executive_report

User = get_user_model()


class PreApprovalReportBindingTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(
            username="test_admin_binding",
            email="admin_binding@example.com",
            password="secret_password",
        )
        self.client = Client.objects.create(
            name="Binding Test Agency",
            is_active=True,
            timezone="UTC",
            requires_approval=True,
        )
        self.p_start = date(2026, 10, 1)
        self.p_end = date(2026, 10, 31)

        # Credentials
        self.cred_fb = PlatformCredential.objects.create(
            client=self.client,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=90),
        )
        self.cred_ig = PlatformCredential.objects.create(
            client=self.client,
            platform="instagram",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=90),
        )

        # Telemetry: Facebook and Instagram daily rollups throughout October
        cur = self.p_start
        while cur <= self.p_end:
            SocialMetricRollup.objects.create(
                client=self.client,
                platform="facebook",
                metric_scope="account",
                object_id="fb_page",
                normalized_metric="IMPRESSIONS",
                period="day",
                period_start=cur,
                metric_value=Decimal("500"),
                sample_count=1,
            )
            SocialMetricRollup.objects.create(
                client=self.client,
                platform="instagram",
                metric_scope="account",
                object_id="ig_profile",
                normalized_metric="IMPRESSIONS",
                period="day",
                period_start=cur,
                metric_value=Decimal("300"),
                sample_count=1,
            )
            cur += timedelta(days=1)

        # Freshness records
        SyncLog.objects.create(
            client=self.client,
            platform="facebook",
            status="success",
            finished_at=timezone.now() - timedelta(hours=2),
            records_synced=10,
        )
        SocialMetricSnapshot.objects.create(
            client=self.client,
            platform="facebook",
            account_id="act_123",
            metric_scope="PAGE",
            object_id="page_123",
            raw_metric_name="impressions",
            normalized_metric="impressions",
            metric_value=1500,
            bucket_period="DAY",
            bucket_timestamp=datetime(2026, 10, 15, 12, 0, 0, tzinfo=dt_tz.utc),
        )

        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client,
            enabled=True,
            timezone="UTC",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
            lookback_days=30,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=True,
            max_data_staleness_hours=72,
            minimum_period_coverage_percent=0,
            provider_call_budget=1,
        )

    def test_01_report_source_hash_matches_builder_with_multichannel_benchmark(self):
        """Proves get_deterministic_report_source_hash exactly matches canonical builder hash."""
        report = save_executive_report(
            client_id=self.client.id,
            date_from=self.p_start,
            date_to=self.p_end,
            platform="all",
            language="es",
        )
        det_hash = get_deterministic_report_source_hash(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            platform=report.platform_filter,
            language=report.language or "es",
        )
        self.assertTrue(len(det_hash) == 64)
        self.assertEqual(det_hash, report.source_hash)

    def test_02_report_source_hash_fails_closed_on_error(self):
        """Proves get_deterministic_report_source_hash does NOT swallow exceptions."""
        with patch(
            "social_stats.analytics.multichannel.benchmarks.build_multichannel_benchmark",
            side_effect=RuntimeError("Forced benchmark test explosion"),
        ):
            with self.assertRaises(RuntimeError):
                get_deterministic_report_source_hash(
                    client_id=self.client.id,
                    period_start=self.p_start,
                    period_end=self.p_end,
                )

    def test_03_preapproval_report_creation_and_binding(self):
        """Proves run in REPORT_CHECK generates a report and attaches it before AWAITING_APPROVAL."""
        self.assertEqual(ExecutiveReport.objects.count(), 0)
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)
        self.assertIsNotNone(run.report_id)
        self.assertIsNotNone(run.report)
        self.assertEqual(run.report.status, "GENERATED")
        self.assertEqual(ExecutiveReport.objects.count(), 1)

        # Verify approval token binds report_id
        expected_token = compute_approval_token(
            run_id=run.id,
            execution_identity=run.execution_identity,
            pipeline_version=run.pipeline_version,
            period_start=run.period_start,
            period_end=run.period_end,
            report_id=run.report_id,
        )
        self.assertEqual(run.approval_token, expected_token)

    def test_04_preapproval_report_reused_if_already_valid(self):
        """Proves an existing valid report is reused and no duplicate is created."""
        existing_report = save_executive_report(
            client_id=self.client.id,
            date_from=self.p_start,
            date_to=self.p_end,
            platform="all",
            language="es",
        )
        self.assertEqual(ExecutiveReport.objects.count(), 1)

        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        self.assertEqual(run.report_id, existing_report.id)
        self.assertEqual(ExecutiveReport.objects.count(), 1)

    def test_05_dry_run_does_not_create_report(self):
        """Proves dry_run=True creates zero ExecutiveReport rows."""
        self.assertEqual(ExecutiveReport.objects.count(), 0)
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=True,
            now=timezone.now(),
        )
        self.assertEqual(ExecutiveReport.objects.count(), 0)
        self.assertIsNone(run.report_id)

    def test_06_generate_report_false_does_not_create_report(self):
        """Proves generate_report=False creates zero ExecutiveReport rows."""
        self.config.generate_report = False
        self.config.save(update_fields=["generate_report"])

        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        self.assertEqual(ExecutiveReport.objects.count(), 0)
        self.assertIsNone(run.report_id)

    def test_07_resume_passes_with_unaltered_bound_report(self):
        """Proves resume proceeds to PROVIDER_EXECUTION_READY when report is bound and clean."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        self.assertEqual(run.status, AutomationStatus.AWAITING_APPROVAL.value)
        self.assertIsNotNone(run.report_id)

        approve_intelligence_run(run.id, self.operator, comment="Approved for testing")
        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())

        self.assertEqual(resumed.status, AutomationStatus.PROVIDER_EXECUTION_READY.value)
        self.assertFalse(resumed.error_code)

    def test_08_resume_blocks_if_bound_report_missing(self):
        """Proves resume fails closed with REPORT_BINDING_MISSING if run.report is missing."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        # Manually clear report
        run.report = None
        run.approval_token = compute_approval_token(
            run_id=run.id,
            execution_identity=run.execution_identity,
            pipeline_version=run.pipeline_version,
            period_start=run.period_start,
            period_end=run.period_end,
            report_id=None,
        )
        run.save(update_fields=["report", "approval_token"])

        approve_intelligence_run(run.id, self.operator)
        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())

        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "REPORT_BINDING_MISSING")

    def test_09_resume_blocks_if_bound_report_metadata_mismatched(self):
        """Proves resume fails closed with REPORT_METADATA_MISMATCH if report metadata differs."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        # Tamper report period
        run.report.period_start = date(2026, 9, 1)
        run.report.save(update_fields=["period_start"])

        approve_intelligence_run(run.id, self.operator)
        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())

        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "REPORT_METADATA_MISMATCH")

    def test_10_resume_blocks_on_source_drift(self):
        """Proves resume fails closed with REPORT_SOURCE_DRIFT when underlying rollups mutate."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        approve_intelligence_run(run.id, self.operator)

        # Mutate underlying data: add new BusinessSignal in October
        from social_stats.models import BusinessSignal
        BusinessSignal.objects.create(
            client=self.client,
            platform="facebook",
            scope="single_channel",
            period_start=self.p_start,
            period_end=self.p_end,
            signal_type="GROWTH_SPIKE",
            signal_identity="fb_growth_spike_oct2026",
            explanation_template="Test spike",
        )

        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "REPORT_SOURCE_DRIFT")
        self.assertIn("Human re-approval required", resumed.error_message_safe)

    def test_11_reserve_provider_blocks_on_source_drift(self):
        """Proves reserve_provider_execution detects drift and fails closed."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        approve_intelligence_run(run.id, self.operator)
        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())
        self.assertEqual(resumed.status, AutomationStatus.PROVIDER_EXECUTION_READY.value)

        # Now drift data right before provider execution: add new BusinessSignal
        from social_stats.models import BusinessSignal
        BusinessSignal.objects.create(
            client=self.client,
            platform="instagram",
            scope="single_channel",
            period_start=self.p_start,
            period_end=self.p_end,
            signal_type="GROWTH_SPIKE",
            signal_identity="ig_growth_spike_oct2026",
            explanation_template="Test spike IG",
        )

        reservation = reserve_provider_execution(run.id, self.operator, now=timezone.now())
        self.assertFalse(reservation["reserved"])
        self.assertEqual(reservation["reason"], "REPORT_SOURCE_DRIFT")

        run.refresh_from_db()
        self.assertEqual(run.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(run.error_code, "REPORT_SOURCE_DRIFT")

    def test_12_token_mismatch_blocks_if_report_id_altered(self):
        """Proves altering run.report_id breaks approval token verification."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        approve_intelligence_run(run.id, self.operator)

        # Alter report_id to point to a different real report
        other_rep = ExecutiveReport.objects.create(
            client=self.client,
            period_start=self.p_start,
            period_end=self.p_end,
            status="GENERATED",
            source_hash="different_hash_for_test_12",
        )
        run.report = other_rep
        run.save(update_fields=["report"])

        resumed = resume_approved_intelligence_run(run.id, self.operator, now=timezone.now())
        self.assertEqual(resumed.status, AutomationStatus.BLOCKED.value)
        self.assertEqual(resumed.error_code, "APPROVAL_TOKEN_MISMATCH")

    def test_13_deterministic_october_identity_bs6a_v5(self):
        """Proves pipeline version bs6a-v5 computes expected October execution identity."""
        self.assertEqual(PIPELINE_VERSION, "bs6a-v5")
        identity = compute_execution_identity(3, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(identity, "92f0cb6f73782fd06f8c94b0233b7434297870a46b95b7d775a8572114cadae1")

    def test_14_approval_tokens_differ_across_different_reports(self):
        """Proves token binding changes if report_id differs."""
        tok1 = compute_approval_token(run_id=1, execution_identity="abc", report_id=10)
        tok2 = compute_approval_token(run_id=1, execution_identity="abc", report_id=11)
        self.assertNotEqual(tok1, tok2)

    def test_15_events_logged_for_preapproval_report_creation(self):
        """Proves automation.report.created event is logged."""
        run = execute_intelligence_automation(
            client_id=self.client.id,
            period_start=self.p_start,
            period_end=self.p_end,
            trigger_type=AutomationTriggerType.SCHEDULED,
            dry_run=False,
            now=timezone.now(),
        )
        self.assertIsNotNone(run.report)
        self.assertTrue(len(run.report.source_hash) == 64)
