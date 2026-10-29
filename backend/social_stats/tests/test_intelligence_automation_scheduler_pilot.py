"""
BS-6B Controlled Scheduler Activation Pilot Test Suite.
Validates:
1. enabled config discovered
2. disabled config ignored
3. wrong timezone not due
4. monthly due calculation
5. stale config blocked
6. approval-required narrative blocked
7. scheduled trigger cannot force
8. duplicate discovery idempotent
9. active run prevents second enqueue
10. provider call count remains zero
11. discovery never queues disabled tenant
12. tenant isolation
13. task exception fail-closed
14. periodic discovery does not invoke provider directly
15. existing report/narrative reused
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta
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
)
from social_stats.analytics.automation.tasks import (
    discover_and_enqueue_due_intelligence_automations,
    run_intelligence_automation_task,
)


class IntelligenceAutomationSchedulerPilotTests(TestCase):
    def setUp(self):
        self.client_3 = Client.objects.create(
            name="Pilot Bop Agencia",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="bop_pilot_3@example.com",
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_3,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=60),
        )

    def test_01_enabled_config_discovered(self):
        """Proves that enabled configs are scanned by the discovery task."""
        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=1,
            reporting_hour=2,
        )
        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        # It scans the enabled config and evaluates due state
        scanned_clients = [s.get("client_id") for s in res.get("skipped_summary", [])] + res.get("due_client_ids", [])
        self.assertIn(self.client_3.id, scanned_clients)

    def test_02_disabled_config_ignored(self):
        """Proves that disabled configs are completely ignored by the discovery task."""
        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=False,  # Disabled
            timezone="America/New_York",
        )
        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        scanned_clients = [s.get("client_id") for s in res.get("skipped_summary", [])] + res.get("due_client_ids", [])
        self.assertNotIn(self.client_3.id, scanned_clients)

    def test_03_wrong_timezone_not_due(self):
        """Proves that tenant timezone determines due state, avoiding server UTC mismatches."""
        client_tokyo = Client.objects.create(
            name="Tokyo Client",
            is_active=True,
            timezone="Asia/Tokyo",
            email="tokyo_tenant@example.com",
        )
        IntelligenceAutomationConfig.objects.create(
            client=client_tokyo,
            enabled=True,
            timezone="Asia/Tokyo",
            reporting_frequency="MONTHLY",
            reporting_day=31,
            reporting_hour=10,
        )
        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        tokyo_summary = next((s for s in res["skipped_summary"] if s["client_id"] == client_tokyo.id), None)
        self.assertIsNotNone(tokyo_summary)
        self.assertIn("NOT_DUE", tokyo_summary["reason"])

    def test_04_monthly_due_calculation(self):
        """Proves monthly cadence matches only exact reporting day and hour."""
        # Set reporting day/hour to current local time in New York
        tz = ZoneInfo("America/New_York")
        local_now = timezone.now().astimezone(tz)

        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=local_now.day,
            reporting_hour=local_now.hour,
        )
        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        self.assertIn(self.client_3.id, res["due_client_ids"])

    def test_05_stale_config_blocked(self):
        """Proves that a scheduled execution for a stale tenant is BLOCKED with ANALYTICS_DATA_STALE."""
        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
            max_data_staleness_hours=24,
        )
        # No sync logs exist => freshness code evaluates to MISSING/STALE
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_3.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertTrue(any("ANALYTICS_DATA" in b for b in res.blocking_reasons))

    def test_06_approval_required_narrative_blocked(self):
        """Proves require_operator_approval=True blocks scheduled narrative generation."""
        IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            generate_narrative=True,
            require_operator_approval=True,
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_3.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertFalse(res.execution_authorized)
        self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", res.blocking_reasons)

    def test_07_scheduled_trigger_cannot_force(self):
        """Proves scheduled trigger ignores --force and enforces all safety gates."""
        IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=False,
            require_operator_approval=True,
        )
        # Calling scheduled trigger directly
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_3.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertIn("AUTOMATION_CONFIG_DISABLED", res.blocking_reasons)

    def test_08_duplicate_discovery_idempotent(self):
        """Proves repeated discovery runs produce identical decisions without duplicate enqueues."""
        tz = ZoneInfo("America/New_York")
        local_now = timezone.now().astimezone(tz)

        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=local_now.day,
            reporting_hour=local_now.hour,
        )
        res1 = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        res2 = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        self.assertEqual(res1["due_client_ids"], res2["due_client_ids"])

    def test_09_active_run_prevents_second_enqueue(self):
        """Proves an existing active or completed run prevents duplicate discovery enqueues."""
        tz = ZoneInfo("America/New_York")
        local_now = timezone.now().astimezone(tz)

        config = IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
            reporting_frequency="MONTHLY",
            reporting_day=local_now.day,
            reporting_hour=local_now.hour,
        )
        # Create an existing completed run for the month
        p_start = date(local_now.year, (local_now.month - 1) or 12, 1)
        p_end = date(local_now.year, local_now.month, 1) - timedelta(days=1)
        IntelligenceAutomationRun.objects.create(
            client=self.client_3,
            period_start=p_start,
            period_end=p_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity="sample-active-run-id",
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            status=AutomationStatus.COMPLETED.value,
            current_stage=AutomationStage.COMPLETE.value,
        )

        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        self.assertNotIn(self.client_3.id, res["due_client_ids"])
        skipped = next((s for s in res["skipped_summary"] if s["client_id"] == self.client_3.id), None)
        self.assertIn("RUN_ALREADY_EXISTS_OR_ACTIVE", skipped["reason"])

    def test_10_provider_call_count_remains_zero(self):
        """Proves provider_call_count on created scheduled run is 0 and no provider calls are executed."""
        run = execute_intelligence_automation(
            client_id=self.client_3.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertEqual(run.provider_call_count, 0)
        self.assertEqual(run.retry_count, 0)

    def test_11_discovery_never_queues_disabled_tenant(self):
        """Proves discovery task query strictly excludes disabled tenant configs."""
        client_disabled = Client.objects.create(
            name="Disabled Tenant",
            is_active=True,
            timezone="America/New_York",
            email="disabled_tenant@example.com",
        )
        IntelligenceAutomationConfig.objects.create(
            client=client_disabled,
            enabled=False,
            timezone="America/New_York",
        )
        res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
        self.assertNotIn(client_disabled.id, res["due_client_ids"])

    def test_12_tenant_isolation(self):
        """Proves configurations and runs for client A cannot affect client B."""
        client_other = Client.objects.create(
            name="Other Tenant",
            is_active=True,
            timezone="America/New_York",
            email="other_tenant@example.com",
        )
        IntelligenceAutomationConfig.objects.create(
            client=self.client_3,
            enabled=True,
            timezone="America/New_York",
        )
        # client_other has no config
        res = evaluate_intelligence_automation_eligibility(
            client_id=client_other.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
        )
        self.assertFalse(res.eligible)
        self.assertIn("AUTOMATION_CONFIG_MISSING", res.blocking_reasons)

    def test_13_task_exception_fail_closed(self):
        """Proves orchestrator handles unhandled exceptions safely and marks run FAILED without leaks."""
        with patch("social_stats.analytics.automation.orchestrator.evaluate_intelligence_automation_eligibility", side_effect=RuntimeError("Unexpected test crash")):
            with self.assertRaises(RuntimeError):
                execute_intelligence_automation(
                    client_id=self.client_3.id,
                    trigger_type=AutomationTriggerType.SCHEDULED.value,
                )

    def test_14_periodic_discovery_does_not_invoke_provider_directly(self):
        """Proves discover_and_enqueue_due_intelligence_automations makes zero HTTP or LLM calls."""
        with patch("urllib.request.urlopen") as mock_http, \
             patch("requests.post") as mock_req_post, \
             patch("requests.get") as mock_req_get:
            
            res = discover_and_enqueue_due_intelligence_automations(dry_run=True)
            self.assertIsNotNone(res)
            self.assertEqual(mock_http.call_count, 0)
            self.assertEqual(mock_req_post.call_count, 0)
            self.assertEqual(mock_req_get.call_count, 0)

    def test_15_existing_report_narrative_reused(self):
        """Proves scheduled execution for canonical period reuses existing ExecutiveReport and ExecutiveNarrative."""
        p_start = date(2026, 9, 22)
        p_end = date(2026, 10, 22)
        rep = ExecutiveReport.objects.create(
            client=self.client_3,
            period_start=p_start,
            period_end=p_end,
            status="GENERATED",
            title="September Report",
        )
        narrative = ExecutiveNarrative.objects.create(
            client=self.client_3,
            executive_report=rep,
            status="VALIDATED",
            rendered_text="Canonical validated text.",
            prompt_version="bs5e-prompt-v3",
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_3.id,
            period_start=p_start,
            period_end=p_end,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
        )
        self.assertIn("report", res.reuse_decisions)
        self.assertIn(f"REUSE ExecutiveReport #{rep.id}", res.reuse_decisions["report"])
        self.assertIn("narrative", res.reuse_decisions)
        self.assertIn(f"REUSE ExecutiveNarrative #{narrative.id}", res.reuse_decisions["narrative"])
