"""
BOP SOCIAL — PHASE BS-9C
COMMERCIAL OPERATIONAL WORKFLOW COMPLETION TESTS

Covers the full end-to-end commercial journey with mocked external services
(publishers, email backend, no live AI or OAuth calls).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import (
    Client,
    UserProfile,
    ClientInvitation,
    ClientUserRole,
    UnifiedPost,
    MediaAsset,
    PlatformCredential,
    UserMFA,
)
from social_stats.marketplace_models import (
    Agency,
    AgencyMembership,
    AgencyClientRelation,
    ApprovalRequest,
    default_relation_permissions,
)
from social_stats.scheduler import process_scheduled_posts


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class BS9CCommercialWorkflowTests(TestCase):
    def setUp(self):
        self.api = APIClient()

        # Agency Owner (equivalent to bopagencia@gmail.com)
        self.agency_owner = User.objects.create_user(
            username='owner@bopagencia.test',
            email='owner@bopagencia.test',
            password='TestPassword123!',
        )
        self.agency = Agency.objects.create(
            name='Bop Agencia',
            slug='bop-agencia-bs9c',
            owner_user=self.agency_owner,
        )
        UserProfile.objects.create(
            user=self.agency_owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.agency_owner,
            role='owner',
            is_active=True,
        )

        # Client A (self-managed equivalent to Client #3)
        self.client_a = Client.objects.create(
            name='Bop Agencia Self',
            company='Bop Agencia Self',
            email='self@bopagencia.test',
            timezone='America/Bogota',
            requires_approval=False,
            is_active=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_a,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.agency_owner,
            permissions=default_relation_permissions(),
        )

        # Client B (managed client equivalent to Client #21)
        self.client_b = Client.objects.create(
            name='Alpha Brands',
            company='Test Alpha Brands S.A.',
            email='alpha@bopagencia.test',
            timezone='America/Bogota',
            requires_approval=True,
            ownership_type='agency_owned',
            is_active=True,
        )
        perms = default_relation_permissions()
        perms['publish_posts'] = 'approval_required'
        self.relation_b = AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_b,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.agency_owner,
            permissions=perms,
        )

        # Foreign client (different agency)
        self.foreign_user = User.objects.create_user(
            username='other@foreign.test',
            email='other@foreign.test',
            password='TestPassword123!',
        )
        self.foreign_agency = Agency.objects.create(
            name='Foreign Agency',
            slug='foreign-bs9c',
            owner_user=self.foreign_user,
        )
        UserProfile.objects.create(
            user=self.foreign_user,
            role='client',
            account_type='agency_member',
            primary_agency=self.foreign_agency,
        )
        AgencyMembership.objects.create(
            agency=self.foreign_agency,
            user=self.foreign_user,
            role='owner',
            is_active=True,
        )
        self.foreign_client = Client.objects.create(
            name='Foreign Brand',
            company='Foreign Brand',
            email='brand@foreign.test',
            is_active=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.foreign_agency,
            client=self.foreign_client,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.foreign_user,
            permissions=default_relation_permissions(),
        )

        PlatformCredential.objects.create(
            client=self.client_b,
            platform='facebook',
            access_token='mock-token',
            page_id='fb-page-b',
            page_name='Alpha FB',
            is_active=True,
        )

    @patch('social_stats.orchestrator.get_publisher')
    @patch('social_stats.composer_views.media_service.upload_media')
    @patch('social_stats.invitation_views.send_mail')
    def test_01_full_commercial_journey_end_to_end(self, mock_send_mail, mock_upload, mock_get_pub):
        # 1. Agency invites new client approver (email sent via mocked backend)
        self.api.force_authenticate(user=self.agency_owner)
        res_inv = self.api.post(
            f'/api/agency/clients/{self.client_b.id}/invitations/',
            {'email': 'approver.alpha@bopagencia.test', 'role': 'approver', 'message': 'Welcome!'},
            format='json',
        )
        self.assertEqual(res_inv.status_code, 201)
        self.assertTrue(res_inv.data['email_sent'])
        self.assertIsNone(res_inv.data['email_error'])
        mock_send_mail.assert_called_once()
        invite_token = res_inv.data['token']

        # 2. New invited user accepts in browser (sets own password)
        self.api.logout()
        res_acc = self.api.post(
            f'/api/invitations/token/{invite_token}/accept/',
            {'full_name': 'Alpha Approver', 'password': 'SecurePassword123!'},
            format='json',
        )
        self.assertEqual(res_acc.status_code, 200)
        approver_user = User.objects.get(email='approver.alpha@bopagencia.test')
        self.assertEqual(res_acc.data['role'], 'approver')

        # 3. Client portal resolves workspace, managing agency, and role
        self.api.force_authenticate(user=approver_user)
        res_me = self.api.get('/api/end-user/me/')
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.data['workspace']['id'], self.client_b.id)
        self.assertEqual(res_me.data['managing_agency']['name'], 'Bop Agencia')
        self.assertEqual(res_me.data['client_role'], 'approver')

        # 4. Agency owner configures Client #21 business profile
        self.api.force_authenticate(user=self.agency_owner)
        res_profile = self.api.patch(
            f'/api/clients/{self.client_b.id}/',
            {'brand_tone': 'professional', 'target_audience': 'B2B Marketing Teams'},
            format='json',
        )
        self.assertEqual(res_profile.status_code, 200)

        # 5. Agency owner uploads media & creates post scoped to Client B (not Client A)
        mock_upload.return_value = MediaAsset.objects.create(
            client=self.client_b,
            uploaded_by=self.agency_owner,
            mime_type='image/png',
            file_size=1024,
            width=800,
            height=800,
        )
        img = SimpleUploadedFile('test.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        res_media = self.api.post(
            '/api/composer/media/',
            {'file': img, 'client': self.client_b.id},
            format='multipart',
        )
        self.assertIn(res_media.status_code, (201, 200))

        future_dt = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
        res_post = self.api.post(
            '/api/composer/posts/',
            {
                'client': self.client_b.id,
                'title': 'Alpha Launch',
                'content': 'Commercial launch announcement',
                'media_type': 'text',
                'target_platforms': ['facebook'],
            },
            format='json',
        )
        self.assertEqual(res_post.status_code, 201)
        post_id = res_post.data['id']
        self.assertEqual(res_post.data['client'], self.client_b.id)

        # Schedule & submit for approval
        res_sched = self.api.post(
            f'/api/composer/posts/{post_id}/schedule/',
            {'scheduled_at': future_dt.isoformat()},
            format='json',
        )
        self.assertEqual(res_sched.status_code, 200)
        self.assertEqual(res_sched.data['status'], 'pending_approval')

        # 6. Calendar shows UnifiedPost on the correct workspace timezone date
        local_date = future_dt.astimezone(timezone.get_fixed_timezone(-300)).date()
        res_cal = self.api.get(
            f'/api/calendar/posts/?client_id={self.client_b.id}&month={local_date.month}&year={local_date.year}'
        )
        self.assertEqual(res_cal.status_code, 200)
        day_items = res_cal.data.get(local_date.isoformat(), [])
        self.assertTrue(any(item.get('unified_post_id') == post_id and item.get('status') == 'pending_approval' for item in day_items))

        # 7. Client approver approves post in portal -> scheduled (not published early)
        self.api.force_authenticate(user=approver_user)
        res_approve = self.api.post(f'/api/composer/posts/{post_id}/approve/', {}, format='json')
        self.assertEqual(res_approve.status_code, 200)
        self.assertEqual(res_approve.data['status'], 'scheduled')

        # 8. Move scheduled_at to past and run scheduler with mocked publisher
        UnifiedPost.objects.filter(pk=post_id).update(scheduled_at=timezone.now() - timedelta(minutes=1))
        mock_pub = MagicMock()
        mock_pub.publish_text.return_value = SimpleNamespace(
            platform_post_id='fb_live_mock_1',
            platform_url='https://facebook.com/mock1',
            raw_response={'id': 'fb_live_mock_1'},
        )
        mock_get_pub.return_value = mock_pub

        with self.captureOnCommitCallbacks(execute=True):
            dispatched = process_scheduled_posts()
        self.assertEqual(dispatched, 1)
        post = UnifiedPost.objects.get(pk=post_id)
        self.assertEqual(post.status, 'published')
        mock_pub.publish_text.assert_called_once()

        # 9. Analytics & Executive Reports accessible to agency owner and client approver
        for auth_user in (self.agency_owner, approver_user):
            self.api.force_authenticate(user=auth_user)
            res_sum = self.api.get(f'/api/analytics/summary/?client_id={self.client_b.id}')
            self.assertEqual(res_sum.status_code, 200)
            res_reps = self.api.get(f'/api/analytics/reports/?client_id={self.client_b.id}')
            self.assertEqual(res_reps.status_code, 200)

        # Approver (non-editor) cannot generate reports (read != write)
        self.api.force_authenticate(user=approver_user)
        res_gen = self.api.post('/api/analytics/reports/', {'client_id': self.client_b.id}, format='json')
        self.assertEqual(res_gen.status_code, 403)

        # Foreign client analytics remain inaccessible (404)
        self.api.force_authenticate(user=self.agency_owner)
        res_foreign = self.api.get(f'/api/analytics/summary/?client_id={self.foreign_client.id}')
        self.assertEqual(res_foreign.status_code, 404)

    @patch('social_stats.invitation_views.send_mail', side_effect=RuntimeError('SMTP connection refused'))
    def test_02_email_delivery_failure_is_visible_and_recoverable(self, mock_send_mail):
        self.api.force_authenticate(user=self.agency_owner)
        res = self.api.post(
            f'/api/agency/clients/{self.client_b.id}/invitations/',
            {'email': 'smtpfail@bopagencia.test', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data['email_sent'])
        self.assertIn('SMTP connection refused', res.data['email_error'])
        self.assertTrue(res.data['invite_url'].startswith('/invitation/'))

    def test_03_mfa_existing_user_cannot_bypass_mfa_on_invite_accept(self):
        mfa_user = User.objects.create_user(
            username='mfa@bopagencia.test',
            email='mfa@bopagencia.test',
            password='TestPassword123!',
        )
        UserMFA.objects.create(user=mfa_user, is_enabled=True)
        inv = ClientInvitation.objects.create(
            invited_by=self.agency_owner,
            agency=self.agency,
            client_record=self.client_b,
            client_email='mfa@bopagencia.test',
            role='approver',
            status='pending',
        )
        self.api.logout()
        res = self.api.post(
            f'/api/invitations/token/{inv.token}/accept/',
            {'password': 'TestPassword123!'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)
        self.assertTrue(res.data.get('mfa_required'))
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'pending')

    def test_04_calendar_reschedule_respects_approval_gate_and_no_external_dispatch(self):
        future_dt = (timezone.now() + timedelta(days=3)).replace(microsecond=0)
        post = UnifiedPost.objects.create(
            client=self.client_b,
            created_by=self.agency_owner,
            content='Calendar reschedule test',
            target_platforms=['facebook'],
            status='draft',
        )
        self.api.force_authenticate(user=self.agency_owner)
        with patch('social_stats.orchestrator.publish_unified_post.delay') as mock_delay:
            res = self.api.post(
                f'/api/calendar/posts/unified-{post.id}/reschedule/',
                {'scheduled_at': future_dt.isoformat()},
                format='json',
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['status'], 'pending_approval')
            mock_delay.assert_not_called()
