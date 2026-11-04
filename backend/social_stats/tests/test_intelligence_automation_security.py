"""
Unit Tests for BS-6A Multi-Tenant Security and Isolation (Test Matrix AV).
Verifies strict tenant isolation across configurations, runs, previews, and queries.
"""
from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase

from social_stats.models import (
    Client,
    IntelligenceAutomationConfig,
    IntelligenceAutomationRun,
    UserProfile,
)
from social_stats.analytics.automation.constants import (
    AutomationStatus,
    PIPELINE_VERSION,
)
from social_stats.analytics.automation.identity import compute_execution_identity
from social_stats.analytics.automation.orchestrator import preview_intelligence_automation


class IntelligenceAutomationSecurityTests(TestCase):
    def setUp(self):
        # Client 1
        self.client_1 = Client.objects.create(name="Tenant Alpha", company="Alpha Corp", email="alpha@tenant.com", is_active=True)
        self.user_1 = User.objects.create_user(username="user_alpha", email="alpha_user@tenant.com")
        self.profile_1 = UserProfile.objects.create(user=self.user_1, client=self.client_1, role="client")

        # Client 2
        self.client_2 = Client.objects.create(name="Tenant Beta", company="Beta Corp", email="beta@tenant.com", is_active=True)
        self.user_2 = User.objects.create_user(username="user_beta", email="beta_user@tenant.com")
        self.profile_2 = UserProfile.objects.create(user=self.user_2, client=self.client_2, role="client")

        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 30)

        # Run records for Client 1
        self.run_1 = IntelligenceAutomationRun.objects.create(
            client=self.client_1,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=compute_execution_identity(self.client_1.id, self.period_start, self.period_end),
            status=AutomationStatus.COMPLETED.value,
        )

        # Run records for Client 2
        self.run_2 = IntelligenceAutomationRun.objects.create(
            client=self.client_2,
            period_start=self.period_start,
            period_end=self.period_end,
            pipeline_version=PIPELINE_VERSION,
            execution_identity=compute_execution_identity(self.client_2.id, self.period_start, self.period_end),
            status=AutomationStatus.COMPLETED.value,
        )

    def test_tenant_runs_isolated_by_client_id(self):
        """Querying runs by client_id strictly filters out other tenants."""
        runs_c1 = list(IntelligenceAutomationRun.objects.filter(client=self.client_1).values_list("id", flat=True))
        runs_c2 = list(IntelligenceAutomationRun.objects.filter(client=self.client_2).values_list("id", flat=True))

        self.assertIn(self.run_1.id, runs_c1)
        self.assertNotIn(self.run_2.id, runs_c1)

        self.assertIn(self.run_2.id, runs_c2)
        self.assertNotIn(self.run_1.id, runs_c2)

    def test_tenant_preview_scoped_to_specific_client(self):
        """Preview for tenant 1 never includes or inspects tenant 2 artifacts."""
        preview_1 = preview_intelligence_automation(
            client_id=self.client_1.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(preview_1["client_id"], self.client_1.id)

        preview_2 = preview_intelligence_automation(
            client_id=self.client_2.id,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertEqual(preview_2["client_id"], self.client_2.id)
        self.assertNotEqual(preview_1["execution_identity"], preview_2["execution_identity"])

    def test_cross_tenant_enumeration_prevention(self):
        """Querying invalid client returns controlled failure without leaking tenant data."""
        preview_invalid = preview_intelligence_automation(
            client_id=999999,
            period_start=self.period_start,
            period_end=self.period_end,
        )
        self.assertFalse(preview_invalid["eligible"])
        self.assertIn("CLIENT_NOT_FOUND", preview_invalid["blocking_reasons"])
        self.assertEqual(preview_invalid["execution_identity"], "")
