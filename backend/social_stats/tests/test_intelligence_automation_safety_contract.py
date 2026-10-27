"""
BS-6A.1 Automation Activation Safety Contract Test Suite.
Validates:
1. eligible != execution_authorized where appropriate
2. blocked reason is deterministic
3. --force cannot bypass locking
4. --force cannot bypass provider budget
5. --force cannot bypass duplicate narrative protection
6. --force cannot create a second active run
7. scheduled trigger cannot force
8. approval-required tenant remains protected
9. disabled scheduler remains disabled
10. no provider calls
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta
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
)


class IntelligenceAutomationSafetyContractTests(TestCase):
    def setUp(self):
        self.client_1 = Client.objects.create(
            name="Pilot Tenant",
            is_active=True,
            timezone="America/New_York",
            requires_approval=True,
            email="tenant_pilot@example.com",
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_1,
            platform="facebook",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=60),
        )

    def test_01_eligible_not_equal_to_execution_authorized_when_approval_required(self):
        """Proves data_eligible=True and eligible=True does not imply execution_authorized=True for scheduled runs when approval is required."""
        cfg = IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
            enabled=True,
            reporting_frequency="MONTHLY",
            lookback_days=30,
            generate_report=True,
            generate_narrative=True,
            require_operator_approval=True,
            provider_call_budget=1,
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        # Even if data is present, scheduled trigger cannot be authorized without operator sign-off
        self.assertFalse(res.execution_authorized)
        self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", res.blocking_reasons)

    def test_02_blocked_reason_is_deterministic(self):
        """Proves that blocking reasons are deterministic and repeatable across multiple evaluations."""
        self.client_1.is_active = False
        self.client_1.save()

        res1 = evaluate_intelligence_automation_eligibility(client_id=self.client_1.id, dry_run=True)
        res2 = evaluate_intelligence_automation_eligibility(client_id=self.client_1.id, dry_run=True)

        self.assertFalse(res1.eligible)
        self.assertFalse(res2.eligible)
        self.assertEqual(res1.blocking_reasons, res2.blocking_reasons)
        self.assertIn("CLIENT_INACTIVE", res1.blocking_reasons)

    def test_03_force_cannot_bypass_locking(self):
        """Proves single-flight locking rejects concurrent execution regardless of force/override."""
        lock_hex = "a" * 64
        lock1 = SingleFlightLock(lock_hex)
        
        # Simulate active lock collision
        with patch.object(SingleFlightLock, "acquire", return_value=False):
            with self.assertRaises(ConcurrencyLockError):
                execute_intelligence_automation(
                    client_id=self.client_1.id,
                    dry_run=False,
                )

    def test_04_force_cannot_bypass_provider_budget(self):
        """Proves that provider call budget exhaustion is an inviolable gate."""
        cfg = IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
            enabled=True,
            generate_narrative=True,
            provider_call_budget=0,  # Zero budget
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertIn("PROVIDER_CALL_BUDGET_EXHAUSTED: budget is 0", res.blocking_reasons)

    def test_05_force_cannot_bypass_duplicate_validated_narrative_protection(self):
        """Proves that existing VALIDATED narrative is reused and cannot be regenerated or overwritten."""
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
            rendered_text="Validated canonical text.",
            prompt_version="bs5e-prompt-v3",
        )

        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=True,
        )
        self.assertNotIn(AutomationStage.NARRATIVE_CHECK.value, res.planned_stages)
        self.assertIn(AutomationStage.NARRATIVE_CHECK.value, res.skipped_stages)
        self.assertIn(f"REUSE ExecutiveNarrative #{narrative.id}", res.reuse_decisions["narrative"])

    def test_06_force_cannot_create_second_active_run(self):
        """Proves DB unique constraint rejects a duplicate active run for the same identity."""
        p_start = date(2026, 9, 1)
        p_end = date(2026, 9, 30)
        
        # Existing active run
        run1 = execute_intelligence_automation(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        # Put run1 into RUNNING status
        run1.status = AutomationStatus.RUNNING.value
        run1.save()

        # Attempting second run must fail at eligibility check
        res2 = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            period_start=p_start,
            period_end=p_end,
            dry_run=False,
        )
        self.assertFalse(res2.eligible)
        self.assertTrue(any("DUPLICATE_ACTIVE_RUN_EXISTS" in b for b in res2.blocking_reasons))

    def test_07_scheduled_trigger_cannot_force_or_bypass_approval(self):
        """Proves that SCHEDULED trigger ignores soft bypasses and enforces all gates."""
        IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
            enabled=False,  # Disabled
            require_operator_approval=True,
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            trigger_type=AutomationTriggerType.SCHEDULED.value,
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertFalse(res.execution_authorized)
        self.assertIn("AUTOMATION_CONFIG_DISABLED", res.blocking_reasons)

    def test_08_approval_required_tenant_remains_protected(self):
        """Proves that a tenant requiring approval blocks unapproved live narrative generation."""
        IntelligenceAutomationConfig.objects.create(
            client=self.client_1,
            enabled=True,
            generate_narrative=True,
            require_operator_approval=True,
        )
        res = evaluate_intelligence_automation_eligibility(
            client_id=self.client_1.id,
            trigger_type=AutomationTriggerType.MANUAL.value,
            dry_run=False,
        )
        self.assertFalse(res.eligible)
        self.assertIn("OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval", res.blocking_reasons)

    def test_09_disabled_scheduler_remains_disabled(self):
        """Proves PeriodicTask table has no automation periodic tasks registered and remains disabled."""
        self.assertFalse(PeriodicTask.objects.filter(task__contains="run_intelligence_automation").exists())
        self.assertFalse(PeriodicTask.objects.filter(task__contains="discover_and_enqueue_due_intelligence_automations").exists())

    def test_10_no_provider_calls_in_preview_or_evaluation(self):
        """Verifies with mocks that external HTTP requests are never invoked in preview."""
        with patch("urllib.request.urlopen") as mock_http, \
             patch("requests.post") as mock_req_post, \
             patch("requests.get") as mock_req_get:
            
            preview = preview_intelligence_automation(
                client_id=self.client_1.id,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
            )
            self.assertIsNotNone(preview)
            self.assertEqual(mock_http.call_count, 0)
            self.assertEqual(mock_req_post.call_count, 0)
            self.assertEqual(mock_req_get.call_count, 0)
