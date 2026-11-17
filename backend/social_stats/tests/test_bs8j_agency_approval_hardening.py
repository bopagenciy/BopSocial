"""
BOP SOCIAL — PHASE BS-8J.1
AGENCY CLIENT APPROVAL HARDENING TESTS

Covers:
8. agency owner can approve own active managed client
9. agency admin can approve own active managed client
10. agency manager can approve if current permission policy allows
11. ordinary agency member denied
12. paused relation denied
13. terminated relation denied
14. foreign agency client denied
15. direct client owner approval remains unchanged
16. superadmin approval remains unchanged
Extra: agency member cannot approve when client has external owner_user
"""
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation, ApprovalRequest


class AgencyApprovalHardeningTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # Agency #2 (Bop Agencia)
        self.owner_user = User.objects.create_user(
            username='bopagencia@gmail.com',
            email='bopagencia@gmail.com',
            password='TestPassword123!',
        )
        self.agency_2 = Agency.objects.create(
            name='Bop Agencia',
            slug='bop-agencia',
            owner_user=self.owner_user,
        )
        self.owner_profile = UserProfile.objects.create(
            user=self.owner_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_owner = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.owner_user,
            role='owner',
            is_active=True,
        )

        # Admin in Agency #2
        self.admin_user = User.objects.create_user(
            username='agencyadmin@bop.local',
            email='agencyadmin@bop.local',
            password='TestPassword123!',
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_admin = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.admin_user,
            role='admin',
            is_active=True,
        )

        # Manager in Agency #2
        self.manager_user = User.objects.create_user(
            username='agencymanager@bop.local',
            email='agencymanager@bop.local',
            password='TestPassword123!',
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_manager = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.manager_user,
            role='manager',
            is_active=True,
        )

        # Ordinary Member in Agency #2
        self.member_user = User.objects.create_user(
            username='agencymember@bop.local',
            email='agencymember@bop.local',
            password='TestPassword123!',
        )
        self.member_profile = UserProfile.objects.create(
            user=self.member_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_member = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.member_user,
            role='member',
            is_active=True,
        )

        # Foreign Agency & Member
        self.foreign_agency_owner = User.objects.create_user(
            username='foreignowner@other.local',
            email='foreignowner@other.local',
            password='TestPassword123!',
        )
        self.foreign_agency = Agency.objects.create(
            name='Other Agency',
            slug='other-agency',
            owner_user=self.foreign_agency_owner,
        )
        self.foreign_profile = UserProfile.objects.create(
            user=self.foreign_agency_owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.foreign_agency,
        )
        self.foreign_membership = AgencyMembership.objects.create(
            agency=self.foreign_agency,
            user=self.foreign_agency_owner,
            role='owner',
            is_active=True,
        )

        # Superadmin user
        self.superadmin_user = User.objects.create_user(
            username='superadmin@system.local',
            email='superadmin@system.local',
            password='TestPassword123!',
            is_staff=True,
            is_superuser=True,
        )
        self.superadmin_profile = UserProfile.objects.create(
            user=self.superadmin_user,
            role='superadmin',
            account_type='legacy',
        )

        # Direct Client Owner (End User)
        self.end_user = User.objects.create_user(
            username='clientowner@external.local',
            email='clientowner@external.local',
            password='TestPassword123!',
        )
        self.end_user_client = Client.objects.create(
            name='External Client Corp',
            company='External Client Corp',
            email='clientowner@external.local',
            owner_user=self.end_user,
            ownership_type='end_user_owned',
        )
        self.end_user_profile = UserProfile.objects.create(
            user=self.end_user,
            role='client',
            account_type='end_user',
            client=self.end_user_client,
        )

        # Managed Client #21 (Agency-owned, no owner_user)
        self.client_21 = Client.objects.create(
            name='Alpha Admin',
            company='Test Alpha Brands S.A.',
            email='testalpha@alphabrands.com',
            ownership_type='agency_owned',
            requires_approval=True,
            owner_user=None,
        )
        self.rel_21 = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_21,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.owner_user,
        )

        # Approval Request for Client #21
        self.approval_21 = ApprovalRequest.objects.create(
            relation=self.rel_21,
            client=self.client_21,
            requested_by=self.member_user,
            action_type='publish_posts',
            payload={'text': 'Hello from Client 21'},
            status='pending',
        )

        # Approval Request for End-User Owned Client (managed by agency_2)
        self.rel_end_user = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.end_user_client,
            status='active',
            initiated_by='end_user',
            initiated_by_user=self.end_user,
        )
        self.approval_end_user = ApprovalRequest.objects.create(
            relation=self.rel_end_user,
            client=self.end_user_client,
            requested_by=self.owner_user,
            action_type='publish_posts',
            payload={'text': 'Agency draft for end-user client'},
            status='pending',
        )

    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_08_agency_owner_can_approve_own_active_managed_client(self, mock_exec):
        self.api_client.force_authenticate(user=self.owner_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 200, res.data)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'approved')
        self.assertEqual(self.approval_21.decided_by, self.owner_user)

    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_09_agency_admin_can_approve_own_active_managed_client(self, mock_exec):
        self.api_client.force_authenticate(user=self.admin_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 200, res.data)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'approved')
        self.assertEqual(self.approval_21.decided_by, self.admin_user)

    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_10_agency_manager_can_approve_own_active_managed_client(self, mock_exec):
        self.api_client.force_authenticate(user=self.manager_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 200, res.data)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'approved')
        self.assertEqual(self.approval_21.decided_by, self.manager_user)

    def test_11_ordinary_agency_member_denied(self):
        self.api_client.force_authenticate(user=self.member_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 403)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'pending')

    def test_12_paused_relation_denied(self):
        self.rel_21.status = 'paused'
        self.rel_21.save()

        self.api_client.force_authenticate(user=self.owner_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 403)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'pending')

    def test_13_terminated_relation_denied(self):
        self.rel_21.status = 'terminated'
        self.rel_21.save()

        self.api_client.force_authenticate(user=self.owner_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 403)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'pending')

    def test_14_foreign_agency_client_denied(self):
        self.api_client.force_authenticate(user=self.foreign_agency_owner)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 403)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'pending')

    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_15_direct_client_owner_approval_remains_unchanged(self, mock_exec):
        self.api_client.force_authenticate(user=self.end_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_end_user.id}/approve/')
        self.assertEqual(res.status_code, 200, res.data)
        self.approval_end_user.refresh_from_db()
        self.assertEqual(self.approval_end_user.status, 'approved')
        self.assertEqual(self.approval_end_user.decided_by, self.end_user)

    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_16_superadmin_approval_remains_unchanged(self, mock_exec):
        self.api_client.force_authenticate(user=self.superadmin_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_21.id}/approve/')
        self.assertEqual(res.status_code, 200, res.data)
        self.approval_21.refresh_from_db()
        self.assertEqual(self.approval_21.status, 'approved')
        self.assertEqual(self.approval_21.decided_by, self.superadmin_user)

    def test_extra_agency_cannot_approve_client_with_external_owner(self):
        # Agency owner cannot approve content on a client that has an external owner_user
        self.api_client.force_authenticate(user=self.owner_user)
        res = self.api_client.post(f'/api/approvals/{self.approval_end_user.id}/approve/')
        self.assertEqual(res.status_code, 403)
        self.approval_end_user.refresh_from_db()
        self.assertEqual(self.approval_end_user.status, 'pending')
