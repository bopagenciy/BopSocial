"""
BOP SOCIAL — PHASE BS-8J.2
AGENCY CLIENT USER INVITATION FLOW TESTS

Covers:
1. agency owner can invite own client user
2. agency admin can invite
3. agency manager can invite if permitted
4. ordinary member denied
5. end_user denied
6. foreign agency client denied
7. paused relation denied
8. terminated relation denied
9. agency_id injection impossible
10. duplicate pending invite rejected
11. email normalized
12. existing user acceptance works
13. new user acceptance flow works
14. token single-use
15. expired token rejected
16. revoked token rejected
17. approver can approve own client content
18. viewer cannot approve
19. editor cannot approve unless explicitly configured
20. cross-client access denied after acceptance
"""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import Client, UserProfile, ClientInvitation, ClientUserRole
from social_stats.marketplace_models import (
    Agency, AgencyMembership, AgencyClientRelation, ApprovalRequest
)


class AgencyClientInvitationTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()

        # Agency #2 (Bop Agencia)
        self.agency_owner_user = User.objects.create_user(
            username='bopagencia@gmail.com',
            email='bopagencia@gmail.com',
            password='TestPassword123!',
        )
        self.agency_2 = Agency.objects.create(
            name='Bop Agencia',
            slug='bop-agencia',
            owner_user=self.agency_owner_user,
        )
        self.owner_profile = UserProfile.objects.create(
            user=self.agency_owner_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_owner = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.agency_owner_user,
            role='owner',
            is_active=True,
        )

        # Admin in Agency #2
        self.agency_admin_user = User.objects.create_user(
            username='agencyadmin@bop.local',
            email='agencyadmin@bop.local',
            password='TestPassword123!',
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.agency_admin_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_admin = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.agency_admin_user,
            role='admin',
            is_active=True,
        )

        # Manager in Agency #2
        self.agency_manager_user = User.objects.create_user(
            username='agencymanager@bop.local',
            email='agencymanager@bop.local',
            password='TestPassword123!',
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.agency_manager_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_manager = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.agency_manager_user,
            role='manager',
            is_active=True,
        )

        # Ordinary Member in Agency #2
        self.agency_member_user = User.objects.create_user(
            username='agencymember@bop.local',
            email='agencymember@bop.local',
            password='TestPassword123!',
        )
        self.member_profile = UserProfile.objects.create(
            user=self.agency_member_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_2,
        )
        self.membership_member = AgencyMembership.objects.create(
            agency=self.agency_2,
            user=self.agency_member_user,
            role='member',
            is_active=True,
        )

        # Foreign Agency (Agency #9)
        self.foreign_owner_user = User.objects.create_user(
            username='foreign@agency.local',
            email='foreign@agency.local',
            password='TestPassword123!',
        )
        self.agency_foreign = Agency.objects.create(
            name='Foreign Agency',
            slug='foreign-agency',
            owner_user=self.foreign_owner_user,
        )
        self.foreign_profile = UserProfile.objects.create(
            user=self.foreign_owner_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency_foreign,
        )
        self.membership_foreign = AgencyMembership.objects.create(
            agency=self.agency_foreign,
            user=self.foreign_owner_user,
            role='owner',
            is_active=True,
        )

        # End user (non-agency)
        self.end_user = User.objects.create_user(
            username='enduser@bop.local',
            email='enduser@bop.local',
            password='TestPassword123!',
        )
        self.end_user_profile = UserProfile.objects.create(
            user=self.end_user,
            role='client',
            account_type='end_user',
        )

        # Managed Client #21 (Test Alpha Brands S.A.)
        self.client_21 = Client.objects.create(
            id=21,
            company='Test Alpha Brands S.A.',
            name='Alpha Brands Workspace',
            email='contact@alphabrands.test',
            ownership_type='agency_owned',
            is_active=True,
        )
        self.relation_21 = AgencyClientRelation.objects.create(
            agency=self.agency_2,
            client=self.client_21,
            status='active',
            initiated_by='agency',
            permissions={'can_publish': True},
        )

        # Foreign Client #30
        self.client_foreign = Client.objects.create(
            id=30,
            company='Foreign Brands Corp',
            name='Foreign Workspace',
            email='contact@foreignbrands.test',
            ownership_type='agency_owned',
            is_active=True,
        )
        self.relation_foreign = AgencyClientRelation.objects.create(
            agency=self.agency_foreign,
            client=self.client_foreign,
            status='active',
            initiated_by='agency',
            permissions={'can_publish': True},
        )

    # 1. agency owner can invite own client user
    def test_01_agency_owner_can_invite_own_client_user(self):
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'stakeholder1@alphabrands.test', 'role': 'approver', 'message': 'Welcome!'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['client_id'], self.client_21.id)
        self.assertEqual(res.data['agency_id'], self.agency_2.id)
        self.assertEqual(res.data['client_email'], 'stakeholder1@alphabrands.test')
        self.assertEqual(res.data['role'], 'approver')
        self.assertEqual(res.data['status'], 'pending')
        self.assertTrue(ClientInvitation.objects.filter(token=res.data['token']).exists())

    # 2. agency admin can invite
    def test_02_agency_admin_can_invite(self):
        self.api_client.force_authenticate(user=self.agency_admin_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'admininvite@alphabrands.test', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['role'], 'viewer')

    # 3. agency manager can invite if permitted
    def test_03_agency_manager_can_invite_if_permitted(self):
        self.api_client.force_authenticate(user=self.agency_manager_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'managerinvite@alphabrands.test', 'role': 'editor'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['role'], 'editor')

    # 4. ordinary member denied
    def test_04_ordinary_member_denied(self):
        self.api_client.force_authenticate(user=self.agency_member_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'denied@alphabrands.test', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    # 5. end_user denied
    def test_05_end_user_denied(self):
        self.api_client.force_authenticate(user=self.end_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'denied2@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    # 6. foreign agency client denied
    def test_06_foreign_agency_client_denied(self):
        # Agency #2 tries to invite into Client #30 (belongs to Agency #9)
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_foreign.id}/invite/',
            {'email': 'hacker@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    # 7. paused relation denied
    def test_07_paused_relation_denied(self):
        self.relation_21.status = 'paused'
        self.relation_21.save()
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'paused@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    # 8. terminated relation denied
    def test_08_terminated_relation_denied(self):
        self.relation_21.status = 'terminated'
        self.relation_21.save()
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'terminated@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    # 9. agency_id injection impossible
    def test_09_agency_id_injection_impossible(self):
        self.api_client.force_authenticate(user=self.agency_owner_user)
        # Attempt to pass foreign agency_id in body
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {
                'email': 'injection@alphabrands.test',
                'agency_id': self.agency_foreign.id,
                'agency': self.agency_foreign.id,
                'role': 'viewer',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        # Verify agency on created invitation is strictly agency_2
        inv = ClientInvitation.objects.get(token=res.data['token'])
        self.assertEqual(inv.agency_id, self.agency_2.id)
        self.assertNotEqual(inv.agency_id, self.agency_foreign.id)

    # 10. duplicate pending invite rejected
    def test_10_duplicate_pending_invite_rejected(self):
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res1 = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'dup@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res1.status_code, 201)

        res2 = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': 'dup@alphabrands.test'},
            format='json',
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn('pending invitation already exists', res2.data['error'])

    # 11. email normalized
    def test_11_email_normalized(self):
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {'email': '  MixedCase.User@AlphaBrands.Test  '},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        inv = ClientInvitation.objects.get(token=res.data['token'])
        self.assertEqual(inv.client_email, 'mixedcase.user@alphabrands.test')

    # 12. existing user acceptance works
    def test_12_existing_user_acceptance_works(self):
        existing_stakeholder = User.objects.create_user(
            username='existing@alphabrands.test',
            email='existing@alphabrands.test',
            password='ExistingPassword123!',
        )
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner_user,
            agency=self.agency_2,
            client_record=self.client_21,
            client_email='existing@alphabrands.test',
            role='approver',
            status='pending',
        )

        # Accept while authenticated as that existing user
        self.api_client.force_authenticate(user=existing_stakeholder)
        res = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'accepted')
        self.assertEqual(res.data['client_id'], self.client_21.id)
        self.assertEqual(res.data['role'], 'approver')

        inv.refresh_from_db()
        self.assertEqual(inv.status, 'accepted')
        self.assertIsNotNone(inv.accepted_at)
        self.assertEqual(inv.client_user, existing_stakeholder)

        # Verify ClientUserRole created
        user_role = ClientUserRole.objects.get(client=self.client_21, user=existing_stakeholder)
        self.assertEqual(user_role.role, 'approver')

    # 13. new user acceptance flow works
    def test_13_new_user_acceptance_flow_works(self):
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner_user,
            agency=self.agency_2,
            client_record=self.client_21,
            client_email='new.user@alphabrands.test',
            role='client_admin',
            status='pending',
        )

        self.api_client.logout()
        res = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {
                'password': 'SecureNewPassword123!',
                'full_name': 'Jane Stakeholder',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'accepted')
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

        # User was created
        created_user = User.objects.get(email='new.user@alphabrands.test')
        self.assertTrue(created_user.check_password('SecureNewPassword123!'))
        self.assertEqual(created_user.first_name, 'Jane')
        self.assertEqual(created_user.last_name, 'Stakeholder')

        # UserProfile attached only to client_21
        self.assertEqual(created_user.profile.client_id, self.client_21.id)
        self.assertEqual(created_user.profile.role, 'client')

        # ClientUserRole created
        user_role = ClientUserRole.objects.get(client=self.client_21, user=created_user)
        self.assertEqual(user_role.role, 'client_admin')

    # 14. token single-use
    def test_14_token_single_use(self):
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner_user,
            agency=self.agency_2,
            client_record=self.client_21,
            client_email='singleuse@alphabrands.test',
            role='viewer',
            status='pending',
        )

        # First use
        self.api_client.logout()
        res1 = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {'password': 'Password123!'},
            format='json',
        )
        self.assertEqual(res1.status_code, 200)

        # Second use attempt
        res2 = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {'password': 'Password123!'},
            format='json',
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn('no longer pending', res2.data['error'])

    # 15. expired token rejected
    def test_15_expired_token_rejected(self):
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner_user,
            agency=self.agency_2,
            client_record=self.client_21,
            client_email='expired@alphabrands.test',
            role='viewer',
            status='pending',
            expires_at=timezone.now() - timedelta(hours=1),
        )

        self.api_client.logout()
        res = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {'password': 'Password123!'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('expired', res.data['error'])
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'expired')

    # 16. revoked token rejected
    def test_16_revoked_token_rejected(self):
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner_user,
            agency=self.agency_2,
            client_record=self.client_21,
            client_email='revoked@alphabrands.test',
            role='viewer',
            status='revoked',
        )

        self.api_client.logout()
        res = self.api_client.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {'password': 'Password123!'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('revoked', res.data['error'])

    # 17. approver can approve own client content
    @patch('social_stats.approval_views.execute_approval', return_value=(True, 'executed', {}))
    def test_17_approver_can_approve_own_client_content(self, mock_exec):
        approver_user = User.objects.create_user(
            username='client.approver@alphabrands.test',
            email='client.approver@alphabrands.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=approver_user,
            role='client',
            account_type='end_user',
            client=self.client_21,
        )
        ClientUserRole.objects.create(
            client=self.client_21,
            user=approver_user,
            role='approver',
        )

        # Create approval request for Client #21
        approval = ApprovalRequest.objects.create(
            relation=self.relation_21,
            client=self.client_21,
            requested_by=self.agency_owner_user,
            action_type='publish_post',
            target_object_type='unified_post',
            target_object_id=999,
            payload={'text': 'Hello Alpha Brands!'},
            status='pending',
        )

        self.api_client.force_authenticate(user=approver_user)
        res = self.api_client.post(f'/api/approvals/{approval.id}/approve/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'approved')

    # 18. viewer cannot approve
    def test_18_viewer_cannot_approve(self):
        viewer_user = User.objects.create_user(
            username='client.viewer@alphabrands.test',
            email='client.viewer@alphabrands.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=viewer_user,
            role='client',
            account_type='end_user',
            client=self.client_21,
        )
        ClientUserRole.objects.create(
            client=self.client_21,
            user=viewer_user,
            role='viewer',
        )

        approval = ApprovalRequest.objects.create(
            relation=self.relation_21,
            client=self.client_21,
            requested_by=self.agency_owner_user,
            action_type='publish_post',
            target_object_type='unified_post',
            target_object_id=998,
            payload={'text': 'Test viewer'},
            status='pending',
        )

        self.api_client.force_authenticate(user=viewer_user)
        res = self.api_client.post(f'/api/approvals/{approval.id}/approve/', {}, format='json')
        self.assertEqual(res.status_code, 403)

    # 19. editor cannot approve unless explicitly configured
    def test_19_editor_cannot_approve_unless_configured(self):
        editor_user = User.objects.create_user(
            username='client.editor@alphabrands.test',
            email='client.editor@alphabrands.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=editor_user,
            role='client',
            account_type='end_user',
            client=self.client_21,
        )
        ClientUserRole.objects.create(
            client=self.client_21,
            user=editor_user,
            role='editor',
        )

        approval = ApprovalRequest.objects.create(
            relation=self.relation_21,
            client=self.client_21,
            requested_by=self.agency_owner_user,
            action_type='publish_post',
            target_object_type='unified_post',
            target_object_id=997,
            payload={'text': 'Test editor'},
            status='pending',
        )

        self.api_client.force_authenticate(user=editor_user)
        res = self.api_client.post(f'/api/approvals/{approval.id}/approve/', {}, format='json')
        self.assertEqual(res.status_code, 403)

    # 20. cross-client access denied after acceptance
    def test_20_cross_client_access_denied_after_acceptance(self):
        stakeholder_user = User.objects.create_user(
            username='stakeholder21@alphabrands.test',
            email='stakeholder21@alphabrands.test',
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=stakeholder_user,
            role='client',
            account_type='end_user',
            client=self.client_21,
        )
        ClientUserRole.objects.create(
            client=self.client_21,
            user=stakeholder_user,
            role='approver',
        )

        # Approval on Foreign Client #30
        foreign_approval = ApprovalRequest.objects.create(
            relation=self.relation_foreign,
            client=self.client_foreign,
            requested_by=self.foreign_owner_user,
            action_type='publish_post',
            target_object_type='unified_post',
            target_object_id=996,
            payload={'text': 'Foreign payload'},
            status='pending',
        )

        self.api_client.force_authenticate(user=stakeholder_user)
        # Cannot approve foreign client approval
        res = self.api_client.post(f'/api/approvals/{foreign_approval.id}/approve/', {}, format='json')
        self.assertEqual(res.status_code, 403)

        # Cannot view foreign client approval detail (forbidden)
        res_get = self.api_client.get(f'/api/approvals/{foreign_approval.id}/')
        self.assertEqual(res_get.status_code, 403)

        # UserProfile.can_access_client check
        self.assertTrue(stakeholder_user.profile.can_access_client(self.client_21.id))
        self.assertFalse(stakeholder_user.profile.can_access_client(self.client_foreign.id))
        self.assertFalse(stakeholder_user.profile.can_access_client(3))  # Client #3 untouched

    # 21. synthetic test invitation (Section I)
    def test_21_synthetic_test_invitation_alpha_brands(self):
        self.api_client.force_authenticate(user=self.agency_owner_user)
        res = self.api_client.post(
            f'/api/agency/clients/{self.client_21.id}/invite/',
            {
                'email': 'client.approver@bopagencia.test',
                'role': 'approver',
                'message': 'Synthetic invitation for Test Alpha Brands S.A.',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['client_id'], self.client_21.id)
        self.assertEqual(res.data['client_name'], 'Test Alpha Brands S.A.')
        self.assertEqual(res.data['client_email'], 'client.approver@bopagencia.test')
        self.assertEqual(res.data['role'], 'approver')
        self.assertEqual(res.data['status'], 'pending')
        token = res.data['token']
        self.assertTrue(bool(token))

        # Verify acceptance URL internally
        acceptance_url = res.data['invite_url']
        self.assertEqual(acceptance_url, f'/invitation/{token}')

        # Verify get_invitation
        self.api_client.logout()
        res_get = self.api_client.get(f'/api/invitations/token/{token}/')
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data['client_name'], 'Test Alpha Brands S.A.')
        self.assertEqual(res_get.data['role'], 'approver')
        self.assertEqual(res_get.data['status'], 'pending')
