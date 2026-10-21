# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Tests for Phase BS-2.7B: Canonical Workspace Currency & Formatter Foundation.

Covers:
- Client model currency defaults (USD) and ISO choices
- Serializer validation and uppercase normalization
- Invalid currency code rejection
- Tenant authorization & isolation (workspace A vs B)
- Language/currency independence (no cross-mutation)
- ROISettings alignment with Client.currency
- Dashboard today API currency payload
"""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Client, UserProfile, ROISettings
from ..serializers import ClientSerializer


class WorkspaceCurrencyFoundationTests(TestCase):
    def setUp(self):
        # Workspace A
        self.user_a = User.objects.create_user(
            username='user_a', email='user_a@example.com', password='password123',
            first_name='Alice', last_name='Owner'
        )
        self.client_a = Client.objects.create(
            name='Alice Admin',
            company='Workspace A Corp',
            email='workspace_a@example.com',
            default_language='en',
            currency='USD',
            timezone='America/New_York',
            owner_user=self.user_a,
            ownership_type='end_user_owned',
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            client=self.client_a,
            role='client',
            account_type='end_user',
            language='en',
        )

        # Workspace B
        self.user_b = User.objects.create_user(
            username='user_b', email='user_b@example.com', password='password123',
            first_name='Bob', last_name='Client'
        )
        self.client_b = Client.objects.create(
            name='Bob Admin',
            company='Workspace B Corp',
            email='workspace_b@example.com',
            default_language='es',
            currency='COP',
            timezone='America/Bogota',
            owner_user=self.user_b,
            ownership_type='end_user_owned',
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            client=self.client_b,
            role='client',
            account_type='end_user',
            language='es',
        )

        # Superadmin
        self.superadmin = User.objects.create_superuser(
            username='superadmin', email='super@example.com', password='password123'
        )
        self.profile_admin = UserProfile.objects.create(
            user=self.superadmin,
            role='superadmin',
            account_type='agency',
            language='en',
        )

        self.api = APIClient()

    # ── 1. Model Defaults & Choices ───────────────────────────────────────────
    def test_client_model_default_currency_is_usd(self):
        """New Client instances default to canonical USD currency."""
        new_client = Client.objects.create(name='Test', company='Test Corp', email='test_default@example.com')
        self.assertEqual(new_client.currency, 'USD')

    def test_client_model_accepts_supported_iso_codes(self):
        """Client model accepts valid ISO 4217 currencies."""
        supported = ['USD', 'COP', 'EUR', 'GBP', 'MXN', 'CAD', 'INR', 'BRL', 'ARS', 'CLP', 'PEN']
        for code in supported:
            c = Client.objects.create(name=f'Test {code}', company=f'Company {code}', email=f'test_{code.lower()}@example.com', currency=code)
            self.assertEqual(c.currency, code)

    # ── 2. Serializer Validation & Normalization ──────────────────────────────
    def test_serializer_normalizes_lowercase_to_uppercase(self):
        """Serializer converts lowercase 'cop' to uppercase 'COP'."""
        serializer = ClientSerializer(self.client_a, data={'currency': 'cop'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['currency'], 'COP')

    def test_serializer_rejects_unsupported_currency_code(self):
        """Serializer rejects unknown/unsupported currency codes with ValidationError."""
        serializer = ClientSerializer(self.client_a, data={'currency': 'XYZ'}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('currency', serializer.errors)

    def test_serializer_exposes_currency_field(self):
        """ClientSerializer output includes canonical currency code."""
        data = ClientSerializer(self.client_b).data
        self.assertEqual(data.get('currency'), 'COP')

    # ── 3. Tenant Isolation & Permissions ─────────────────────────────────────
    def test_workspace_user_can_update_own_currency(self):
        """Owner of workspace A can update currency on their own client."""
        self.api.force_authenticate(user=self.user_a)
        res = self.api.patch(f'/api/clients/{self.client_a.id}/', {'currency': 'EUR'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.client_a.refresh_from_db()
        self.assertEqual(self.client_a.currency, 'EUR')

    def test_workspace_user_cannot_update_other_workspace_currency(self):
        """User A from Workspace A cannot modify Workspace B's currency."""
        self.api.force_authenticate(user=self.user_a)
        res = self.api.patch(f'/api/clients/{self.client_b.id}/', {'currency': 'EUR'}, format='json')
        self.assertIn(res.status_code, [403, 404])
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.currency, 'COP')

    # ── 4. Language & Currency Independence ───────────────────────────────────
    def test_language_mutation_does_not_alter_currency(self):
        """Changing workspace or user language does not alter the workspace currency."""
        self.client_b.default_language = 'en'
        self.client_b.save(update_fields=['default_language'])
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.currency, 'COP')
        self.assertEqual(self.client_b.default_language, 'en')

        self.profile_b.language = 'en'
        self.profile_b.save(update_fields=['language'])
        self.profile_b.refresh_from_db()
        self.assertEqual(self.client_b.currency, 'COP')

    def test_currency_mutation_does_not_alter_language_or_timezone(self):
        """Updating currency leaves default_language, user language, and timezone intact."""
        self.api.force_authenticate(user=self.user_b)
        res = self.api.patch(f'/api/clients/{self.client_b.id}/', {'currency': 'USD'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.client_b.refresh_from_db()
        self.assertEqual(self.client_b.currency, 'USD')
        self.assertEqual(self.client_b.default_language, 'es')
        self.assertEqual(self.client_b.timezone, 'America/Bogota')
        self.assertEqual(self.profile_b.language, 'es')

    # ── 5. ROISettings Alignment ──────────────────────────────────────────────
    def test_roisettings_unconfigured_defaults_to_client_currency(self):
        """GET /api/roi/settings/<id>/ returns client.currency when unconfigured."""
        self.api.force_authenticate(user=self.superadmin)
        res = self.api.get(f'/api/roi/settings/{self.client_b.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get('currency'), 'COP')

    def test_roisettings_creation_initializes_with_client_currency(self):
        """PUT /api/roi/settings/<id>/ initializes new ROISettings with client.currency."""
        self.api.force_authenticate(user=self.superadmin)
        res = self.api.put(
            f'/api/roi/settings/{self.client_b.id}/',
            {'facebook_budget': '1500.00'},
            format='json'
        )
        self.assertEqual(res.status_code, 200)
        settings = ROISettings.objects.get(client=self.client_b)
        self.assertEqual(settings.currency, 'COP')

    # ── 6. Today Dashboard Payload ────────────────────────────────────────────
    def test_today_dashboard_includes_currency(self):
        """GET /api/dashboard/today/ returns client_currency and leads.currency."""
        self.api.force_authenticate(user=self.user_b)
        res = self.api.get('/api/dashboard/today/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get('client_currency'), 'COP')
        self.assertEqual(res.data.get('leads', {}).get('currency'), 'COP')
