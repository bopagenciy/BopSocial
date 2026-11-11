"""
BOP SOCIAL — PHASE BS-8F
AGENCY OWNER MULTI-CLIENT ACCESS ENABLEMENT TESTS

Proves:
1. Agency owner can access Client #3 (Bop Agencia self workspace)
2. Agency owner can access a second synthetic active client relation
3. Agency owner cannot access foreign agency client
4. Paused relation denied
5. Terminated relation denied
6. Direct end-user remains single-client scoped
7. Staff behavior unchanged
8. Superadmin global access unchanged
9. ClientViewSet list returns only own agency clients
10. Direct foreign client detail returns 403/404
11. Client switcher receives only own agency clients (query param spoofing rejected)
"""
import uuid
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation


class AgencyOwnerMultiClientAccessTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # ── Canonical Agency #2 (Bop Agencia) & Owner (bopagencia@gmail.com) ──
        self.owner_user = User.objects.create_user(
            username='bopagencia@gmail.com',
            email='bopagencia@gmail.com',
            password='TestPassword123!',
            is_staff=False,
            is_superuser=False,
        )
        self.agency_2 = Agency.objects.create(
            name='Bop Agencia',
            slug='bop-agencia',
            owner_user=self.owner_user,
        )

        # Self workspace: Client #3 (Bop Agencia)
        self.client_3 = Client.objects.create(
            name='Bop Agencia',
            company='Bop Agencia',
            email='bopagencia-ws@test.local',
        )

        self.agency_profile = UserProfile.objects.create(
            user=self.owner_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
            client=self.client_3,
            default_workspace=self.client_3,
            email_verified=True,
            terms_accepted=True,
        )
        self.membership_2 = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.owner_user,
            role='owner',
            is_active=True,
        )

        # Active relation for Client #3
        self.rel_client_3 = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_3,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # Second synthetic active client
        self.client_2_second = Client.objects.create(
            name='Cliente Beta Corp',
            company='Beta Corp',
            email='beta@test.local',
        )
        self.rel_2_second = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_2_second,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # Paused client relation
        self.client_2_paused = Client.objects.create(
            name='Cliente Paused',
            company='Paused Client Inc',
            email='paused@test.local',
        )
        self.rel_2_paused = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_2_paused,
            status='paused',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # Terminated client relation
        self.client_2_terminated = Client.objects.create(
            name='Cliente Terminated',
            company='Terminated Client LLC',
            email='terminated@test.local',
        )
        self.rel_2_terminated = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_2_terminated,
            status='terminated',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # ── Foreign Agency (Agency Beta) & Foreign Client ──
        self.foreign_owner = User.objects.create_user(
            username='foreign_owner@test.local',
            email='foreign_owner@test.local',
            password='TestPassword123!',
        )
        self.agency_foreign = Agency.objects.create(
            name='Foreign Agency Ltd',
            slug='foreign-agency',
            owner_user=self.foreign_owner,
        )
        self.foreign_profile = UserProfile.objects.create(
            user=self.foreign_owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_foreign,
        )
        self.foreign_membership = AgencyMembership.objects.create(
            agency=self.agency_foreign,
            user=self.foreign_owner,
            role='owner',
            is_active=True,
        )
        self.client_foreign = Client.objects.create(
            name='Foreign Client Workspace',
            company='Foreign Corp',
            email='foreign@test.local',
        )
        self.rel_foreign = AgencyClientRelation.objects.create(
            agency=self.agency_foreign,
            client=self.client_foreign,
            status='active',
            initiated_by='agency',
        )

        # ── Direct End User (single-client scoped) ──
        self.client_eu = Client.objects.create(
            name='Solo User Workspace',
            company='Solo Business',
            email='solo@test.local',
        )
        self.end_user = User.objects.create_user(
            username='solo@test.local',
            email='solo@test.local',
            password='TestPassword123!',
        )
        self.end_user_profile = UserProfile.objects.create(
            user=self.end_user,
            role='client',
            account_type='end_user',
            client=self.client_eu,
            default_workspace=self.client_eu,
        )

        # ── Staff User ──
        self.staff_client = Client.objects.create(
            name='Staff Assigned Client',
            company='Staff Client SA',
            email='staff_client@test.local',
        )
        self.staff_user = User.objects.create_user(
            username='staff@test.local',
            email='staff@test.local',
            password='TestPassword123!',
            is_staff=True,
        )
        self.staff_profile = UserProfile.objects.create(
            user=self.staff_user,
            role='staff',
        )
        self.staff_profile.assigned_clients.add(self.staff_client)

        # ── Super Admin ──
        self.super_user = User.objects.create_user(
            username='superadmin@test.local',
            email='superadmin@test.local',
            password='TestPassword123!',
            is_staff=True,
            is_superuser=True,
        )
        self.super_profile = UserProfile.objects.create(
            user=self.super_user,
            role='superadmin',
        )

    def test_01_agency_owner_can_access_client_3(self):
        """Agency owner can access their self workspace Client #3."""
        self.assertTrue(self.agency_profile.can_access_client(self.client_3.id))

    def test_02_agency_owner_can_access_second_synthetic_active_client(self):
        """Agency owner can access a second active client related to their agency."""
        self.assertTrue(self.agency_profile.can_access_client(self.client_2_second.id))

    def test_03_agency_owner_cannot_access_foreign_agency_client(self):
        """Agency owner cannot access a client belonging to a foreign agency."""
        self.assertFalse(self.agency_profile.can_access_client(self.client_foreign.id))

    def test_04_paused_relation_denied(self):
        """Paused relation is strictly denied access."""
        self.assertFalse(self.agency_profile.can_access_client(self.client_2_paused.id))

    def test_05_terminated_relation_denied(self):
        """Terminated relation is strictly denied access."""
        self.assertFalse(self.agency_profile.can_access_client(self.client_2_terminated.id))

    def test_06_direct_end_user_remains_single_client_scoped(self):
        """Direct end-user only accesses their own profile.client and none other."""
        self.assertTrue(self.end_user_profile.can_access_client(self.client_eu.id))
        self.assertFalse(self.end_user_profile.can_access_client(self.client_3.id))
        self.assertFalse(self.end_user_profile.can_access_client(self.client_2_second.id))
        self.assertFalse(self.end_user_profile.can_access_client(self.client_foreign.id))

    def test_07_staff_behavior_unchanged(self):
        """Staff user can access assigned clients, denied unassigned ones."""
        self.assertTrue(self.staff_profile.can_access_client(self.staff_client.id))
        self.assertFalse(self.staff_profile.can_access_client(self.client_foreign.id))
        self.assertFalse(self.staff_profile.can_access_client(self.client_3.id))

    def test_08_superadmin_global_access_unchanged(self):
        """Superadmin has unrestricted access to all clients."""
        self.assertTrue(self.super_profile.can_access_client(self.client_3.id))
        self.assertTrue(self.super_profile.can_access_client(self.client_2_second.id))
        self.assertTrue(self.super_profile.can_access_client(self.client_foreign.id))
        self.assertTrue(self.super_profile.can_access_client(self.client_2_paused.id))
        self.assertTrue(self.super_profile.can_access_client(self.client_2_terminated.id))

    def test_09_clientviewset_list_returns_only_own_agency_clients(self):
        """ClientViewSet list endpoint returns only own agency's active clients."""
        self.api_client.force_authenticate(user=self.owner_user)
        response = self.api_client.get('/api/clients/')
        self.assertEqual(response.status_code, 200)

        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        returned_ids = [c['id'] for c in results]

        self.assertIn(self.client_3.id, returned_ids)
        self.assertIn(self.client_2_second.id, returned_ids)
        self.assertNotIn(self.client_foreign.id, returned_ids)
        self.assertNotIn(self.client_2_paused.id, returned_ids)
        self.assertNotIn(self.client_2_terminated.id, returned_ids)
        self.assertNotIn(self.client_eu.id, returned_ids)

    def test_10_direct_foreign_client_detail_returns_403_or_404(self):
        """Accessing a foreign client's detail or summary directly returns 403 or 404."""
        self.api_client.force_authenticate(user=self.owner_user)

        # GET detail
        response = self.api_client.get(f'/api/clients/{self.client_foreign.id}/')
        self.assertIn(response.status_code, (403, 404))

        # GET summary
        summary_response = self.api_client.get(f'/api/clients/{self.client_foreign.id}/summary/')
        self.assertIn(summary_response.status_code, (403, 404))

    def test_11_client_switcher_receives_only_own_agency_clients(self):
        """Client switcher feed cannot be bypassed by injecting foreign client IDs into query params."""
        self.api_client.force_authenticate(user=self.owner_user)

        # Legitimate query param for own client
        res_own = self.api_client.get(f'/api/clients/?client_id={self.client_2_second.id}')
        self.assertEqual(res_own.status_code, 200)
        results_own = res_own.data if isinstance(res_own.data, list) else res_own.data.get('results', [])
        self.assertEqual(len(results_own), 1)
        self.assertEqual(results_own[0]['id'], self.client_2_second.id)

        # Spoofed foreign client_id query param
        res_spoof = self.api_client.get(f'/api/clients/?client_id={self.client_foreign.id}')
        self.assertEqual(res_spoof.status_code, 200)
        results_spoof = res_spoof.data if isinstance(res_spoof.data, list) else res_spoof.data.get('results', [])
        self.assertEqual(len(results_spoof), 0)
