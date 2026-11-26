import io
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats import media_service
from social_stats.marketplace_models import (
    ActivityLog,
    Agency,
    AgencyClientRelation,
    AgencyMembership,
)
from social_stats.models import Client, UnifiedPost, UserProfile


def _make_png(name='approval.png'):
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), color=(10, 90, 180)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class BS10E4ApprovalWorkflowTests(APITestCase):
    def setUp(self):
        self.agency_owner = User.objects.create_user(
            username='bop_agency_owner_10e4',
            email='bopagencia10e4@test.local',
            password='Password123!',
        )
        self.pilot_user = User.objects.create_user(
            username='pilot_10e4',
            email='pilot10e4@test.local',
            password='Password123!',
        )
        self.external_owner = User.objects.create_user(
            username='external_10e4',
            email='external10e4@test.local',
            password='Password123!',
        )
        self.foreign_user = User.objects.create_user(
            username='foreign_10e4',
            email='foreign10e4@test.local',
            password='Password123!',
        )

        self.agency = Agency.objects.create(
            name='Bop Agencia',
            slug='bop-agencia-10e4',
            owner_user=self.agency_owner,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.agency_owner,
            role='owner',
            is_active=True,
        )

        # Agency-owned workspace with technical pilot user as owner_user
        self.self_client = Client.objects.create(
            name='Bop Agencia',
            company='Bop Agencia',
            email='self10e4@test.local',
            owner_user=self.pilot_user,
            ownership_type='agency_owned',
            requires_approval=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.self_client,
            status='active',
            permissions={'draft_posts': True, 'schedule_posts': True, 'publish_posts': False},
        )
        UserProfile.objects.create(
            user=self.agency_owner,
            role='client',
            account_type='agency_member',
            client=self.self_client,
            primary_agency=self.agency,
        )
        UserProfile.objects.create(
            user=self.pilot_user,
            role='client',
            account_type='end_user',
            client=self.self_client,
        )

        # Externally managed client (end_user_owned with external owner_user)
        self.external_client = Client.objects.create(
            name='External Client',
            company='External Client',
            email='ext10e4@test.local',
            owner_user=self.external_owner,
            ownership_type='end_user_owned',
            requires_approval=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.external_client,
            status='active',
            permissions={'draft_posts': True, 'schedule_posts': True, 'publish_posts': False},
        )
        UserProfile.objects.create(
            user=self.external_owner,
            role='client',
            account_type='end_user',
            client=self.external_client,
        )

        # Unrelated foreign tenant
        self.foreign_client = Client.objects.create(
            name='Foreign Client',
            company='Foreign Client',
            email='foreign10e4@test.local',
            owner_user=self.foreign_user,
            ownership_type='end_user_owned',
        )
        UserProfile.objects.create(
            user=self.foreign_user,
            role='client',
            account_type='end_user',
            client=self.foreign_client,
        )

        self.api = APIClient()

    @patch('social_stats.composer_views.publish_unified_post.delay')
    def test_self_owned_workspace_approval_queue_approve_audit_and_invalidation(self, mock_delay):
        future_dt = datetime(2026, 11, 27, 15, 0, tzinfo=dt_timezone.utc)
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png(),
                    client_id=self.self_client.id,
                    uploaded_by_id=self.agency_owner.id,
                )
                post = UnifiedPost.objects.create(
                    client=self.self_client,
                    created_by=self.agency_owner,
                    title='BOP-001',
                    content='Commercial pending approval',
                    media_type='image',
                    media_urls=[f'asset:{asset.id}'],
                    target_platforms=['facebook', 'instagram'],
                    status='pending_approval',
                    scheduled_at=future_dt,
                )

                self.api.force_authenticate(user=self.agency_owner)

                # 1. /api/auth/me/ grants composer.approve for self-owned workspace
                me_res = self.api.get('/api/auth/me/')
                self.assertEqual(me_res.status_code, 200)
                self.assertTrue(me_res.data['permissions'].get('composer.approve'))

                # 2. /api/dashboard/counts/ reflects pending_approval post
                counts_res = self.api.get('/api/dashboard/counts/', {'client_id': self.self_client.id})
                self.assertEqual(counts_res.status_code, 200)
                self.assertEqual(counts_res.data['pending_approvals'], 1)

                # 3. /api/composer/approvals/ shows post with platforms and signed thumbnail_url
                q_res = self.api.get('/api/composer/approvals/', {'client_id': self.self_client.id})
                self.assertEqual(q_res.status_code, 200)
                self.assertEqual(q_res.data['count'], 1)
                q_item = q_res.data['queue'][0]
                self.assertEqual(q_item['id'], post.id)
                self.assertEqual(q_item['target_platforms'], ['facebook', 'instagram'])
                self.assertIn(f'/api/media/serve/{asset.id}/', q_item['thumbnail_url'])
                self.assertIn('token=', q_item['thumbnail_url'])

                # 4. Approve preserves scheduled_at, does not publish prematurely, and logs audit
                app_res = self.api.post(
                    f'/api/composer/posts/{post.id}/approve/',
                    {},
                    format='json',
                    HTTP_X_CLIENT_ID=str(self.self_client.id),
                )
                self.assertEqual(app_res.status_code, 200, app_res.data)
                post.refresh_from_db()
                self.assertEqual(post.status, 'scheduled')
                self.assertEqual(post.scheduled_at, future_dt)
                self.assertEqual(post.approved_by_id, self.agency_owner.id)
                mock_delay.assert_not_called()
                self.assertTrue(
                    ActivityLog.objects.filter(
                        client=self.self_client,
                        action_type='post_approved',
                        target_object_id=post.id,
                    ).exists()
                )

                # 5. Editing approved content invalidates approval
                edit_res = self.api.patch(
                    f'/api/composer/posts/{post.id}/',
                    {'content': 'Edited after approval'},
                    format='json',
                    HTTP_X_CLIENT_ID=str(self.self_client.id),
                )
                self.assertEqual(edit_res.status_code, 200, edit_res.data)
                post.refresh_from_db()
                self.assertIsNone(post.approved_by_id)
                self.assertEqual(post.status, 'pending_approval')

                # 6. Reject (cancel) transitions to cancelled and logs audit
                rej_res = self.api.post(
                    f'/api/composer/posts/{post.id}/cancel/',
                    {},
                    format='json',
                    HTTP_X_CLIENT_ID=str(self.self_client.id),
                )
                self.assertEqual(rej_res.status_code, 200)
                post.refresh_from_db()
                self.assertEqual(post.status, 'cancelled')
                self.assertTrue(
                    ActivityLog.objects.filter(
                        client=self.self_client,
                        action_type='post_rejected',
                        target_object_id=post.id,
                    ).exists()
                )

    def test_external_client_approval_restricted_and_foreign_tenant_denied(self):
        ext_post = UnifiedPost.objects.create(
            client=self.external_client,
            created_by=self.agency_owner,
            title='External Post',
            content='Needs client approval',
            media_type='text',
            target_platforms=['facebook'],
            status='pending_approval',
            scheduled_at=datetime.now(dt_timezone.utc) + timedelta(days=2),
        )

        # Agency owner CANNOT approve externally owned client's post
        self.api.force_authenticate(user=self.agency_owner)
        res_agency = self.api.post(
            f'/api/composer/posts/{ext_post.id}/approve/',
            {},
            format='json',
            HTTP_X_CLIENT_ID=str(self.external_client.id),
        )
        self.assertEqual(res_agency.status_code, 403)

        # Foreign tenant CANNOT view or approve
        self.api.force_authenticate(user=self.foreign_user)
        res_foreign_q = self.api.get('/api/composer/approvals/', {'client_id': self.self_client.id})
        self.assertEqual(res_foreign_q.status_code, 403)
        res_foreign_app = self.api.post(
            f'/api/composer/posts/{ext_post.id}/approve/',
            {},
            format='json',
        )
        self.assertIn(res_foreign_app.status_code, (403, 404))

        # External client owner CAN approve their own post
        self.api.force_authenticate(user=self.external_owner)
        res_ext_owner = self.api.post(
            f'/api/composer/posts/{ext_post.id}/approve/',
            {},
            format='json',
            HTTP_X_CLIENT_ID=str(self.external_client.id),
        )
        self.assertEqual(res_ext_owner.status_code, 200)
        ext_post.refresh_from_db()
        self.assertEqual(ext_post.status, 'scheduled')

        # Inactive agency relation is rejected even on agency_owned workspace
        inactive_client = Client.objects.create(
            name='Inactive Rel',
            company='Inactive Rel',
            email='inactiverel10e4@test.local',
            ownership_type='agency_owned',
            requires_approval=True,
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=inactive_client,
            status='paused',
            permissions={'draft_posts': True},
        )
        inactive_post = UnifiedPost.objects.create(
            client=inactive_client,
            created_by=self.agency_owner,
            title='Inactive Rel Post',
            content='Should not approve',
            media_type='text',
            target_platforms=['facebook'],
            status='pending_approval',
        )
        self.api.force_authenticate(user=self.agency_owner)
        res_inactive = self.api.post(
            f'/api/composer/posts/{inactive_post.id}/approve/',
            {},
            format='json',
            HTTP_X_CLIENT_ID=str(inactive_client.id),
        )
        self.assertIn(res_inactive.status_code, (403, 404))

    @patch('social_stats.orchestrator.publish_to_platform.delay')
    @patch('social_stats.scheduler.publish_unified_post.delay')
    def test_publishing_safety_respects_publish_posts_false_and_approval_gate(self, mock_sched_delay, mock_plat_delay):
        from social_stats.orchestrator import publish_unified_post
        from social_stats.scheduler import process_scheduled_posts

        future_dt = datetime.now(dt_timezone.utc) + timedelta(days=1)
        post = UnifiedPost.objects.create(
            client=self.self_client,
            created_by=self.agency_owner,
            title='Safety Post',
            content='Must not publish prematurely',
            media_type='text',
            target_platforms=['facebook', 'instagram'],
            status='pending_approval',
            scheduled_at=future_dt,
        )

        # Agency user with publish_posts=False is denied on publish_now
        self.api.force_authenticate(user=self.agency_owner)
        res_pub = self.api.post(
            f'/api/composer/posts/{post.id}/publish_now/',
            {},
            format='json',
            HTTP_X_CLIENT_ID=str(self.self_client.id),
        )
        self.assertEqual(res_pub.status_code, 403)

        # Even if status were 'scheduled' without approved_by, scheduler & orchestrator block dispatch
        UnifiedPost.objects.filter(pk=post.id).update(
            status='scheduled',
            scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5),
            approved_by=None,
        )
        process_scheduled_posts()
        mock_sched_delay.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

        publish_unified_post(post.id)
        mock_plat_delay.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

        # Approved future post is not dispatched prematurely by orchestrator
        UnifiedPost.objects.filter(pk=post.id).update(
            status='scheduled',
            scheduled_at=future_dt,
            approved_by=self.agency_owner,
        )
        publish_unified_post(post.id)
        mock_plat_delay.assert_not_called()
