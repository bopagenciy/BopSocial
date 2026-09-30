# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Tests for Phase BOP-CONV-B1A: Canonical Tenant & Contact Identity Foundation.

Covers:
- Client model auto-generation of UUIDv4 bop_organization_id
- Client bop_organization_id uniqueness and persistence
- Client model-level immutability enforcement
- ClientSerializer exposure and mutation rejection
- WhatsAppContact model auto-generation of UUIDv4 bop_contact_id
- WhatsAppContact bop_contact_id uniqueness and persistence
- WhatsAppContact model-level immutability enforcement
- WhatsAppContactSerializer exposure and mutation rejection
- Lead model read-only bop_contact_id property & serializer exposure
- Tenant isolation on bop_organization_id client lookup
- Tenant isolation on bop_contact_id contact lookup
- Preservation of integer primary keys (Client.id) and backward compatibility
"""
import uuid
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from ..models import Client, UserProfile, WhatsAppContact
from ..bot_models import Lead, BotFlow
from ..serializers import ClientSerializer
from ..whatsapp_serializers import WhatsAppContactSerializer, WhatsAppContactSummarySerializer
from ..bot_serializers import LeadListSerializer


class CanonicalTenantIdentityTests(TestCase):
    def setUp(self):
        # Tenant A
        self.user_a = User.objects.create_user(
            username='tenant_a_user', email='tenant_a@example.com', password='password123',
        )
        self.client_a = Client.objects.create(
            name='Alice Admin',
            company='Tenant A Corp',
            email='tenant_a@example.com',
            owner_user=self.user_a,
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            client=self.client_a,
            role='client',
            account_type='end_user',
        )

        # Tenant B
        self.user_b = User.objects.create_user(
            username='tenant_b_user', email='tenant_b@example.com', password='password123',
        )
        self.client_b = Client.objects.create(
            name='Bob Admin',
            company='Tenant B Corp',
            email='tenant_b@example.com',
            owner_user=self.user_b,
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            client=self.client_b,
            role='client',
            account_type='end_user',
        )

        # Superadmin
        self.superadmin = User.objects.create_superuser(
            username='admin_user', email='admin@example.com', password='password123',
        )
        self.profile_admin = UserProfile.objects.create(
            user=self.superadmin,
            role='superadmin',
        )

    def test_client_auto_generates_bop_organization_id(self):
        """Newly created Client must receive a valid, non-null UUIDv4 bop_organization_id."""
        self.assertIsNotNone(self.client_a.bop_organization_id)
        parsed = uuid.UUID(str(self.client_a.bop_organization_id))
        self.assertEqual(parsed.version, 4)

    def test_client_bop_organization_id_is_unique(self):
        """Different Clients must have different bop_organization_id values."""
        self.assertNotEqual(
            self.client_a.bop_organization_id,
            self.client_b.bop_organization_id,
        )

    def test_client_bop_organization_id_persists_on_update(self):
        """Updating existing Client attributes must not alter bop_organization_id."""
        orig_id = self.client_a.bop_organization_id
        self.client_a.company = 'Updated Tenant A Corp'
        self.client_a.save()
        self.client_a.refresh_from_db()
        self.assertEqual(self.client_a.bop_organization_id, orig_id)

    def test_client_model_level_immutability(self):
        """Attempting to change bop_organization_id on existing Client must raise ValueError."""
        new_uuid = uuid.uuid4()
        self.client_a.bop_organization_id = new_uuid
        with self.assertRaises(ValueError):
            self.client_a.save()

    def test_client_serializer_exposes_bop_organization_id(self):
        """ClientSerializer must output bop_organization_id as string."""
        data = ClientSerializer(self.client_a).data
        self.assertIn('bop_organization_id', data)
        self.assertEqual(data['bop_organization_id'], str(self.client_a.bop_organization_id))

    def test_client_serializer_rejects_bop_organization_id_mutation(self):
        """ClientSerializer must reject attempts to mutate bop_organization_id in PUT/PATCH."""
        new_uuid = str(uuid.uuid4())
        serializer = ClientSerializer(
            instance=self.client_a,
            data={'company': 'New Name', 'bop_organization_id': new_uuid},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('bop_organization_id', serializer.errors)

    def test_client_serializer_allows_identical_bop_organization_id(self):
        """Submitting the current bop_organization_id in PUT/PATCH is valid and safe."""
        serializer = ClientSerializer(
            instance=self.client_a,
            data={'company': 'Same Org ID', 'bop_organization_id': str(self.client_a.bop_organization_id)},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_tenant_isolation_on_bop_organization_id_lookup(self):
        """Tenant A cannot look up Tenant B using bop_organization_id via ClientViewSet."""
        client = APIClient()
        client.force_authenticate(user=self.user_a)

        # Tenant A querying with Tenant B's bop_organization_id returns empty
        resp = client.get(f'/api/clients/?bop_organization_id={self.client_b.bop_organization_id}')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 0)

        # Tenant A querying with Tenant A's bop_organization_id returns client_a
        resp_own = client.get(f'/api/clients/?bop_organization_id={self.client_a.bop_organization_id}')
        self.assertEqual(resp_own.status_code, 200)
        results_own = resp_own.data.get('results', resp_own.data) if isinstance(resp_own.data, dict) else resp_own.data
        self.assertEqual(len(results_own), 1)
        self.assertEqual(results_own[0]['id'], self.client_a.id)

    def test_existing_client_id_remains_integer_pk(self):
        """Client.id must remain integer primary key for backward compatibility."""
        self.assertIsInstance(self.client_a.id, int)
        self.assertIsInstance(self.client_b.id, int)


class CanonicalContactIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='contact_tenant_user', email='ct_user@example.com', password='password123',
        )
        self.client_1 = Client.objects.create(
            name='Workspace One', company='Workspace One Ltd', email='ws1@example.com',
        )
        self.profile = UserProfile.objects.create(
            user=self.user, client=self.client_1, role='client',
        )

        self.client_2 = Client.objects.create(
            name='Workspace Two', company='Workspace Two Ltd', email='ws2@example.com',
        )

        self.contact_1 = WhatsAppContact.objects.create(
            client=self.client_1, phone='+15551234567', name='Alice Prospect',
        )
        self.contact_2 = WhatsAppContact.objects.create(
            client=self.client_2, phone='+15559876543', name='Bob Other Tenant',
        )

    def test_contact_auto_generates_bop_contact_id(self):
        """Newly created WhatsAppContact must receive a valid, non-null UUIDv4 bop_contact_id."""
        self.assertIsNotNone(self.contact_1.bop_contact_id)
        parsed = uuid.UUID(str(self.contact_1.bop_contact_id))
        self.assertEqual(parsed.version, 4)

    def test_contact_bop_contact_id_is_unique(self):
        """Different WhatsAppContacts must have different bop_contact_id values."""
        self.assertNotEqual(
            self.contact_1.bop_contact_id,
            self.contact_2.bop_contact_id,
        )

    def test_contact_bop_contact_id_persists_on_update(self):
        """Updating contact fields must not change bop_contact_id."""
        orig_id = self.contact_1.bop_contact_id
        self.contact_1.name = 'Alice Prospect Updated'
        self.contact_1.save()
        self.contact_1.refresh_from_db()
        self.assertEqual(self.contact_1.bop_contact_id, orig_id)

    def test_contact_model_level_immutability(self):
        """Attempting to change bop_contact_id on existing contact must raise ValueError."""
        new_uuid = uuid.uuid4()
        self.contact_1.bop_contact_id = new_uuid
        with self.assertRaises(ValueError):
            self.contact_1.save()

    def test_contact_serializer_exposes_bop_contact_id(self):
        """WhatsAppContactSerializer and WhatsAppContactSummarySerializer must output bop_contact_id."""
        data = WhatsAppContactSerializer(self.contact_1).data
        self.assertIn('bop_contact_id', data)
        self.assertEqual(data['bop_contact_id'], str(self.contact_1.bop_contact_id))

        summary_data = WhatsAppContactSummarySerializer(self.contact_1).data
        self.assertIn('bop_contact_id', summary_data)
        self.assertEqual(summary_data['bop_contact_id'], str(self.contact_1.bop_contact_id))

    def test_contact_serializer_rejects_mutation(self):
        """WhatsAppContactSerializer must reject attempts to mutate bop_contact_id."""
        new_uuid = str(uuid.uuid4())
        serializer = WhatsAppContactSerializer(
            instance=self.contact_1,
            data={'name': 'New Name', 'bop_contact_id': new_uuid},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('bop_contact_id', serializer.errors)

    def test_lead_exposes_bop_contact_id_from_contact(self):
        """Lead model and serializer must expose the contact's canonical bop_contact_id."""
        lead = Lead.objects.create(
            client=self.client_1,
            contact=self.contact_1,
            name='Alice Lead',
            phone=self.contact_1.phone,
        )
        self.assertEqual(lead.bop_contact_id, self.contact_1.bop_contact_id)

        data = LeadListSerializer(lead).data
        self.assertIn('bop_contact_id', data)
        self.assertEqual(data['bop_contact_id'], str(self.contact_1.bop_contact_id))

    def test_tenant_isolation_on_bop_contact_id_lookup(self):
        """Tenant 1 cannot look up Tenant 2's contact by bop_contact_id."""
        api = APIClient()
        api.force_authenticate(user=self.user)

        # Querying contact from client_2 returns nothing for user of client_1
        resp = api.get(f'/api/whatsapp/contacts/?bop_contact_id={self.contact_2.bop_contact_id}')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 0)

        # Querying contact from client_1 returns the contact
        resp_own = api.get(f'/api/whatsapp/contacts/?bop_contact_id={self.contact_1.bop_contact_id}')
        self.assertEqual(resp_own.status_code, 200)
        results_own = resp_own.data.get('results', resp_own.data) if isinstance(resp_own.data, dict) else resp_own.data
        self.assertEqual(len(results_own), 1)
        self.assertEqual(results_own[0]['id'], self.contact_1.id)
