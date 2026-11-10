from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from social_stats.models import Client, UserProfile
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation
from social_stats.views import _agency_client_ids


class TenantScopingHardeningTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        # Agency A and Owner
        self.owner_user_a = User.objects.create_user(
            username='owner_a@test.local', email='owner_a@test.local', password='password123'
        )
        self.agency_a = Agency.objects.create(
            name='Agency Alpha', slug='agency-alpha', owner_user=self.owner_user_a
        )
        self.profile_a = UserProfile.objects.create(
            user=self.owner_user_a,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_a,
        )
        self.membership_a = AgencyMembership.objects.create(
            agency=self.agency_a, user=self.owner_user_a, role='owner', is_active=True
        )

        # Agency B and Owner
        self.owner_user_b = User.objects.create_user(
            username='owner_b@test.local', email='owner_b@test.local', password='password123'
        )
        self.agency_b = Agency.objects.create(
            name='Agency Beta', slug='agency-beta', owner_user=self.owner_user_b
        )
        self.profile_b = UserProfile.objects.create(
            user=self.owner_user_b,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_b,
        )
        self.membership_b = AgencyMembership.objects.create(
            agency=self.agency_b, user=self.owner_user_b, role='owner', is_active=True
        )

        # Clients
        self.client_a1 = Client.objects.create(name='Client A1', company='Client A1', email='a1@test.local')
        self.client_a2 = Client.objects.create(name='Client A2', company='Client A2', email='a2@test.local')
        self.client_b1 = Client.objects.create(name='Client B1', company='Client B1', email='b1@test.local')
        self.client_paused = Client.objects.create(name='Client Paused', company='Client Paused', email='paused@test.local')
        self.client_terminated = Client.objects.create(name='Client Term', company='Client Term', email='term@test.local')

        # Active relations for Agency A
        AgencyClientRelation.objects.create(
            agency=self.agency_a, client=self.client_a1, status='active', initiated_by='agency'
        )
        AgencyClientRelation.objects.create(
            agency=self.agency_a, client=self.client_a2, status='active', initiated_by='agency'
        )

        # Active relation for Agency B
        AgencyClientRelation.objects.create(
            agency=self.agency_b, client=self.client_b1, status='active', initiated_by='agency'
        )

        # Paused and Terminated relations for Agency A
        AgencyClientRelation.objects.create(
            agency=self.agency_a, client=self.client_paused, status='paused', initiated_by='agency'
        )
        AgencyClientRelation.objects.create(
            agency=self.agency_a, client=self.client_terminated, status='terminated', initiated_by='agency'
        )

    def test_agency_owner_sees_all_active_clients_of_own_agency(self):
        """1. Agency owner sees all active clients of their own agency."""
        request = self.factory.get('/api/credentials/')
        request.user = self.owner_user_a
        cids = _agency_client_ids(request)
        self.assertIn(self.client_a1.id, cids)
        self.assertIn(self.client_a2.id, cids)

    def test_agency_owner_cannot_see_another_agency_clients(self):
        """2. Agency owner cannot see another agency's clients."""
        request = self.factory.get('/api/credentials/')
        request.user = self.owner_user_a
        cids = _agency_client_ids(request)
        self.assertNotIn(self.client_b1.id, cids)

    def test_inactive_and_paused_relations_are_excluded(self):
        """3. Inactive/paused/terminated relations are excluded."""
        request = self.factory.get('/api/credentials/')
        request.user = self.owner_user_a
        cids = _agency_client_ids(request)
        self.assertNotIn(self.client_paused.id, cids)
        self.assertNotIn(self.client_terminated.id, cids)

    def test_direct_end_user_behavior_unchanged(self):
        """4. Direct client/end-user behavior remains strictly unchanged."""
        end_user = User.objects.create_user(
            username='enduser@test.local', email='enduser@test.local', password='password123'
        )
        direct_client = Client.objects.create(name='Direct Client', company='Direct Corp', email='direct@test.local')
        UserProfile.objects.create(
            user=end_user,
            role='client',
            account_type='end_user',
            client=direct_client,
        )
        request = self.factory.get('/api/credentials/')
        request.user = end_user
        cids = _agency_client_ids(request)
        self.assertEqual(cids, [direct_client.id])

    def test_staff_assigned_client_behavior_unchanged(self):
        """5. Staff assigned_clients behavior remains strictly unchanged."""
        staff_user = User.objects.create_user(
            username='staff@test.local', email='staff@test.local', password='password123'
        )
        client_s1 = Client.objects.create(name='Staff C1', company='Staff C1', email='s1@test.local')
        client_s2 = Client.objects.create(name='Staff C2', company='Staff C2', email='s2@test.local')
        staff_profile = UserProfile.objects.create(
            user=staff_user,
            role='staff',
            account_type='legacy',
        )
        staff_profile.assigned_clients.add(client_s1, client_s2)
        request = self.factory.get('/api/credentials/')
        request.user = staff_user
        cids = _agency_client_ids(request)
        self.assertCountEqual(cids, [client_s1.id, client_s2.id])
