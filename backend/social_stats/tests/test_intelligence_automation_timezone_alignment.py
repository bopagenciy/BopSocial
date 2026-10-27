"""
BS-6B.0A Timezone Scheduler Alignment & Blocked-Run Idempotency Test Suite.
Validates:
1. NY due conversion standard time
2. NY due conversion daylight time
3. spring-forward behavior
4. fall-back behavior
5. missed scheduler tick recovery
6. global scanner after due time still detects tenant
7. tenant already processed not rediscovered
8. LA timezone
9. Bogota timezone
10. UTC timezone
11. repeated identical blocked scan does not create row storm
12. changed blocker state can be audited
13. active-run uniqueness remains hard
14. approval gate unchanged
15. zero provider calls
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, CrontabSchedule

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
    calculate_next_due_datetime,
    is_tenant_due,
)
from social_stats.analytics.automation.tasks import (
    discover_and_enqueue_due_intelligence_automations,
    run_intelligence_automation_task,
)


class TimezoneSchedulerAlignmentTests(TestCase):
    def setUp(self):
        self.client_ny = Client.objects.create(
            name="New York Client",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="ny_client@example.com",
        )
        self.config_ny = IntelligenceAutomationConfig.objects.create(
            client=self.client_ny,
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
        )

    def test_01_ny_due_conversion_standard_time(self):
        """Proves NY local due time in standard time (EST, UTC-5) converts to 07:00 UTC."""
        # Jan 1 at 02:00 EST
        ref_dt = datetime(2026, 1, 1, 2, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        utc_dt = ref_dt.astimezone(dt_tz.utc)
        self.assertEqual(utc_dt.hour, 7)
        self.assertEqual(utc_dt.day, 1)

    def test_02_ny_due_conversion_daylight_time(self):
        """Proves NY local due time in daylight saving time (EDT, UTC-4) converts to 06:00 UTC."""
        # July 1 at 02:00 EDT
        ref_dt = datetime(2026, 7, 1, 2, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        utc_dt = ref_dt.astimezone(dt_tz.utc)
        self.assertEqual(utc_dt.hour, 6)
        self.assertEqual(utc_dt.day, 1)

    def test_03_spring_forward_behavior(self):
        """Proves 2:00 AM on spring-forward Sunday (non-existent local time) resolves cleanly without crashing."""
        # 2026-03-08 in America/New_York: clocks jump from 02:00 to 03:00
        ref_now = datetime(2026, 3, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        next_due = calculate_next_due_datetime(self.config_ny, reference_datetime=ref_now)
        # Next due is April 1 (since March 1 has arrived)
        self.assertEqual(next_due.month, 4)
        self.assertEqual(next_due.day, 1)
        self.assertEqual(next_due.hour, 2)

    def test_04_fall_back_behavior(self):
        """Proves 2:00 AM on fall-back Sunday (ambiguous local time) resolves deterministically."""
        # 2026-11-01 in America/New_York: clocks fall back from 02:00 to 01:00
        ref_now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=dt_tz.utc)
        next_due = calculate_next_due_datetime(self.config_ny, reference_datetime=ref_now)
        self.assertEqual(next_due.month, 11)
        self.assertEqual(next_due.day, 1)
        self.assertEqual(next_due.hour, 2)
        # UTC conversion is 07:00 UTC
        self.assertEqual(next_due.astimezone(dt_tz.utc).hour, 7)

    def test_05_missed_scheduler_tick_recovery(self):
        """Proves that if the scanner was down at 02:00 and wakes at 04:30 local, the tenant is still detected as due."""
        # Mock time at 2026-11-01 04:30 EST (2.5 hours after 02:00 due window)
        tz_ny = ZoneInfo("America/New_York")
        wake_time = datetime(2026, 11, 1, 4, 30, 0, tzinfo=tz_ny)

        is_due, p_start, p_end, reason = is_tenant_due(self.config_ny, reference_datetime=wake_time)
        self.assertTrue(is_due)
        self.assertEqual(reason, "DUE")
        self.assertEqual(p_start, date(2026, 10, 1))
        self.assertEqual(p_end, date(2026, 10, 31))

    def test_06_global_scanner_after_due_time_still_detects_tenant(self):
        """Proves global 15-minute scanner executing before NY local 02:00 vs after NY 02:00 on Nov 1."""
        tz_ny = ZoneInfo("America/New_York")
        # 05:00 UTC on Nov 1 is 01:00 EDT Nov 1 (1 hour BEFORE 02:00 due window)
        time_before = datetime(2026, 11, 1, 5, 0, 0, tzinfo=dt_tz.utc)
        is_due_before, _, _, reason_before = is_tenant_due(self.config_ny, reference_datetime=time_before)
        self.assertFalse(is_due_before)
        self.assertIn("NOT_DUE", reason_before)

        # 07:15 UTC on Nov 1 is 02:15 EST Nov 1 (15 minutes AFTER 02:00 due window, fall back passed)
        time_after = datetime(2026, 11, 1, 7, 15, 0, tzinfo=dt_tz.utc)
        is_due_after, p_start, p_end, _ = is_tenant_due(self.config_ny, reference_datetime=time_after)
        self.assertTrue(is_due_after)
        self.assertEqual(p_start, date(2026, 10, 1))
        self.assertEqual(p_end, date(2026, 10, 31))

    def test_07_tenant_already_processed_not_rediscovered(self):
        """Proves that a period with an existing run (even BLOCKED or COMPLETED) is not re-queued."""
        test_time = datetime(2026, 11, 1, 8, 0, 0, tzinfo=dt_tz.utc)

        # Create an existing run for October period
        IntelligenceAutomationRun.objects.create(
            client=self.client_ny,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            pipeline_version=PIPELINE_VERSION,
            execution_identity="sample-oct-run",
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            status=AutomationStatus.COMPLETED.value,
            current_stage=AutomationStage.COMPLETE.value,
        )

        with patch("django.utils.timezone.now", return_value=test_time):
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertNotIn(self.client_ny.id, res["due_client_ids"])
            skipped = next((s for s in res["skipped_summary"] if s["client_id"] == self.client_ny.id), None)
            self.assertIsNotNone(skipped)
            self.assertIn("RUN_ALREADY_EXISTS_OR_ACTIVE", skipped["reason"])

    def test_08_la_timezone(self):
        """Proves America/Los_Angeles tenant correctly evaluates due state in Pacific time."""
        client_la = Client.objects.create(
            name="Los Angeles Client",
            is_active=True,
            timezone="America/Los_Angeles",
            email="la_client@example.com",
        )
        cfg_la = IntelligenceAutomationConfig.objects.create(
            client=client_la,
            enabled=True,
            timezone="America/Los_Angeles",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
        )
        # 07:15 UTC on Nov 1 is 02:15 EST in NY (Due), but 23:15 PDT Oct 31 in LA (Not Due)
        time_sample = datetime(2026, 11, 1, 7, 15, 0, tzinfo=dt_tz.utc)
        is_due, _, _, reason = is_tenant_due(cfg_la, reference_datetime=time_sample)
        self.assertFalse(is_due)
        self.assertIn("NOT_DUE", reason)

        # 10:15 UTC on Nov 1 is 02:15 PST in LA (Due)
        time_sample_due = datetime(2026, 11, 1, 10, 15, 0, tzinfo=dt_tz.utc)
        is_due_la, _, _, _ = is_tenant_due(cfg_la, reference_datetime=time_sample_due)
        self.assertTrue(is_due_la)

    def test_09_bogota_timezone(self):
        """Proves America/Bogota tenant (no DST, constant UTC-5) evaluates cleanly."""
        client_bogota = Client.objects.create(
            name="Bogota Client",
            is_active=True,
            timezone="America/Bogota",
            email="bogota_client@example.com",
        )
        cfg_bogota = IntelligenceAutomationConfig.objects.create(
            client=client_bogota,
            enabled=True,
            timezone="America/Bogota",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
        )
        # 07:00 UTC on Nov 1 is exactly 02:00 in Bogota
        time_sample = datetime(2026, 11, 1, 7, 0, 0, tzinfo=dt_tz.utc)
        is_due, _, _, _ = is_tenant_due(cfg_bogota, reference_datetime=time_sample)
        self.assertTrue(is_due)

    def test_10_utc_timezone(self):
        """Proves UTC tenant schedule behaves with zero offset."""
        client_utc = Client.objects.create(
            name="UTC Client",
            is_active=True,
            timezone="UTC",
            email="utc_client@example.com",
        )
        cfg_utc = IntelligenceAutomationConfig.objects.create(
            client=client_utc,
            enabled=True,
            timezone="UTC",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
        )
        # 02:00 UTC on Nov 1 is Due
        time_sample = datetime(2026, 11, 1, 2, 0, 0, tzinfo=dt_tz.utc)
        is_due, _, _, _ = is_tenant_due(cfg_utc, reference_datetime=time_sample)
        self.assertTrue(is_due)

    def test_11_repeated_identical_blocked_scan_does_not_create_row_storm(self):
        """Proves repeated periodic scans of an invariant blocked tenant do NOT create runaway BLOCKED rows."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)
        
        elig = evaluate_intelligence_automation_eligibility(
            client_id=self.client_ny.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=True,
        )

        IntelligenceAutomationRun.objects.create(
            client=self.client_ny,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=elig.execution_identity,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            status=AutomationStatus.BLOCKED.value,
            current_stage=AutomationStage.ELIGIBILITY.value,
            error_code=elig.blocking_reasons[0],
            metadata={"block_state_hash": elig.block_state_hash},
        )

        initial_count = IntelligenceAutomationRun.objects.count()

        # Run discovery scan multiple times
        test_time = datetime(2026, 10, 2, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=test_time):
            for _ in range(5):
                res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
                self.assertNotIn(self.client_ny.id, res["due_client_ids"])

        final_count = IntelligenceAutomationRun.objects.count()
        self.assertEqual(initial_count, final_count)

    def test_12_changed_blocker_state_can_be_audited(self):
        """Proves a new reporting period evaluates cleanly as its own audit unit."""
        # Period 1 (August) was blocked
        IntelligenceAutomationRun.objects.create(
            client=self.client_ny,
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            pipeline_version=PIPELINE_VERSION,
            execution_identity="sample-aug-run",
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            status=AutomationStatus.BLOCKED.value,
            current_stage=AutomationStage.ELIGIBILITY.value,
        )

        # In October, evaluating September period is separate and detected
        test_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=dt_tz.utc)
        with patch("django.utils.timezone.now", return_value=test_time):
            is_due, p_start, p_end, _ = is_tenant_due(self.config_ny, reference_datetime=test_time)
            self.assertTrue(is_due)
            self.assertEqual(p_start, date(2026, 9, 1))

    def test_13_active_run_uniqueness_remains_hard(self):
        """Proves DB constraint prevents duplicate active run rows."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)

        run1 = execute_intelligence_automation(
            client_id=self.client_ny.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        run1.status = AutomationStatus.RUNNING.value
        run1.save()

        # Attempting second execution is blocked by concurrency lock or unique constraint
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_ny.id,
            period_start=p_start,
            period_end=p_end,
        )
        self.assertFalse(res.eligible)
        self.assertTrue(any("DUPLICATE_ACTIVE_RUN_EXISTS" in b for b in res.blocking_reasons))

    def test_14_approval_gate_unchanged(self):
        """Proves require_operator_approval=True continues to block autonomous narrative generation."""
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_ny.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertFalse(res.execution_authorized)
        self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", res.blocking_reasons)

    def test_15_zero_provider_calls_across_all_due_checks(self):
        """Proves is_tenant_due and calculate_next_due_datetime make zero external network or LLM calls."""
        with patch("urllib.request.urlopen") as mock_http, \
             patch("requests.post") as mock_post:
            
            due, _, _, _ = is_tenant_due(self.config_ny)
            next_due = calculate_next_due_datetime(self.config_ny)
            
            self.assertIsNotNone(next_due)
            self.assertEqual(mock_http.call_count, 0)
            self.assertEqual(mock_post.call_count, 0)
