# ============================================================================
#  Social Stats — BS-3G.3B Queued Publication Watchdog Synthetic Test Suite
# ============================================================================
import threading
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import (
    Client, PlatformCredential, PostQueue, QueuedItem, UnifiedPost,
    PlatformPublishLog, UserProfile,
)
from social_stats.scheduler import (
    recover_orphaned_queued_posts, _evaluate_and_recover_post,
    _dispatch_queued_item, process_scheduled_posts,
)

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class QueuedPublicationWatchdogTests(TestCase):
    def setUp(self):
        # Tenant 1: requires_approval = True
        self.client_appr = Client.objects.create(
            name='Tenant Approval Watchdog',
            company='Approval Watchdog Corp',
            email=f'client-appr-{id(self)}@test.com',
            timezone='America/Bogota',
            requires_approval=True,
            is_active=True,
        )
        self.cred_fb1 = PlatformCredential.objects.create(
            client=self.client_appr,
            platform='facebook',
            access_token='mock_fb_token_1',
            page_id='page_appr_123',
            is_active=True,
        )

        # Tenant 2: requires_approval = False
        self.client_no_appr = Client.objects.create(
            name='Tenant No-Approval Watchdog',
            company='No-Approval Watchdog Corp',
            email=f'client-noappr-{id(self)}@test.com',
            timezone='UTC',
            requires_approval=False,
            is_active=True,
        )

        # Tenant 3: Inactive client
        self.client_inactive = Client.objects.create(
            name='Tenant Inactive Watchdog',
            company='Inactive Corp',
            email=f'client-inactive-{id(self)}@test.com',
            timezone='UTC',
            requires_approval=False,
            is_active=False,
        )

        # Users & API Client
        self.user = User.objects.create_user(
            username=f'operator_{id(self)}',
            email=f'operator_{id(self)}@test.com',
            password='testpassword123',
            first_name='Lead',
            last_name='Operator',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            client=self.client_appr,
            role='client',
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # =========================================================================
    # CORE WATCHDOG SAFETY CASES (Scenarios 1-6)
    # =========================================================================

    def test_01_stale_queued_zero_logs_recovered(self):
        """Case 1: Stale queued post (age >= 5m) with zero logs is safely recovered."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Stale post with 0 logs',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=6),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')

    def test_02_fresh_queued_ignored(self):
        """Case 2: Fresh queued post (age < 5m) is ignored by watchdog."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Fresh post',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=2),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')

    def test_03_queued_with_any_platform_publish_log_skipped(self):
        """Case 3: Queued post with an existing pending PlatformPublishLog is skipped."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Post with pending log',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='pending',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

    def test_04_queued_with_success_log_skipped(self):
        """Case 4: Queued post with an existing success log is strictly skipped."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Post with success log',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_123456789',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

    def test_05_queued_with_platform_post_id_skipped(self):
        """Case 5: Queued post with any platform_post_id present is skipped."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Post with platform id',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
            platform_post_id='fb_ambiguous_999',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

    def test_06_inactive_client_skipped(self):
        """Case 6: Post belonging to an inactive client is skipped."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_inactive,
            content='Post for inactive tenant',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')

    # =========================================================================
    # APPROVAL GOVERNANCE (Scenarios 7-9)
    # =========================================================================

    def test_07_approval_required_missing_approved_by_transitions_pending_approval(self):
        """Case 7: Post requiring approval missing approved_by is reverted to pending_approval."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Unapproved post missing user',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
            approved_by=None,
            approved_at=now - timedelta(minutes=10),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay, \
             patch('social_stats.notification_watchers.notify_approver_for_post.delay') as mock_notify:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()
            mock_notify.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

    def test_08_approval_required_missing_approved_at_transitions_pending_approval(self):
        """Case 8: Post requiring approval missing approved_at is reverted to pending_approval."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Unapproved post missing timestamp',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
            approved_by=self.user,
            approved_at=None,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay, \
             patch('social_stats.notification_watchers.notify_approver_for_post.delay') as mock_notify:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()
            mock_notify.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

    def test_09_approved_stale_queued_recovered(self):
        """Case 9: Duly approved stale queued post on approval-requiring tenant is recovered."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Approved stale post',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
            approved_by=self.user,
            approved_at=now - timedelta(minutes=10),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post.id)

    # =========================================================================
    # NON-QUEUED STATES NEVER AUTO-RECOVERED (Scenarios 10-12)
    # =========================================================================

    def test_10_publishing_post_never_auto_recovered(self):
        """Case 10: Post in status='publishing' is never auto-recovered by watchdog."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Publishing in flight',
            target_platforms=['facebook'],
            status='publishing',
            queued_at=now - timedelta(minutes=20),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'publishing')

    def test_11_failed_post_never_auto_recovered(self):
        """Case 11: Post in status='failed' is never auto-recovered by watchdog."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Failed post',
            target_platforms=['facebook'],
            status='failed',
            queued_at=now - timedelta(minutes=20),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'failed')

    def test_12_published_post_never_auto_recovered(self):
        """Case 12: Post in status='published' is never auto-recovered by watchdog."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Published post',
            target_platforms=['facebook'],
            status='published',
            published_at=now - timedelta(minutes=20),
            queued_at=now - timedelta(minutes=25),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'published')

    # =========================================================================
    # CONCURRENCY & BROKER FAILURE (Scenarios 13-14)
    # =========================================================================

    def test_13_concurrent_watchdogs_one_dispatch_only(self):
        """Case 13: Overlapping watchdog evaluations dispatch exactly once using row locking."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Concurrent recovery test',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )

        dispatches = []

        def fake_delay(pid):
            dispatches.append(pid)

        # First evaluation acquires lock and redispatches
        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=fake_delay):
            dec1 = _evaluate_and_recover_post(post.id, now, now - timedelta(seconds=300), 300)
            self.assertEqual(dec1, 'RECOVERED')

            # Simulate concurrent worker attempting while row status or lock changed
            # In test, we change status to simulate that first worker published it
            post.status = 'publishing'
            post.save(update_fields=['status'])

            dec2 = _evaluate_and_recover_post(post.id, now, now - timedelta(seconds=300), 300)
            self.assertEqual(dec2, 'SKIPPED_LOCKED')

        self.assertEqual(len(dispatches), 1)

    def test_14_broker_failure_during_recovery_leaves_post_safely_recoverable(self):
        """Case 14: Broker failure during recovery leaves post in queued state for next cycle."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Broker down during watchdog',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=RuntimeError('Broker connection lost')):
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 0)

        # Post is preserved in queued status, not destroyed or marked failed
        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')
        self.assertEqual(post.publish_logs.count(), 0)

    # =========================================================================
    # ORIGIN & TRACEABILITY PRESERVATION (Scenarios 15-16)
    # =========================================================================

    def test_15_postqueue_origin_post_original_queued_item_remains_used_and_untouched(self):
        """Case 15: PostQueue-origin orphan is recovered without rematerializing QueuedItem."""
        queue = PostQueue.objects.create(
            client=self.client_no_appr,
            name='Watchdog Queue Pilot',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=10),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Queue item content',
            status='waiting',
        )

        # Simulate broker failure during original queue dispatch
        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=RuntimeError('Broker fail')):
            post = _dispatch_queued_item(queue, item, timezone.now() - timedelta(minutes=8))

        item.refresh_from_db()
        self.assertEqual(item.status, 'used')
        self.assertEqual(item.unified_post, post)

        initial_post_count = UnifiedPost.objects.count()
        initial_item_count = QueuedItem.objects.count()

        # Watchdog runs
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post.id)

        # DB integrity: zero new posts, item remains used and linked
        self.assertEqual(UnifiedPost.objects.count(), initial_post_count)
        self.assertEqual(QueuedItem.objects.count(), initial_item_count)
        item.refresh_from_db()
        self.assertEqual(item.status, 'used')
        self.assertEqual(item.unified_post, post)
        post.refresh_from_db()
        self.assertEqual(post.source_queue, queue)
        self.assertEqual(post.source_queued_item, item)

    def test_16_scheduled_origin_post_no_duplicate_unified_post_created(self):
        """Case 16: Scheduled-origin orphan is recovered on existing row, preserving scheduled_at."""
        target_sched_at = timezone.now() - timedelta(minutes=15)
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Scheduled orphan',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=target_sched_at,
        )

        initial_count = UnifiedPost.objects.count()

        # Scheduled task runs with broker down
        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=RuntimeError('Broker fail')):
            process_scheduled_posts()

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')
        self.assertIsNotNone(post.queued_at)

        # Stale orphan age passes grace period
        post.queued_at = timezone.now() - timedelta(minutes=10)
        post.save(update_fields=['queued_at'])

        # Watchdog recovers
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post.id)

        self.assertEqual(UnifiedPost.objects.count(), initial_count)
        post.refresh_from_db()
        self.assertEqual(post.scheduled_at, target_sched_at)

    # =========================================================================
    # QUEUED_AT AUDIT ACROSS ALL 4 PATHS (Scenario 17)
    # =========================================================================

    def test_17_queued_at_correctly_written_by_all_four_paths(self):
        """Case 17: queued_at is explicitly populated by all 4 queue-transition paths."""
        now = timezone.now()

        # Path 1: PostQueue _dispatch_queued_item
        queue = PostQueue.objects.create(
            client=self.client_no_appr,
            name='Path 1 Queue',
            platforms=['facebook'],
            schedule_rule='* * * * *',
        )
        item = QueuedItem.objects.create(queue=queue, content='Path 1 Item', status='waiting')
        with patch('social_stats.scheduler.publish_unified_post.delay'):
            post1 = _dispatch_queued_item(queue, item, now)
        self.assertIsNotNone(post1.queued_at)
        self.assertEqual(post1.queued_at, now)

        # Path 2: Scheduled publishing process_scheduled_posts
        post2 = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Path 2 Post',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=now - timedelta(minutes=2),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_scheduled_posts()
        post2.refresh_from_db()
        self.assertEqual(post2.status, 'queued')
        self.assertIsNotNone(post2.queued_at)

        # Path 3: Composer publish_now
        post3 = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Path 3 Post',
            target_platforms=['facebook'],
            status='draft',
            approved_by=self.user,
            approved_at=now,
        )
        with patch('social_stats.orchestrator.publish_unified_post.delay'):
            resp = self.api.post(f'/api/composer/posts/{post3.id}/publish_now/')
            self.assertEqual(resp.status_code, 200)
        post3.refresh_from_db()
        self.assertEqual(post3.status, 'queued')
        self.assertIsNotNone(post3.queued_at)

        # Path 4: Composer approve (immediate approval)
        post4 = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Path 4 Post',
            target_platforms=['facebook'],
            status='pending_approval',
            scheduled_at=now - timedelta(minutes=1), # past/immediate
        )
        with patch('social_stats.orchestrator.publish_unified_post.delay'):
            resp = self.api.post(f'/api/composer/posts/{post4.id}/approve/')
            self.assertEqual(resp.status_code, 200)
        post4.refresh_from_db()
        self.assertEqual(post4.status, 'queued')
        self.assertIsNotNone(post4.queued_at)

    # =========================================================================
    # FALLBACK AGE LOGIC & TENANT ISOLATION (Scenarios 18-20)
    # =========================================================================

    def test_18_fallback_age_logic_works_for_legacy_queued_at_null_rows(self):
        """Case 18: Fallback COALESCE(queued_at, scheduled_at, created_at) safely handles NULL queued_at."""
        now = timezone.now()

        # Legacy row A: queued_at is None, scheduled_at is 10 min ago
        post_a = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Legacy post A with scheduled_at',
            target_platforms=['facebook'],
            status='queued',
            scheduled_at=now - timedelta(minutes=10),
            queued_at=None,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post_a.id)

        # Legacy row B: queued_at is None, scheduled_at is None, created_at is 10 min ago
        post_b = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Legacy post B with created_at only',
            target_platforms=['facebook'],
            status='queued',
            scheduled_at=None,
            queued_at=None,
        )
        # Update created_at in DB
        UnifiedPost.objects.filter(id=post_b.id).update(created_at=now - timedelta(minutes=10))

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            # Both post_a (already recovered but in mock still queued) and post_b
            self.assertIn(post_b.id, [call.args[0] for call in mock_delay.call_args_list])

    def test_19_inactive_deleted_tenant_isolation(self):
        """Case 19: Inactive client posts are strictly isolated and never recovered."""
        now = timezone.now()
        post_inactive = UnifiedPost.objects.create(
            client=self.client_inactive,
            content='Inactive tenant orphan',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )
        post_active = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Active tenant orphan',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 1)
            mock_delay.assert_called_once_with(post_active.id)

        post_inactive.refresh_from_db()
        self.assertEqual(post_inactive.status, 'queued')

    def test_20_watchdog_cannot_cross_tenant_boundaries(self):
        """Case 20: Watchdog dispatches maintain strict tenant isolation and post ID binding."""
        now = timezone.now()
        post1 = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Tenant 1 approved orphan',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
            approved_by=self.user,
            approved_at=now - timedelta(minutes=10),
        )
        post2 = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Tenant 2 orphan',
            target_platforms=['facebook'],
            status='queued',
            queued_at=now - timedelta(minutes=10),
        )

        dispatched_ids = []
        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=lambda pid: dispatched_ids.append(pid)):
            recovered = recover_orphaned_queued_posts(grace_seconds=300)
            self.assertEqual(recovered, 2)

        self.assertEqual(set(dispatched_ids), {post1.id, post2.id})
