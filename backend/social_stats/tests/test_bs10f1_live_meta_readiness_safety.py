from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework.test import APIClient, APITestCase

from social_stats.marketplace_models import ActivityLog, Agency, AgencyClientRelation, AgencyMembership
from social_stats.marketplace_permissions import can_approve_for_client
from social_stats.models import Client, ClientUserRole, PlatformCredential, PlatformPublishLog, UnifiedPost, UserProfile
from social_stats.orchestrator import publish_to_platform, publish_unified_post
from social_stats.scheduler import process_scheduled_posts


class BS10F1PublishingSafetyTests(APITestCase):
    def setUp(self):
        self.agency_owner = User.objects.create_user(
            username='owner_10f1',
            email='owner10f1@test.local',
            password='Password123!',
        )
        self.explicit_approver = User.objects.create_user(
            username='approver_10f1',
            email='approver10f1@test.local',
            password='Password123!',
        )
        self.agency = Agency.objects.create(
            name='Bop Agencia 10F1',
            slug='bop-10f1',
            owner_user=self.agency_owner,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.agency_owner,
            role='owner',
            is_active=True,
        )
        self.client_obj = Client.objects.create(
            name='Bop Client 10F1',
            company='Bop Client 10F1',
            email='client10f1@test.local',
            ownership_type='agency_owned',
            requires_approval=True,
        )
        self.relation = AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_obj,
            status='active',
            permissions={'draft_posts': True, 'schedule_posts': True, 'publish_posts': False},
        )
        UserProfile.objects.create(
            user=self.agency_owner,
            role='client',
            account_type='agency_member',
            client=self.client_obj,
            primary_agency=self.agency,
        )
        UserProfile.objects.create(
            user=self.explicit_approver,
            role='client',
            account_type='end_user',
            client=self.client_obj,
        )
        self.api = APIClient()

    @patch('social_stats.orchestrator.publish_to_platform.delay')
    @patch('social_stats.scheduler.publish_unified_post.delay')
    def test_approved_due_post_blocked_when_publish_posts_false_in_scheduler_and_worker(
        self, mock_sched_delay, mock_plat_delay
    ):
        due_dt = datetime.now(dt_timezone.utc) - timedelta(minutes=2)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.agency_owner,
            title='Approved Due Post',
            content='Must not dispatch while publish_posts=False',
            media_type='text',
            target_platforms=['facebook', 'instagram'],
            status='scheduled',
            scheduled_at=due_dt,
            approved_by=self.agency_owner,
            approved_at=due_dt - timedelta(minutes=10),
        )

        # 1. Scheduler must NOT queue or dispatch when publish_posts=False
        dispatched = process_scheduled_posts()
        self.assertEqual(dispatched, 0)
        mock_sched_delay.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')

        # 2. Worker must NOT dispatch to platforms when publish_posts=False
        publish_unified_post(post.id)
        mock_plat_delay.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')

        # 3. Once publish_posts=True, scheduler dispatches normally
        self.relation.permissions['publish_posts'] = True
        self.relation.save(update_fields=['permissions'])
        dispatched_after = process_scheduled_posts()
        self.assertEqual(dispatched_after, 1)
        mock_sched_delay.assert_called_once_with(post.id)

    def test_explicit_client_approver_role_blocks_agency_bypass_even_if_agency_owned(self):
        # Assign an explicit client-side approver on an agency_owned workspace
        ClientUserRole.objects.create(
            user=self.explicit_approver,
            client=self.client_obj,
            role='approver',
        )
        self.assertTrue(can_approve_for_client(self.explicit_approver, self.client_obj))
        self.assertFalse(can_approve_for_client(self.agency_owner, self.client_obj))

    @patch('social_stats.orchestrator._dispatch_publish')
    def test_per_platform_execution_blocks_when_publish_posts_false(self, mock_dispatch):
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform='facebook',
            access_token='tok_fb',
            is_active=True,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.agency_owner,
            title='Direct Platform Exec',
            content='Must not call _dispatch_publish when publish_posts=False',
            media_type='text',
            target_platforms=['facebook'],
            status='queued',
            scheduled_at=datetime.now(dt_timezone.utc) - timedelta(minutes=1),
            approved_by=self.agency_owner,
            approved_at=datetime.now(dt_timezone.utc) - timedelta(minutes=5),
        )
        publish_to_platform(post.id, 'facebook')
        mock_dispatch.assert_not_called()
        log = PlatformPublishLog.objects.get(unified_post=post, platform='facebook')
        self.assertEqual(log.status, 'failed')
        self.assertEqual(log.error_code, 'permission_denied')

    @patch('social_stats.notification_dispatcher.dispatch')
    def test_self_owned_workspace_permission_management_audited_and_external_foreign_denied(self, _mock_disp):
        # 1. Agency owner CAN toggle publish_posts on own agency_owned workspace, and it is audited
        self.api.force_authenticate(user=self.agency_owner)
        res_on = self.api.put(
            f'/api/relations/{self.relation.id}/permissions/',
            {'permissions': {'publish_posts': True}},
            format='json',
        )
        self.assertEqual(res_on.status_code, 200, res_on.data)
        self.assertTrue(res_on.data['permissions']['publish_posts'])
        self.assertTrue(
            ActivityLog.objects.filter(
                client=self.client_obj,
                action_type='permissions_changed',
                target_object_id=self.relation.id,
            ).exists()
        )

        # 2. Externally managed (end_user_owned) client relation is DENIED (403)
        ext_owner = User.objects.create_user(
            username='ext_owner_10f2', email='ext10f2@test.local', password='Password123!',
        )
        ext_client = Client.objects.create(
            name='External 10F2', company='External 10F2', email='extc10f2@test.local',
            owner_user=ext_owner, ownership_type='end_user_owned',
        )
        ext_rel = AgencyClientRelation.objects.create(
            agency=self.agency, client=ext_client, status='active',
            permissions={'draft_posts': True, 'publish_posts': False},
        )
        res_ext = self.api.put(
            f'/api/relations/{ext_rel.id}/permissions/',
            {'permissions': {'publish_posts': True}},
            format='json',
        )
        self.assertEqual(res_ext.status_code, 403)

        # 3. Foreign tenant is DENIED (403)
        foreign_user = User.objects.create_user(
            username='foreign_10f2', email='foreign10f2@test.local', password='Password123!',
        )
        UserProfile.objects.create(user=foreign_user, role='client', account_type='end_user')
        self.api.force_authenticate(user=foreign_user)
        res_foreign = self.api.put(
            f'/api/relations/{self.relation.id}/permissions/',
            {'permissions': {'publish_posts': False}},
            format='json',
        )
        self.assertEqual(res_foreign.status_code, 403)
