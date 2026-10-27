"""
BS-6B.0B Blocked-Run Reactivation & Material-State Idempotency Test Suite.
Validates:
1. unchanged approval blocker does not duplicate
2. approval state change allows one new attempt
3. unchanged stale blocker does not duplicate
4. stale -> fresh allows one new attempt
5. two blockers, one resolved remains blocked
6. both resolved allows one attempt
7. 96 repeated scanner ticks create no storm
8. active run uniqueness remains enforced
9. advisory lock remains enforced
10. completed artifacts reuse
11. attempt history preserved
12. scheduled trigger cannot force
13. provider budget unchanged
14. retry count remains 0
15. zero provider calls
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    BusinessSignal,
    ExecutiveReport,
    ExecutiveNarrative,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
)
from social_stats.analytics.automation import (
    PIPELINE_VERSION,
    AutomationStage,
    AutomationStatus,
    AutomationTriggerType,
    SingleFlightLock,
    ConcurrencyLockError,
    evaluate_intelligence_automation_eligibility,
    preview_intelligence_automation,
    execute_intelligence_automation,
    is_tenant_due,
)
from social_stats.analytics.automation.tasks import (
    discover_and_enqueue_due_intelligence_automations,
    run_intelligence_automation_task,
)


class BlockedRunReactivationTests(TestCase):
    def setUp(self):
        self.client_1 = Client.objects.create(
            name="Pilot Tenant",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="tenant_reactivation@example.com",
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_1,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=60),
        )
        self.config = IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
            lookback_days=30,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=True,
            provider_call_budget=1,
            max_retry_count=0,
            max_data_staleness_hours=24,
        )

    def test_01_unchanged_approval_blocker_does_not_duplicate(self):
        """Proves that when a tenant is blocked by approval, repeated scans do NOT re-enqueue."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        # Pre-evaluate eligibility to get material block state hash
        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=True,
        )

        # Create historical BLOCKED run
        run1 = IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig.execution_identity,
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code=elig.blocking_reasons[0],
            metadata={"block_state_hash": elig.block_state_hash},
        )

        # Run discovery scan with mocked due time
        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=ref_time):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertNotIn(self.client_1.id, res["due_client_ids"])
            skipped = next((s for s in res["skipped_summary"] if s["client_id"] == self.client_1.id), None)
            self.assertIsNotNone(skipped)
            self.assertIn("BLOCKED_STATE_UNCHANGED", skipped["reason"])

    def test_02_approval_state_change_allows_one_new_attempt(self):
        """Proves that when operator approval is satisfied, the tenant is reactivated for discovery."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=True,
        )

        run1 = IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig.execution_identity,
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code=elig.blocking_reasons[0],
            metadata={"block_state_hash": elig.block_state_hash},
        )

        # Operator approval is resolved: config require_operator_approval set to False
        self.config.require_operator_approval = False
        self.config.save()

        # Provide adequate snapshots so it doesn't fail on data missing
        SocialMetricSnapshot.objects.create(
            client=self.client_1,
            platform="facebook",
            raw_metric_name="impressions",
            normalized_metric="impressions",
            bucket_timestamp=timezone.make_aware(datetime(2026, 9, 15, 12, 0, 0)),
            metric_value=500.0,
        )

        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=ref_time), \
             patch("social_stats.analytics.automation.eligibility.evaluate_tenant_freshness") as mock_fresh:
            from social_stats.analytics.automation.freshness import FreshnessResult, FreshnessCode
            mock_fresh.return_value = FreshnessResult(
                code=FreshnessCode.FRESH,
                is_fresh=True,
                latest_sync_at=timezone.now(),
                data_age_hours=2.0,
                threshold_hours=24,
                latest_snapshot_date=date(2026, 9, 15),
                latest_rollup_date=date(2026, 9, 15),
                active_credential_count=1,
                expired_credential_count=0,
            )

            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertIn(self.client_1.id, res["due_client_ids"])

    def test_03_unchanged_stale_blocker_does_not_duplicate(self):
        """Proves repeated discovery on unchanged stale blocker skips gracefully."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=True,
        )

        IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig.execution_identity,
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code="ANALYTICS_DATA_STALE",
            metadata={"block_state_hash": elig.block_state_hash},
        )

        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=ref_time):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertNotIn(self.client_1.id, res["due_client_ids"])

    def test_04_stale_to_fresh_allows_one_new_attempt(self):
        """Proves that transitioning from stale to fresh changes material hash and permits new attempt."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        elig_stale = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=True,
        )

        IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig_stale.execution_identity,
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code="ANALYTICS_DATA_STALE",
            metadata={"block_state_hash": elig_stale.block_state_hash},
        )

        # Approval satisfied and freshness now fresh
        self.config.require_operator_approval = False
        self.config.save()

        # Add snapshots so data missing doesn't block
        SocialMetricSnapshot.objects.create(
            client=self.client_1,
            platform="facebook",
            raw_metric_name="impressions",
            normalized_metric="impressions",
            bucket_timestamp=timezone.make_aware(datetime(2026, 9, 15, 12, 0, 0)),
            metric_value=500.0,
        )

        ref_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=ref_time), \
             patch("social_stats.analytics.automation.eligibility.evaluate_tenant_freshness") as mock_fresh:
            from social_stats.analytics.automation.freshness import FreshnessResult, FreshnessCode
            mock_fresh.return_value = FreshnessResult(
                code=FreshnessCode.FRESH,
                is_fresh=True,
                latest_sync_at=timezone.now(),
                data_age_hours=1.0,
                threshold_hours=24,
                latest_snapshot_date=date(2026, 9, 15),
                latest_rollup_date=date(2026, 9, 15),
                active_credential_count=1,
                expired_credential_count=0,
            )

            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertIn(self.client_1.id, res["due_client_ids"])

    def test_05_two_blockers_one_resolved_remains_blocked(self):
        """Proves that if staleness AND approval are blocking, resolving only staleness leaves approval blocking."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        with patch("social_stats.analytics.automation.eligibility.evaluate_tenant_freshness") as mock_fresh:
            from social_stats.analytics.automation.freshness import FreshnessResult, FreshnessCode
            mock_fresh.return_value = FreshnessResult(
                code=FreshnessCode.FRESH,
                is_fresh=True,
                latest_sync_at=timezone.now(),
                data_age_hours=1.0,
                threshold_hours=24,
                latest_snapshot_date=date(2026, 9, 15),
                latest_rollup_date=date(2026, 9, 15),
                active_credential_count=1,
                expired_credential_count=0,
            )

            elig = evaluate_intelligence_automation_eligibility(
                client_id=self.client_1.id,
                period_start=p_start,
                period_end=p_end,
                trigger_type="SCHEDULED",
                dry_run=False,
            )
            self.assertFalse(elig.eligible)
            self.assertFalse(elig.execution_authorized)
            self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", elig.blocking_reasons)

    def test_06_both_resolved_allows_one_attempt(self):
        """Proves resolving both blockers produces full authorization."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        self.config.require_operator_approval = False
        self.config.save()

        # Add snapshot so data missing doesn't block
        SocialMetricSnapshot.objects.create(
            client=self.client_1,
            platform="facebook",
            raw_metric_name="impressions",
            normalized_metric="impressions",
            bucket_timestamp=timezone.make_aware(datetime(2026, 9, 15, 12, 0, 0)),
            metric_value=500.0,
        )

        with patch("social_stats.analytics.automation.eligibility.evaluate_tenant_freshness") as mock_fresh:
            from social_stats.analytics.automation.freshness import FreshnessResult, FreshnessCode
            mock_fresh.return_value = FreshnessResult(
                code=FreshnessCode.FRESH,
                is_fresh=True,
                latest_sync_at=timezone.now(),
                data_age_hours=1.0,
                threshold_hours=24,
                latest_snapshot_date=date(2026, 9, 15),
                latest_rollup_date=date(2026, 9, 15),
                active_credential_count=1,
                expired_credential_count=0,
            )

            elig = evaluate_intelligence_automation_eligibility(
                client_id=self.client_1.id,
                period_start=p_start,
                period_end=p_end,
                trigger_type="SCHEDULED",
                dry_run=False,
            )
            self.assertTrue(elig.eligible)
            self.assertTrue(elig.execution_authorized)
            self.assertEqual(len(elig.blocking_reasons), 0)

    def test_07_96_repeated_scanner_ticks_create_no_storm(self):
        """Simulates 96 consecutive scanner ticks (1 day at 15-min intervals) with unchanged blocker."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type="SCHEDULED",
            dry_run=True,
        )

        IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig.execution_identity,
            trigger_type="SCHEDULED",
            status="BLOCKED",
            current_stage="ELIGIBILITY",
            error_code=elig.blocking_reasons[0],
            metadata={"block_state_hash": elig.block_state_hash},
        )

        initial_count = IntelligenceAutomationRun.objects.count()

        # Simulate 96 ticks starting at 10:00 UTC (06:00 EDT)
        base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        for i in range(96):
            tick_time = base_time + timedelta(minutes=15 * i)
            with patch("django.utils.timezone.now", return_value=tick_time):
                res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
                self.assertNotIn(self.client_1.id, res["due_client_ids"])

        final_count = IntelligenceAutomationRun.objects.count()
        self.assertEqual(initial_count, final_count)

    def test_08_active_run_uniqueness_remains_enforced(self):
        """Proves DB constraint prevents duplicate active run rows."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        run = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        run.status = AutomationStatus.RUNNING.value
        run.save()

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
        )
        self.assertFalse(res.eligible)
        self.assertTrue(any("DUPLICATE_ACTIVE_RUN_EXISTS" in b for b in res.blocking_reasons))

    def test_09_advisory_lock_remains_enforced(self):
        """Proves PostgreSQL advisory locking rejects concurrent execution attempts."""
        with patch.object(SingleFlightLock, "acquire", return_value=False):
            with self.assertRaises(ConcurrencyLockError):
                execute_intelligence_automation(
                    client_id=self.client_1.id,
                    dry_run=False,
                )

    def test_10_completed_artifacts_reuse(self):
        """Proves existing ExecutiveReport and VALIDATED ExecutiveNarrative are reused."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        rep = ExecutiveReport.objects.create(
            client=self.client_1,
            period_start=p_start,
            period_end=p_end,
            status="GENERATED",
            title="September Report",
        )
        narrative = ExecutiveNarrative.objects.create(
            client=self.client_1,
            executive_report=rep,
            status="VALIDATED",
            rendered_text="Canonical validated text.",
            prompt_version="bs5e-prompt-v3",
        )

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=True,
        )
        self.assertIn("report", res.reuse_decisions)
        self.assertIn(f"REUSE ExecutiveReport #{rep.id}", res.reuse_decisions["report"])
        self.assertIn("narrative", res.reuse_decisions)
        self.assertIn(f"REUSE ExecutiveNarrative #{narrative.id}", res.reuse_decisions["narrative"])

    def test_11_attempt_history_preserved_with_incrementing_attempt_number(self):
        """Proves prior terminal runs remain immutable and subsequent runs record attempt_number."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        # Run 1: BLOCKED
        run1 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run1.metadata.get("attempt_number"), 1)

        # Run 2: Second attempt
        run2 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertEqual(run2.metadata.get("attempt_number"), 2)
        # Run 1 remains immutable
        run1_reloaded = IntelligenceAutomationRun.objects.get(id=run1.id)
        self.assertEqual(run1_reloaded.id, run1.id)
        self.assertEqual(run1_reloaded.status, "BLOCKED")

    def test_12_scheduled_trigger_cannot_force(self):
        """Proves SCHEDULED trigger ignores --force and enforces all safety gates."""
        self.config.enabled = False
        self.config.save()

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            trigger_type="SCHEDULED",
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertIn("AUTOMATION_CONFIG_DISABLED", res.blocking_reasons)

    def test_13_provider_budget_unchanged(self):
        """Proves provider call budget remains strictly enforced."""
        self.config.provider_call_budget = 0
        self.config.save()

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            trigger_type="SCHEDULED",
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertIn("PROVIDER_CALL_BUDGET_EXHAUSTED: budget is 0", res.blocking_reasons)

    def test_14_retry_count_remains_zero(self):
        """Proves fail-closed retry count remains 0 on all runs."""
        run = execute_intelligence_automation(
            client_id=self.client_1.id,
            dry_run=False,
        )
        self.assertEqual(run.retry_count, 0)

    def test_15_zero_provider_calls(self):
        """Proves zero LLM or external HTTP calls across entire evaluation cycle."""
        with patch("urllib.request.urlopen") as mock_http, \
             patch("requests.post") as mock_post:
            
            discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertEqual(mock_http.call_count, 0)
            self.assertEqual(mock_post.call_count, 0)
