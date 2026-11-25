"""
BOP SOCIAL — PHASE BS-9B
COMMERCIAL SECURITY & PUBLISHING HARDENING TESTS

Focused validation using mocked publishers and mocked OAuth providers only.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import (
    Client,
    UserProfile,
    ClientUserRole,
    UnifiedPost,
    PlatformCredential,
    PlatformPublishLog,
)
from social_stats.marketplace_models import (
    Agency,
    AgencyMembership,
    AgencyClientRelation,
    ApprovalRequest,
    default_relation_permissions,
)
from social_stats.orchestrator import publish_unified_post
from social_stats.scheduler import process_scheduled_posts


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class BS9BSecurityPublishingHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

        # Agency A & Owner
        self.agency_owner = User.objects.create_user(
            username='agency.owner@bs9b.test',
            email='agency.owner@bs9b.test',
            password='TestPassword123!',
        )
        self.agency = Agency.objects.create(
            name='Agency BS9B',
            slug='agency-bs9b',
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

        # Managed Client (requires_approval=True, no direct owner_user)
        self.client_managed = Client.objects.create(
            name='Alpha Co',
            company='Alpha Co S.A.',
            email='alpha@bs9b.test',
            requires_approval=True,
            ownership_type='agency_owned',
            is_active=True,
        )
        perms = default_relation_permissions()
        perms['publish_posts'] = 'approval_required'
        perms['connect_platforms'] = 'allowed'
        self.relation = AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_managed,
            status='active',
            initiated_by='agency',
            initiated_by_user=self.agency_owner,
            permissions=perms,
        )

        # Foreign Agency & Client
        self.foreign_user = User.objects.create_user(
            username='foreign@bs9b.test',
            email='foreign@bs9b.test',
            password='TestPassword123!',
        )
        self.foreign_agency = Agency.objects.create(
            name='Foreign Agency',
            slug='foreign-bs9b',
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
            name='Foreign Co',
            company='Foreign Co S.A.',
            email='foreign.co@bs9b.test',
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

        # Client-scoped roles on client_managed
        self.viewer = self._make_client_user('viewer@bs9b.test', 'viewer')
        self.approver = self._make_client_user('approver@bs9b.test', 'approver')
        self.editor = self._make_client_user('editor@bs9b.test', 'editor')
        self.client_admin = self._make_client_user('cadmin@bs9b.test', 'client_admin')

        # Direct owner client (legacy/self-managed)
        self.direct_owner = User.objects.create_user(
            username='direct@bs9b.test',
            email='direct@bs9b.test',
            password='TestPassword123!',
        )
        self.direct_client = Client.objects.create(
            name='Direct Co',
            company='Direct Co',
            email='direct@bs9b.test',
            owner_user=self.direct_owner,
            requires_approval=False,
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.direct_owner,
            role='client',
            account_type='end_user',
            client=self.direct_client,
        )

        # Active Facebook credential for managed client
        self.fb_cred = PlatformCredential.objects.create(
            client=self.client_managed,
            platform='facebook',
            access_token='mock-fb-token',
            page_id='123456',
            page_name='Alpha Page',
            is_active=True,
        )

    def _make_client_user(self, email, role_name):
        u = User.objects.create_user(
            username=email,
            email=email,
            password='TestPassword123!',
        )
        UserProfile.objects.create(
            user=u,
            role='client',
            account_type='end_user',
            client=self.client_managed,
        )
        ClientUserRole.objects.create(
            client=self.client_managed,
            user=u,
            role=role_name,
        )
        return u

    # 1. Approved posts proceed through mocked publishing
    @patch('social_stats.orchestrator.get_publisher')
    def test_01_approved_post_proceeds_through_mocked_publishing(self, mock_get_pub):
        mock_pub = MagicMock()
        mock_pub.publish_text.return_value = SimpleNamespace(
            platform_post_id='fb_post_101',
            platform_url='https://facebook.com/101',
            raw_response={'id': 'fb_post_101'},
        )
        mock_get_pub.return_value = mock_pub

        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.agency_owner,
            content='Approved launch post',
            target_platforms=['facebook'],
            status='pending_approval',
        )
        ar = ApprovalRequest.objects.create(
            relation=self.relation,
            client=self.client_managed,
            requested_by=self.agency_owner,
            action_type='publish_post',
            payload={'post_id': post.id},
            target_object_type='UnifiedPost',
            target_object_id=post.id,
        )

        self.api.force_authenticate(user=self.approver)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.api.post(f'/api/approvals/{ar.id}/approve/', {}, format='json')

        self.assertEqual(res.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.approved_by_id, self.approver.id)
        self.assertIsNotNone(post.approved_at)
        self.assertEqual(post.status, 'published')
        mock_pub.publish_text.assert_called_once()

    # 2. Unapproved scheduled posts cannot publish
    @patch('social_stats.orchestrator.get_publisher')
    @patch('social_stats.notification_watchers.notify_approver_for_post.delay')
    def test_02_unapproved_scheduled_post_cannot_publish(self, mock_notify, mock_get_pub):
        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.agency_owner,
            content='Sneaky unapproved scheduled post',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=timezone.now() - timedelta(minutes=5),
            approved_by=None,
        )

        # Direct orchestrator call must refuse and move to pending_approval
        publish_unified_post(post.id)
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')
        mock_get_pub.assert_not_called()

        # Scheduler tick must also refuse unapproved scheduled posts
        post.status = 'scheduled'
        post.save(update_fields=['status'])
        with self.captureOnCommitCallbacks(execute=True):
            dispatched = process_scheduled_posts()
        self.assertEqual(dispatched, 0)
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')
        mock_get_pub.assert_not_called()

    # 3. Rejected posts cannot publish
    @patch('social_stats.orchestrator.get_publisher')
    def test_03_rejected_post_cannot_publish(self, mock_get_pub):
        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.agency_owner,
            content='Rejected post',
            target_platforms=['facebook'],
            status='pending_approval',
        )
        ar = ApprovalRequest.objects.create(
            relation=self.relation,
            client=self.client_managed,
            requested_by=self.agency_owner,
            action_type='publish_post',
            payload={'post_id': post.id},
            target_object_type='UnifiedPost',
            target_object_id=post.id,
        )

        self.api.force_authenticate(user=self.approver)
        res = self.api.post(
            f'/api/approvals/{ar.id}/reject/',
            {'reason': 'Off brand'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)

        post.refresh_from_db()
        self.assertEqual(post.status, 'draft')
        self.assertIsNone(post.approved_by_id)

        publish_unified_post(post.id)
        mock_get_pub.assert_not_called()

    # 4. Future scheduled posts are not published early after approval
    @patch('social_stats.orchestrator.publish_unified_post.delay')
    @patch('social_stats.orchestrator.get_publisher')
    def test_04_future_scheduled_post_not_published_early(self, mock_get_pub, mock_delay):
        future_dt = timezone.now() + timedelta(days=2)
        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.agency_owner,
            content='Future post',
            target_platforms=['facebook'],
            status='pending_approval',
            scheduled_at=future_dt,
        )
        ar = ApprovalRequest.objects.create(
            relation=self.relation,
            client=self.client_managed,
            requested_by=self.agency_owner,
            action_type='publish_post',
            payload={'post_id': post.id},
            target_object_type='UnifiedPost',
            target_object_id=post.id,
        )

        self.api.force_authenticate(user=self.approver)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.api.post(f'/api/approvals/{ar.id}/approve/', {}, format='json')

        self.assertEqual(res.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')
        self.assertEqual(post.approved_by_id, self.approver.id)
        self.assertEqual(post.scheduled_at, future_dt)
        mock_delay.assert_not_called()
        mock_get_pub.assert_not_called()

        # Even if orchestrator is invoked early, it refuses premature dispatch
        publish_unified_post(post.id)
        mock_get_pub.assert_not_called()

    # 5. Duplicate approval/task execution cannot duplicate publishing
    @patch('social_stats.orchestrator.get_publisher')
    def test_05_duplicate_approval_and_task_execution_prevented(self, mock_get_pub):
        mock_pub = MagicMock()
        mock_pub.publish_text.return_value = SimpleNamespace(
            platform_post_id='fb_post_202',
            platform_url='https://facebook.com/202',
            raw_response={'id': 'fb_post_202'},
        )
        mock_get_pub.return_value = mock_pub

        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.agency_owner,
            content='Idempotent post',
            target_platforms=['facebook'],
            status='pending_approval',
        )
        ar = ApprovalRequest.objects.create(
            relation=self.relation,
            client=self.client_managed,
            requested_by=self.agency_owner,
            action_type='publish_post',
            payload={'post_id': post.id},
            target_object_type='UnifiedPost',
            target_object_id=post.id,
        )

        self.api.force_authenticate(user=self.approver)
        with self.captureOnCommitCallbacks(execute=True):
            res1 = self.api.post(f'/api/approvals/{ar.id}/approve/', {}, format='json')
        self.assertEqual(res1.status_code, 200)

        # Second approval attempt rejected
        res2 = self.api.post(f'/api/approvals/{ar.id}/approve/', {}, format='json')
        self.assertEqual(res2.status_code, 400)

        # Duplicate task execution skipped
        publish_unified_post(post.id)
        self.assertEqual(mock_pub.publish_text.call_count, 1)
        self.assertEqual(PlatformPublishLog.objects.filter(unified_post=post, platform='facebook').count(), 1)

    # 6. Material edits invalidate previous approval
    def test_06_material_edit_invalidates_previous_approval(self):
        future_dt = timezone.now() + timedelta(days=1)
        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.editor,
            content='Original approved copy',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=future_dt,
            approved_by=self.approver,
            approved_at=timezone.now(),
        )

        self.api.force_authenticate(user=self.editor)
        res = self.api.patch(
            f'/api/composer/posts/{post.id}/',
            {'content': 'Changed copy after approval'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        post.refresh_from_db()
        self.assertIsNone(post.approved_by_id)
        self.assertIsNone(post.approved_at)
        self.assertEqual(post.status, 'pending_approval')

    # 7. Unauthorized direct approval returns 403
    def test_07_unauthorized_direct_approval_returns_403(self):
        post = UnifiedPost.objects.create(
            client=self.client_managed,
            created_by=self.editor,
            content='Needs approval',
            target_platforms=['facebook'],
            status='pending_approval',
        )

        for unauth_user in (self.viewer, self.editor):
            self.api.force_authenticate(user=unauth_user)
            res = self.api.post(f'/api/composer/posts/{post.id}/approve/', {}, format='json')
            self.assertEqual(res.status_code, 403)

        self.api.force_authenticate(user=self.approver)
        res_ok = self.api.post(f'/api/composer/posts/{post.id}/approve/', {}, format='json')
        self.assertEqual(res_ok.status_code, 200)

    # 8. Viewer and approver cannot modify/delete workspaces; mass assignment blocked
    def test_08_viewer_and_approver_cannot_modify_or_delete_workspace(self):
        for role_user in (self.viewer, self.approver, self.editor):
            self.api.force_authenticate(user=role_user)
            res_patch = self.api.patch(
                f'/api/clients/{self.client_managed.id}/',
                {'company': 'Hijacked Co'},
                format='json',
            )
            self.assertEqual(res_patch.status_code, 403)

            res_del = self.api.delete(f'/api/clients/{self.client_managed.id}/')
            self.assertEqual(res_del.status_code, 403)

        # client_admin can update branding but cannot mass-assign owner_user/subscription_plan
        self.api.force_authenticate(user=self.client_admin)
        res_admin = self.api.patch(
            f'/api/clients/{self.client_managed.id}/',
            {
                'company': 'Alpha Co Updated',
                'owner_user': self.viewer.id,
                'subscription_plan': 'enterprise',
                'ownership_type': 'self_managed',
            },
            format='json',
        )
        self.assertEqual(res_admin.status_code, 200)
        self.client_managed.refresh_from_db()
        self.assertEqual(self.client_managed.company, 'Alpha Co Updated')
        self.assertIsNone(self.client_managed.owner_user_id)
        self.assertEqual(self.client_managed.ownership_type, 'agency_owned')

    # 9. Viewers/approvers cannot mutate posts; editors cannot bypass approvals
    def test_09_viewer_approver_cannot_mutate_posts_and_editor_cannot_bypass(self):
        for readonly_user in (self.viewer, self.approver):
            self.api.force_authenticate(user=readonly_user)
            res = self.api.post(
                '/api/composer/posts/',
                {'content': 'Blocked', 'target_platforms': ['facebook']},
                format='json',
            )
            self.assertEqual(res.status_code, 403)

        # Editor creates post and tries to publish directly without approval
        self.api.force_authenticate(user=self.editor)
        res_create = self.api.post(
            '/api/composer/posts/',
            {'content': 'Editor draft', 'target_platforms': ['facebook']},
            format='json',
        )
        self.assertEqual(res_create.status_code, 201)
        post_id = res_create.data['id']

        res_pub = self.api.post(f'/api/composer/posts/{post_id}/publish_now/', {}, format='json')
        self.assertEqual(res_pub.status_code, 202)
        self.assertEqual(res_pub.data['status'], 'pending_approval')

    # 10. Foreign tenant mutations are rejected
    def test_10_foreign_tenant_mutations_rejected(self):
        foreign_post = UnifiedPost.objects.create(
            client=self.foreign_client,
            created_by=self.foreign_user,
            content='Foreign post',
            target_platforms=['facebook'],
            status='draft',
        )

        self.api.force_authenticate(user=self.agency_owner)
        res_patch = self.api.patch(
            f'/api/composer/posts/{foreign_post.id}/',
            {'content': 'Tampered'},
            format='json',
        )
        self.assertIn(res_patch.status_code, (403, 404))

        res_client = self.api.patch(
            f'/api/clients/{self.foreign_client.id}/',
            {'company': 'Tampered'},
            format='json',
        )
        self.assertIn(res_client.status_code, (403, 404))

    # 11. OAuth start requires authorized authentication
    def test_11_oauth_start_requires_authorized_authentication(self):
        # Unauthenticated -> 401
        self.api.logout()
        res_anon = self.api.get(f'/api/oauth/facebook/start/{self.client_managed.id}/?mode=json')
        self.assertEqual(res_anon.status_code, 401)

        # Viewer, approver, editor, foreign user -> 403
        for denied_user in (self.viewer, self.approver, self.editor, self.foreign_user):
            self.api.force_authenticate(user=denied_user)
            res_fb = self.api.get(f'/api/oauth/facebook/start/{self.client_managed.id}/?mode=json')
            self.assertEqual(res_fb.status_code, 403)
            res_gg = self.api.get(f'/api/oauth/google/start/{self.client_managed.id}/?mode=json')
            self.assertEqual(res_gg.status_code, 403)
            res_li = self.api.get(f'/api/oauth/linkedin/start/{self.client_managed.id}/?mode=json')
            self.assertEqual(res_li.status_code, 403)

        # Authorized agency owner & client_admin -> 200 with auth_url (no JWT in URL)
        for allowed_user in (self.agency_owner, self.client_admin):
            self.api.force_authenticate(user=allowed_user)
            res_ok = self.api.get(f'/api/oauth/facebook/start/{self.client_managed.id}/?mode=json')
            self.assertEqual(res_ok.status_code, 200)
            self.assertIn('auth_url', res_ok.data)
            self.assertIn('facebook.com/dialog/oauth', res_ok.data['auth_url'])
            self.assertNotIn('Bearer', res_ok.data['auth_url'])

    # 12. Invalid/replayed OAuth state rejected; valid state binds to exact client
    @patch('social_stats.oauth_views.requests.get')
    def test_12_oauth_state_integrity_and_replay_protection(self, mock_req_get):
        self.api.force_authenticate(user=self.client_admin)
        res_start = self.api.get(f'/api/oauth/facebook/start/{self.client_managed.id}/?mode=json')
        self.assertEqual(res_start.status_code, 200)
        auth_url = res_start.data['auth_url']
        from urllib.parse import urlparse, parse_qs
        state = parse_qs(urlparse(auth_url).query)['state'][0]

        # Tampered state -> rejected
        res_tamper = self.api.get(f'/api/oauth/facebook/callback/?code=abc&state={state}tampered')
        self.assertEqual(res_tamper.status_code, 302)
        self.assertIn('error=oauth_state_invalid', res_tamper['Location'])

        # Wrong provider callback -> rejected
        res_wrong_prov = self.api.get(f'/api/oauth/linkedin/callback/?code=abc&state={state}')
        self.assertEqual(res_wrong_prov.status_code, 302)
        self.assertIn('error=oauth_state_mismatch', res_wrong_prov['Location'])

        # Mock Facebook Graph API responses for valid callback
        mock_req_get.side_effect = [
            MagicMock(json=lambda: {'access_token': 'short_tok'}),
            MagicMock(json=lambda: {'access_token': 'long_tok', 'expires_in': 5184000}),
            MagicMock(json=lambda: {'data': [{'id': '999', 'name': 'Alpha FB', 'access_token': 'page_tok'}]}),
            MagicMock(json=lambda: {'data': []}),
        ]

        res_valid = self.api.get(f'/api/oauth/facebook/callback/?code=good_code&state={state}')
        self.assertEqual(res_valid.status_code, 302)
        self.assertIn(f'client_id={self.client_managed.id}', res_valid['Location'])

        # Replay of the same state -> rejected
        res_replay = self.api.get(f'/api/oauth/facebook/callback/?code=good_code&state={state}')
        self.assertEqual(res_replay.status_code, 302)
        self.assertIn('error=oauth_state_replayed', res_replay['Location'])

    # 13. Direct owner permissions preserved
    def test_13_direct_owner_permissions_preserved(self):
        self.api.force_authenticate(user=self.direct_owner)
        res_patch = self.api.patch(
            f'/api/clients/{self.direct_client.id}/',
            {'company': 'Direct Co Updated'},
            format='json',
        )
        self.assertEqual(res_patch.status_code, 200)
        res_oauth = self.api.get(f'/api/oauth/facebook/start/{self.direct_client.id}/?mode=json')
        self.assertEqual(res_oauth.status_code, 200)
