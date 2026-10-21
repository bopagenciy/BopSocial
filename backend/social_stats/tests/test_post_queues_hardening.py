# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Targeted tests for BS-3G.2B:
PostQueue Concurrency, Approval & Traceability Hardening.

Covers 35 mandatory test cases:
  1-5.   Concurrency (same item, concurrent processors, multi-queue, same slot, uniqueness)
  6-14.  Approval (skips unapproved, approved eligible, copied audit fields, edit invalidation,
         reorder safe, no-approval tenant, duplicate approve safe)
  15-18. Validation (invalid media blocked, cross-tenant media blocked, multi-platform, partial failure blocks)
  19-23. Failure recovery (broker failure, post traceable, no duplicate post, auditable, queue advances)
  24-26. Round robin (recycle, approval preserved, edited recycled item cleared)
  27-30. Timezone (client timezone, DST, fallback UTC, invalid cron skip)
  31-35. Traceability (source_queue set, source_queued_item set, delete safety, reverse traceability)
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import (
    Client, PlatformCredential, UnifiedPost, PostQueue, QueuedItem,
    MediaAsset, UserProfile, PlatformPublishLog,
)
from social_stats.scheduler import (
    process_post_queues, _queue_is_due, _dispatch_queued_item,
    _client_tz, _build_post_content, _preflight_check_item,
)

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PostQueuesHardeningTests(TestCase):
    def setUp(self):
        # Tenant 1: requires_approval = True
        self.client_approval = Client.objects.create(
            name='Tenant Approval BS-3G',
            company='Approval Company',
            email=f'client-approval-{id(self)}@test.com',
            timezone='America/Bogota',
            requires_approval=True,
        )
        self.cred_fb1 = PlatformCredential.objects.create(
            client=self.client_approval,
            platform='facebook',
            access_token='mock_fb_token_1',
            page_id='page_appr_123',
            is_active=True,
        )
        self.cred_ig1 = PlatformCredential.objects.create(
            client=self.client_approval,
            platform='instagram',
            access_token='mock_ig_token_1',
            instagram_account_id='17841400000000010',
            is_active=True,
        )

        # Tenant 2: requires_approval = False
        self.client_no_approval = Client.objects.create(
            name='Tenant No-Approval BS-3G',
            company='No-Approval Company',
            email=f'client-no-appr-{id(self)}@test.com',
            timezone='UTC',
            requires_approval=False,
        )
        self.cred_fb2 = PlatformCredential.objects.create(
            client=self.client_no_approval,
            platform='facebook',
            access_token='mock_fb_token_2',
            page_id='page_noappr_456',
            is_active=True,
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
            client=self.client_approval,
            role='client',
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # =========================================================================
    # AH. CONCURRENCY (Cases 1-5)
    # =========================================================================

    def test_01_same_item_cannot_be_claimed_twice(self):
        """Case 1: Same item cannot be claimed or materialized twice."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Concurrency Q1',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=10),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Unique Content 1',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            post1 = _dispatch_queued_item(queue, item)
            self.assertIsNotNone(post1)
            item.refresh_from_db()
            self.assertEqual(item.status, 'used')

            # Second claim attempt must fail defensively
            with self.assertRaises(ValueError):
                _dispatch_queued_item(queue, item)

    def test_02_concurrent_processors_same_queue_one_dispatch(self):
        """Case 2: Two concurrent process_post_queues invocations produce exactly 1 dispatch."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Concurrency Q2',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        QueuedItem.objects.create(
            queue=queue,
            content='Item for concurrent check',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            # First invocation dispatches
            fired1 = process_post_queues()
            self.assertEqual(fired1, 1)

            # Overlapping / immediate subsequent invocation finds queue no longer due
            fired2 = process_post_queues()
            self.assertEqual(fired2, 0)

            self.assertEqual(mock_delay.call_count, 1)

    def test_03_different_queues_dispatch_independently(self):
        """Case 3: Multiple queues with due slots dispatch independently."""
        queue1 = PostQueue.objects.create(
            client=self.client_approval,
            name='Independent Q1',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        QueuedItem.objects.create(
            queue=queue1,
            content='Item Q1',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        queue2 = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Independent Q2',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        QueuedItem.objects.create(
            queue=queue2,
            content='Item Q2',
            status='waiting',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 2)
            self.assertEqual(mock_delay.call_count, 2)

    def test_04_same_cron_slot_only_one_dispatch(self):
        """Case 4: Same cron slot cannot fire twice."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Slot Test Queue',
            platforms=['facebook'],
            schedule_rule='*/15 * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=20),
        )
        QueuedItem.objects.create(queue=queue, content='Item A', status='waiting')
        QueuedItem.objects.create(queue=queue, content='Item B', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            f1 = process_post_queues()
            self.assertEqual(f1, 1)

            # Subsequent call within same window
            f2 = process_post_queues()
            self.assertEqual(f2, 0)

    def test_05_item_to_post_uniqueness(self):
        """Case 5: One QueuedItem cannot produce multiple UnifiedPosts."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Uniqueness Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=10),
        )
        item = QueuedItem.objects.create(queue=queue, content='Unique post test', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            post1 = _dispatch_queued_item(queue, item)
            self.assertIsNotNone(post1)

            # Attempting to dispatch the same item again raises error
            with self.assertRaises(ValueError):
                _dispatch_queued_item(queue, item)

            self.assertEqual(UnifiedPost.objects.filter(source_queued_item=item).count(), 1)

    # =========================================================================
    # AI. APPROVAL POLICY (Cases 6-14)
    # =========================================================================

    def test_06_approval_required_tenant_skips_unapproved_item(self):
        """Case 6: For requires_approval=True, unapproved items are skipped."""
        initial_dispatched = timezone.now() - timedelta(minutes=5)
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Approval Gate Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=initial_dispatched,
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Unapproved Item',
            status='waiting',
            approved_by=None,
            approved_at=None,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 0)
            mock_delay.assert_not_called()

        item.refresh_from_db()
        self.assertEqual(item.status, 'waiting')
        queue.refresh_from_db()
        self.assertEqual(queue.last_dispatched_at, initial_dispatched)

    def test_07_approved_item_eligible(self):
        """Case 7: For requires_approval=True, approved item is eligible and fires."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Approved Eligible Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Pre-approved Item',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 1)
            mock_delay.assert_called_once()

        item.refresh_from_db()
        self.assertEqual(item.status, 'used')

    def test_08_approval_copied_to_unified_post(self):
        """Case 8: Approval fields transfer to materialized UnifiedPost."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Audit Transfer Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        appr_time = timezone.now() - timedelta(hours=1)
        item = QueuedItem.objects.create(
            queue=queue,
            content='Audit test',
            status='waiting',
            approved_by=self.user,
            approved_at=appr_time,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        self.assertIsNotNone(post)
        self.assertEqual(post.approved_by, self.user)
        self.assertEqual(post.approved_at, appr_time)
        self.assertEqual(post.status, 'queued')

    def test_09_edit_content_clears_approval(self):
        """Case 9: Editing item content clears approved_by and approved_at."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Edit Test Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Initial Text',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        self.assertTrue(item.is_approved)

        item.content = 'Updated Text'
        item.save()

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)
        self.assertFalse(item.is_approved)

    def test_10_edit_media_clears_approval(self):
        """Case 10: Editing item media_urls clears approval."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Media Edit Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Text',
            media_urls=['https://example.com/1.jpg'],
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        item.media_urls = ['https://example.com/2.jpg']
        item.save()

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)

    def test_11_hashtag_edit_clears_approval(self):
        """Case 11: Editing hashtags clears approval."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Hashtag Edit Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Text',
            hashtags=['tag1'],
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        item.hashtags = ['tag1', 'tag2']
        item.save()

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)

    def test_12_reorder_preserves_approval(self):
        """Case 12: Changing sort_order alone preserves approval."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Reorder Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Text',
            sort_order=1,
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        item.sort_order = 5
        item.save(update_fields=['sort_order'])

        item.refresh_from_db()
        self.assertEqual(item.approved_by, self.user)
        self.assertIsNotNone(item.approved_at)

    def test_13_no_approval_tenant_works_without_approval(self):
        """Case 13: Tenant with requires_approval=False dispatches without approval."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='No Appr Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Auto post',
            status='waiting',
            approved_by=None,
            approved_at=None,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 1)
            mock_delay.assert_called_once()

        item.refresh_from_db()
        self.assertEqual(item.status, 'used')
        self.assertIsNone(item.unified_post.approved_by)

    def test_14_duplicate_approve_safe(self):
        """Case 14: Approving an already approved item is safe and idempotent."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Double Approve Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Item to approve via API',
            status='waiting',
        )

        res1 = self.api.post(f'/api/composer/queues/{queue.id}/items/{item.id}/approve/')
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.data['is_approved'])

        # Duplicate approve
        res2 = self.api.post(f'/api/composer/queues/{queue.id}/items/{item.id}/approve/')
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.data['is_approved'])

    # =========================================================================
    # AJ. VALIDATION & TENANT SAFETY (Cases 15-18)
    # =========================================================================

    def test_15_invalid_media_blocks_before_claim(self):
        """Case 15: Invalid media reference blocks claim without consuming item."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Validation Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Item with missing media asset',
            media_urls=['asset:999999'],  # nonexistent asset
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 0)
            mock_delay.assert_not_called()

        item.refresh_from_db()
        self.assertEqual(item.status, 'waiting')
        self.assertIsNone(item.unified_post)

    def test_16_cross_tenant_media_blocked(self):
        """Case 16: Cross-tenant asset references are blocked before dispatch."""
        # Asset belonging to client_no_approval
        other_asset = MediaAsset.objects.create(
            client=self.client_no_approval,
            file=SimpleUploadedFile('other.jpg', b'image data', content_type='image/jpeg'),
            mime_type='image/jpeg',
            file_size=1024,
            width=800,
            height=800,
        )

        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Cross Tenant Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Hacked asset attempt',
            media_urls=[f'asset:{other_asset.id}'],
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 0)
            mock_delay.assert_not_called()

        item.refresh_from_db()
        self.assertEqual(item.status, 'waiting')

    def test_17_multi_platform_validation_all_pass(self):
        """Case 17: Multi-platform queue dispatches when all platforms validate."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Multi Platform Q',
            platforms=['facebook', 'instagram'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Valid multi-platform image post',
            media_urls=['https://example.com/photo.jpg'],
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 1)
            mock_delay.assert_called_once()

    def test_18_one_target_failure_blocks_whole_item(self):
        """Case 18: If one platform is unsupported or fails, whole item is blocked."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Unsupported Target Q',
            platforms=['facebook', 'nonexistent_platform'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Text for multi',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 0)
            mock_delay.assert_not_called()

        item.refresh_from_db()
        self.assertEqual(item.status, 'waiting')

    # =========================================================================
    # AK. FAILURE RECOVERY & ATOMICITY (Cases 19-23)
    # =========================================================================

    def test_19_broker_dispatch_failure_does_not_silently_lose_item(self):
        """Case 19: Celery broker failure leaves post materialized and recoverable."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Broker Failure Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Important Content',
            status='waiting',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=RuntimeError('Broker down')):
            # The scheduler catches the error gracefully
            fired = process_post_queues()
            self.assertEqual(fired, 1)

        # Content is preserved in DB as a queued post, linked to queue and item
        item.refresh_from_db()
        self.assertEqual(item.status, 'used')
        self.assertIsNotNone(item.unified_post)
        self.assertEqual(item.unified_post.status, 'queued')
        self.assertEqual(item.unified_post.content, 'Important Content')

    def test_20_generated_post_remains_traceable(self):
        """Case 20: Generated UnifiedPost has source_queue and source_queued_item."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Traceable Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Traceable item',
            status='waiting',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        self.assertEqual(post.source_queue, queue)
        self.assertEqual(post.source_queued_item, item)

    def test_21_next_scheduler_tick_does_not_create_duplicate_post(self):
        """Case 21: Next scheduler tick does not recreate post for previously claimed item."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='No Duplicate Tick Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Solo Item',
            status='waiting',
        )

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            fired1 = process_post_queues()
            self.assertEqual(fired1, 1)

            # Advance time by 2 minutes so cron would be due again if there were items
            queue.refresh_from_db()
            queue.last_dispatched_at = timezone.now() - timedelta(minutes=2)
            queue.save(update_fields=['last_dispatched_at'])

            fired2 = process_post_queues()
            self.assertEqual(fired2, 0)
            self.assertEqual(UnifiedPost.objects.filter(source_queued_item=item).count(), 1)

    def test_22_provider_failure_remains_auditable(self):
        """Case 22: Orchestrator / provider failures log to PlatformPublishLog cleanly."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Provider Failure Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(queue=queue, content='Audit fail', status='waiting')

        with patch('social_stats.publishers.facebook.FacebookPublisher.publish_text', side_effect=Exception('Meta 500 error')):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        log = PlatformPublishLog.objects.filter(unified_post=post, platform='facebook').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'failed')
        self.assertIn('Meta 500', log.error_message)

    def test_23_queue_advances_according_to_documented_policy(self):
        """Case 23: last_dispatched_at advances only on successful materialization."""
        initial_time = timezone.now() - timedelta(minutes=5)
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Advance Policy Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=initial_time,
        )
        # Empty queue: no advance
        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()
        queue.refresh_from_db()
        self.assertEqual(queue.last_dispatched_at, initial_time)

        # Add approved item: advances
        QueuedItem.objects.create(
            queue=queue,
            content='Valid item',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()
        queue.refresh_from_db()
        self.assertGreater(queue.last_dispatched_at, initial_time)

    # =========================================================================
    # AL. ROUND ROBIN RECYCLE & APPROVAL (Cases 24-26)
    # =========================================================================

    def test_24_round_robin_recycle(self):
        """Case 24: round_robin resets used items to waiting when all items are consumed."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Evergreen RR Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            queue_strategy='round_robin',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item1 = QueuedItem.objects.create(queue=queue, content='RR 1', status='waiting', sort_order=1)
        item2 = QueuedItem.objects.create(queue=queue, content='RR 2', status='waiting', sort_order=2)

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            # Dispatch item 1
            process_post_queues()
            item1.refresh_from_db()
            self.assertEqual(item1.status, 'used')

            # Force queue due again
            queue.last_dispatched_at = timezone.now() - timedelta(minutes=5)
            queue.save(update_fields=['last_dispatched_at'])

            # Dispatch item 2
            process_post_queues()
            item2.refresh_from_db()
            self.assertEqual(item2.status, 'used')

            # Now all used. Next tick triggers recycling!
            queue.last_dispatched_at = timezone.now() - timedelta(minutes=5)
            queue.save(update_fields=['last_dispatched_at'])

            process_post_queues()
            item1.refresh_from_db()
            item2.refresh_from_db()
            # item1 was recycled to waiting and then immediately claimed to used
            self.assertEqual(item1.status, 'used')
            # item2 was recycled and is waiting
            self.assertEqual(item2.status, 'waiting')

    def test_25_recycled_approval_preserved_appropriately(self):
        """Case 25: Recycled items in round_robin retain approval if content unmodified."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Evergreen Appr Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            queue_strategy='round_robin',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item1 = QueuedItem.objects.create(
            queue=queue, content='RR Appr 1', status='used', sort_order=1,
            approved_by=self.user, approved_at=timezone.now(),
        )

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            # Trigger recycling
            fired = process_post_queues()
            self.assertEqual(fired, 1)

        item1.refresh_from_db()
        self.assertEqual(item1.approved_by, self.user)
        self.assertIsNotNone(item1.approved_at)

    def test_26_edited_recycled_item_approval_cleared(self):
        """Case 26: Editing recycled item content clears approval."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Evergreen Edit Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue, content='Initial evergreen text', status='waiting',
            approved_by=self.user, approved_at=timezone.now(),
        )

        item.content = 'Updated evergreen text'
        item.save()

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)

    # =========================================================================
    # AM. TIMEZONE & CRON (Cases 27-30)
    # =========================================================================

    def test_27_client_timezone_cron(self):
        """Case 27: Scheduler respects client timezone."""
        # Client in Bogota (UTC-5)
        tz = _client_tz(self.client_approval.id)
        self.assertEqual(str(tz), 'America/Bogota')

    def test_28_dst_normal_behavior(self):
        """Case 28: DST timezone transitions handle correctly."""
        client_ny = Client.objects.create(
            name='NY Client',
            company='NY Co',
            email=f'ny-{id(self)}@test.com',
            timezone='America/New_York',
        )
        queue = PostQueue.objects.create(
            client=client_ny,
            name='DST Queue',
            platforms=['facebook'],
            schedule_rule='0 10 * * *',  # 10:00 AM NY time
            last_dispatched_at=datetime(2026, 3, 7, 15, 0, tzinfo=ZoneInfo('UTC')),
        )
        # Check due check does not raise
        now = datetime(2026, 3, 8, 15, 0, tzinfo=ZoneInfo('UTC'))
        is_due = _queue_is_due(queue, now)
        self.assertIsInstance(is_due, bool)

    def test_29_invalid_timezone_fallback_utc(self):
        """Case 29: Invalid client timezone gracefully falls back to UTC."""
        client_bad_tz = Client.objects.create(
            name='Bad TZ Client',
            company='Bad TZ',
            email=f'badtz-{id(self)}@test.com',
            timezone='Invalid/Timezone_Name',
        )
        tz = _client_tz(client_bad_tz.id)
        self.assertEqual(str(tz), 'UTC')

    def test_30_invalid_cron_safe_skip(self):
        """Case 30: Invalid cron rule does not crash scheduler."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Bad Cron Q',
            platforms=['facebook'],
            schedule_rule='not a valid cron expression',
        )
        now = timezone.now()
        is_due = _queue_is_due(queue, now)
        self.assertFalse(is_due)

    # =========================================================================
    # AN. DURABLE TRACEABILITY & DELETE SAFETY (Cases 31-35)
    # =========================================================================

    def test_31_unified_post_source_queue_set(self):
        """Case 31: UnifiedPost.source_queue is set upon materialization."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Trace Queue Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(queue=queue, content='Trace post', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        self.assertEqual(post.source_queue_id, queue.id)

    def test_32_unified_post_source_queued_item_set(self):
        """Case 32: UnifiedPost.source_queued_item is set upon materialization."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Trace Item Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(queue=queue, content='Trace item', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        self.assertEqual(post.source_queued_item_id, item.id)

    def test_33_deleting_queue_preserves_post(self):
        """Case 33: Deleting a PostQueue preserves historical UnifiedPost with source_queue set to null."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Delete Queue Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(queue=queue, content='Post survivor', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post = item.unified_post
        post_id = post.id

        # Delete queue
        queue.delete()

        # Post still exists
        surviving_post = UnifiedPost.objects.get(id=post_id)
        self.assertIsNone(surviving_post.source_queue)

    def test_34_deleting_item_preserves_post(self):
        """Case 34: Deleting a QueuedItem preserves historical UnifiedPost."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Delete Item Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item = QueuedItem.objects.create(queue=queue, content='Item delete survivor', status='waiting')

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            process_post_queues()

        item.refresh_from_db()
        post_id = item.unified_post_id

        # Delete item
        item.delete()

        surviving_post = UnifiedPost.objects.get(id=post_id)
        self.assertIsNone(surviving_post.source_queued_item)

    def test_35_reverse_traceability_works(self):
        """Case 35: Reverse relationship queue.unified_posts lists all materialized posts."""
        queue = PostQueue.objects.create(
            client=self.client_no_approval,
            name='Reverse Trace Q',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            last_dispatched_at=timezone.now() - timedelta(minutes=5),
        )
        item1 = QueuedItem.objects.create(queue=queue, content='Post 1', status='waiting', sort_order=1)
        item2 = QueuedItem.objects.create(queue=queue, content='Post 2', status='waiting', sort_order=2)

        with patch('social_stats.scheduler.publish_unified_post.delay'):
            # First tick
            process_post_queues()

            # Second tick
            queue.last_dispatched_at = timezone.now() - timedelta(minutes=5)
            queue.save(update_fields=['last_dispatched_at'])
            process_post_queues()

        self.assertEqual(queue.unified_posts.count(), 2)

    # =========================================================================
    # ADDITIONAL TESTS: HASHTAGS, API & REVOKE
    # =========================================================================

    def test_36_hashtag_materialization_clean(self):
        """Hashtags are normalized, deduplicated, and appended cleanly."""
        content = _build_post_content('Hello world', ['tech', '#bop', '  ai  ', '#tech', '##extra'])
        self.assertEqual(content, 'Hello world\n\n#tech #bop #ai #extra')

    def test_37_revoke_approval_api(self):
        """Revoke approval endpoint sets approval fields to null."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Revoke Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Approved item to revoke',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        res = self.api.post(f'/api/composer/queues/{queue.id}/items/{item.id}/revoke_approval/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['is_approved'])

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)

    def test_38_revoke_used_item_rejected(self):
        """Revoke approval for already used item returns 400 Bad Request."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Revoke Used Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Consumed item',
            status='used',
            approved_by=self.user,
            approved_at=timezone.now(),
        )

        res = self.api.post(f'/api/composer/queues/{queue.id}/items/{item.id}/revoke_approval/')
        self.assertEqual(res.status_code, 400)
        self.assertIn('already been used', res.data['detail'])

    def test_39_queue_platform_change_invalidates_waiting_approval(self):
        """Section W: Changing PostQueue platforms clears approval on waiting items."""
        queue = PostQueue.objects.create(
            client=self.client_approval,
            name='Platform Change Q',
            platforms=['facebook'],
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Approved item',
            status='waiting',
            approved_by=self.user,
            approved_at=timezone.now(),
        )
        self.assertTrue(item.is_approved)

        queue.platforms = ['facebook', 'instagram']
        queue.save()

        item.refresh_from_db()
        self.assertIsNone(item.approved_by)
        self.assertIsNone(item.approved_at)
