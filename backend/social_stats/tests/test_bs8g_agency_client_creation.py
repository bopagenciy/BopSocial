"""
BOP SOCIAL — PHASE BS-8G
AGENCY-SCOPED CLIENT CREATION TESTS

Covers:
1. owner can create agency client
2. admin can create agency client
3. manager can create agency client
4. ordinary member denied
5. end_user denied
6. superadmin without agency membership denied / cannot spoof agency
7. agency_id payload injection ignored/rejected (created under user's primary agency)
8. Client + AgencyClientRelation created atomically
9. ownership_type forced agency_owned
10. created_via forced agency_invite
11. relation status active
12. duplicate normalized email rejected
13. cross-agency creation impossible
14. failed relation creation rolls back Client
15. new client immediately visible through agency-scoped ClientViewSet
"""
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation


class AgencyClientCreationTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # ── Canonical Agency #2 (Bop Agencia) & Owner ────────────────────────
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
        self.client_3 = Client.objects.create(
            name='Bop Agencia',
            company='Bop Agencia',
            email='bopagencia-ws@test.local',
            ownership_type='agency_owned',
            is_active=True,
        )
        self.owner_profile = UserProfile.objects.create(
            user=self.owner_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
            client=self.client_3,
            default_workspace=self.client_3,
            email_verified=True,
            terms_accepted=True,
        )
        self.owner_membership = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.owner_user,
            role='owner',
            is_active=True,
        )
        self.rel_client_3 = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_3,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # ── Foreign Agency (Agency Foreign) ──────────────────────────────────
        self.foreign_owner = User.objects.create_user(
            username='foreign@agency.local',
            email='foreign@agency.local',
            password='TestPassword123!',
        )
        self.foreign_agency = Agency.objects.create(
            name='Foreign Agency',
            slug='foreign-agency',
            owner_user=self.foreign_owner,
        )
        self.foreign_client = Client.objects.create(
            name='Foreign Workspace',
            company='Foreign Co',
            email='foreign@corp.local',
        )
        self.foreign_profile = UserProfile.objects.create(
            user=self.foreign_owner,
            account_type='agency_member',
            primary_agency=self.foreign_agency,
            client=self.foreign_client,
        )
        AgencyMembership.objects.create(
            agency=self.foreign_agency,
            user=self.foreign_owner,
            role='owner',
            is_active=True,
        )

        # ── Agency Admin User ────────────────────────────────────────────────
        self.admin_user = User.objects.create_user(
            username='admin@bopagencia.test',
            email='admin@bopagencia.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=self.admin_user,
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.admin_user,
            role='admin',
            is_active=True,
        )

        # ── Agency Manager User ──────────────────────────────────────────────
        self.manager_user = User.objects.create_user(
            username='manager@bopagencia.test',
            email='manager@bopagencia.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=self.manager_user,
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.manager_user,
            role='manager',
            is_active=True,
        )

        # ── Agency Member User (role: member) ────────────────────────────────
        self.member_user = User.objects.create_user(
            username='member@bopagencia.test',
            email='member@bopagencia.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=self.member_user,
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.member_user,
            role='member',
            is_active=True,
        )

        # ── Direct End User ──────────────────────────────────────────────────
        self.end_user = User.objects.create_user(
            username='enduser@external.local',
            email='enduser@external.local',
            password='TestPassword123!',
        )
        self.end_user_client = Client.objects.create(
            name='Standalone Client',
            company='Standalone Client',
            email='standalone@test.local',
        )
        UserProfile.objects.create(
            user=self.end_user,
            role='client',
            account_type='end_user',
            client=self.end_user_client,
        )

        # ── Superadmin User ──────────────────────────────────────────────────
        self.superadmin = User.objects.create_user(
            username='superadmin@test.local',
            email='superadmin@test.local',
            password='TestPassword123!',
            is_staff=True,
            is_superuser=True,
        )
        UserProfile.objects.create(
            user=self.superadmin,
            role='superadmin',
            account_type='staff',
        )

    # 1. owner can create agency client
    def test_01_owner_can_create_agency_client(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Alpha Brand Co',
            'name': 'Alpha Brand',
            'email': 'alpha@brand.local',
            'website': 'https://alphabrand.local',
            'default_language': 'es',
            'currency': 'USD',
            'requires_approval': True,
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('client', data)
        self.assertEqual(data['client']['company'], 'Alpha Brand Co')
        self.assertEqual(data['client']['email'], 'alpha@brand.local')

        client = Client.objects.get(email='alpha@brand.local')
        self.assertEqual(client.company, 'Alpha Brand Co')
        self.assertEqual(client.requires_approval, True)

    # 2. admin can create agency client
    def test_02_admin_can_create_agency_client(self):
        self.api_client.force_authenticate(user=self.admin_user)
        payload = {
            'company': 'Beta Brand Co',
            'name': 'Beta Brand',
            'email': 'beta@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Client.objects.filter(email='beta@brand.local').exists())

    # 3. manager can create agency client
    def test_03_manager_can_create_agency_client(self):
        self.api_client.force_authenticate(user=self.manager_user)
        payload = {
            'company': 'Gamma Brand Co',
            'name': 'Gamma Brand',
            'email': 'gamma@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Client.objects.filter(email='gamma@brand.local').exists())

    # 4. ordinary member denied
    def test_04_ordinary_member_denied(self):
        self.api_client.force_authenticate(user=self.member_user)
        payload = {
            'company': 'Delta Brand Co',
            'name': 'Delta Brand',
            'email': 'delta@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(Client.objects.filter(email='delta@brand.local').exists())

    # 5. end_user denied
    def test_05_end_user_denied(self):
        self.api_client.force_authenticate(user=self.end_user)
        payload = {
            'company': 'Epsilon Brand Co',
            'name': 'Epsilon Brand',
            'email': 'epsilon@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(Client.objects.filter(email='epsilon@brand.local').exists())

    # 6. superadmin without agency membership denied
    def test_06_superadmin_without_agency_membership_denied(self):
        self.api_client.force_authenticate(user=self.superadmin)
        payload = {
            'company': 'Zeta Brand Co',
            'name': 'Zeta Brand',
            'email': 'zeta@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 403)

    # 7. agency_id payload injection ignored/rejected
    def test_07_agency_id_payload_injection_ignored(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Injected Agency Co',
            'name': 'Injected Agency',
            'email': 'injected@brand.local',
            'agency_id': self.foreign_agency.id,
            'agency': self.foreign_agency.id,
            'primary_agency': self.foreign_agency.id,
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='injected@brand.local')
        relation = AgencyClientRelation.objects.get(client=client)
        # MUST belong to Bop Agencia, NEVER Foreign Agency
        self.assertEqual(relation.agency_id, self.agency_2.id)
        self.assertNotEqual(relation.agency_id, self.foreign_agency.id)

    # 8. Client + AgencyClientRelation created atomically
    def test_08_client_and_relation_created_atomically(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Atomic Test Co',
            'name': 'Atomic Test',
            'email': 'atomic@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='atomic@brand.local')
        relation = AgencyClientRelation.objects.get(client=client)
        self.assertEqual(relation.agency, self.agency_2)
        self.assertEqual(relation.initiated_by_user, self.owner_user)

    # 9. ownership_type forced agency_owned
    def test_09_ownership_type_forced_agency_owned(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Ownership Co',
            'name': 'Ownership Test',
            'email': 'ownership@brand.local',
            'ownership_type': 'independent',  # Client-side spoof attempt
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='ownership@brand.local')
        self.assertEqual(client.ownership_type, 'agency_owned')

    # 10. created_via forced agency_invite
    def test_10_created_via_forced_agency_invite(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'CreatedVia Co',
            'name': 'CreatedVia Test',
            'email': 'createdvia@brand.local',
            'created_via': 'self_signup',  # Client-side spoof attempt
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='createdvia@brand.local')
        self.assertEqual(client.created_via, 'agency_invite')

    # 11. relation status active
    def test_11_relation_status_active(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'RelStatus Co',
            'name': 'RelStatus Test',
            'email': 'relstatus@brand.local',
            'status': 'pending',  # Client-side spoof attempt
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='relstatus@brand.local')
        relation = AgencyClientRelation.objects.get(client=client)
        self.assertEqual(relation.status, 'active')
        self.assertEqual(relation.initiated_by, 'agency')

    # 12. duplicate normalized email rejected
    def test_12_duplicate_normalized_email_rejected(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Dup Co',
            'name': 'Dup Test',
            'email': 'DUP@brand.LOCAL',
        }
        res1 = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res1.status_code, 201)

        # Attempt to create duplicate with different casing / whitespace
        payload_dup = {
            'company': 'Dup Co 2',
            'name': 'Dup Test 2',
            'email': '  dup@brand.local  ',
        }
        res2 = self.api_client.post('/api/agency/clients/', payload_dup, format='json')
        self.assertEqual(res2.status_code, 400)
        self.assertIn('already exists', str(res2.json()))

    # 13. cross-agency creation impossible
    def test_13_cross_agency_creation_impossible(self):
        # Authenticated as foreign owner
        self.api_client.force_authenticate(user=self.foreign_owner)
        payload = {
            'company': 'Foreign Created Co',
            'name': 'Foreign Created',
            'email': 'foreigncreated@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)

        client = Client.objects.get(email='foreigncreated@brand.local')
        relation = AgencyClientRelation.objects.get(client=client)
        # Foreign owner creation cannot link to Agency #2
        self.assertEqual(relation.agency_id, self.foreign_agency.id)
        self.assertNotEqual(relation.agency_id, self.agency_2.id)

        # And Bop owner cannot see Foreign Created Co
        self.api_client.force_authenticate(user=self.owner_user)
        list_res = self.api_client.get('/api/agency/clients/')
        self.assertEqual(list_res.status_code, 200)
        client_ids = [c['id'] for c in list_res.json()]
        self.assertNotIn(client.id, client_ids)

    # 14. failed relation creation rolls back Client
    def test_14_failed_relation_creation_rolls_back_client(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Rollback Co',
            'name': 'Rollback Test',
            'email': 'rollback@brand.local',
        }
        with patch.object(AgencyClientRelation.objects, 'create', side_effect=Exception('DB Error')):
            with self.assertRaises(Exception):
                self.api_client.post('/api/agency/clients/', payload, format='json')

        # Ensure Client was rolled back and does not exist in DB
        self.assertFalse(Client.objects.filter(email='rollback@brand.local').exists())

    # 15. new client immediately visible through agency-scoped ClientViewSet
    def test_15_new_client_immediately_visible_through_clientviewset(self):
        self.api_client.force_authenticate(user=self.owner_user)
        payload = {
            'company': 'Visible Co',
            'name': 'Visible Test',
            'email': 'visible@brand.local',
        }
        res = self.api_client.post('/api/agency/clients/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        new_client_id = res.json()['client']['id']

        # Query /api/clients/ (ClientViewSet.get_queryset())
        clients_res = self.api_client.get('/api/clients/')
        self.assertEqual(clients_res.status_code, 200)
        results = clients_res.data if isinstance(clients_res.data, list) else clients_res.data.get('results', [])
        accessible_ids = [c['id'] for c in results]

        self.assertIn(self.client_3.id, accessible_ids)
        self.assertIn(new_client_id, accessible_ids)
        self.assertNotIn(self.foreign_client.id, accessible_ids)
