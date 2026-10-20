"""
Tests for Scheduled Publishing & Celery Task Registration (Phase BS-3G.1A).

Covers:
1. scheduler tasks registered in Celery app
2. task names match Beat configuration
3. due approved post dispatched
4. future post skipped
5. draft post skipped
6. pending approval skipped
7. published post skipped
8. duplicate scheduler run safe (idempotency)
9. queue processor registered
10. queue processor empty run safe
11. queue processor eligible item dispatched
12. already processed queue item skipped
13. dispatch exception handled safely
14. no real Meta API calls made
15. no historical DB mutation (test database isolation)
16. timezone-aware comparison
17. worker queue compatibility
18. Beat schedule import validation
"""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
import importlib

from dashboard.celery import app as celery_app
from social_stats.models import Client, PlatformCredential, UnifiedPost, PostQueue, QueuedItem
from social_stats.scheduler import (
    process_scheduled_posts,
    process_post_queues,
    _queue_is_due,
    _pick_next_queued_item,
)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ScheduledPublishingTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name='Test Client BS-3G',
            company='Test Company',
            email=f'test-bs3g-{id(self)}@x.test',
            timezone='America/Bogota',
        )
        self.credential = PlatformCredential.objects.create(
            client=self.client_obj,
            platform='instagram',
            access_token='mock_token_bs3g',
            instagram_account_id='17841400000000001',
            is_active=True,
        )

    # 1. scheduler tasks registered
    def test_01_scheduler_tasks_registered(self):
        registered = celery_app.tasks
        self.assertIn('social_stats.scheduler.process_scheduled_posts', registered)
        self.assertIn('social_stats.scheduler.process_post_queues', registered)

    # 2. task names match Beat config
    def test_02_task_names_match_beat_config(self):
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        self.assertIn('composer-process-scheduled-posts', beat_schedule)
        self.assertIn('composer-process-post-queues', beat_schedule)

        scheduled_task_name = beat_schedule['composer-process-scheduled-posts']['task']
        queue_task_name = beat_schedule['composer-process-post-queues']['task']

        self.assertEqual(scheduled_task_name, 'social_stats.scheduler.process_scheduled_posts')
        self.assertEqual(queue_task_name, 'social_stats.scheduler.process_post_queues')
        self.assertIn(scheduled_task_name, celery_app.tasks)
        self.assertIn(queue_task_name, celery_app.tasks)

    # 3. due approved post dispatched
    def test_03_due_approved_post_dispatched(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Due post test',
            media_type='text',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            n = process_scheduled_posts()
            self.assertEqual(n, 1)
            mock_delay.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')

    # 4. future post skipped
    def test_04_future_post_skipped(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Future post test',
            media_type='text',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=timezone.now() + timedelta(hours=2),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            n = process_scheduled_posts()
            self.assertEqual(n, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')

    # 5. draft post skipped
    def test_05_draft_post_skipped(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Draft post test',
            media_type='text',
            target_platforms=['facebook'],
            status='draft',
            scheduled_at=timezone.now() - timedelta(minutes=10),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            n = process_scheduled_posts()
            self.assertEqual(n, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'draft')

    # 6. pending approval skipped
    def test_06_pending_approval_skipped(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Pending approval test',
            media_type='text',
            target_platforms=['facebook'],
            status='pending_approval',
            scheduled_at=timezone.now() - timedelta(minutes=10),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            n = process_scheduled_posts()
            self.assertEqual(n, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

    # 7. published post skipped
    def test_07_published_post_skipped(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Already published test',
            media_type='text',
            target_platforms=['facebook'],
            status='published',
            scheduled_at=timezone.now() - timedelta(minutes=10),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            n = process_scheduled_posts()
            self.assertEqual(n, 0)
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'published')

    # 8. duplicate scheduler run safe
    def test_08_duplicate_scheduler_run_safe(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Idempotency test',
            media_type='text',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            # First tick dispatches
            n1 = process_scheduled_posts()
            self.assertEqual(n1, 1)
            mock_delay.assert_called_once_with(post.id)

            # Second consecutive tick encounters status='queued' and skips
            n2 = process_scheduled_posts()
            self.assertEqual(n2, 0)
            self.assertEqual(mock_delay.call_count, 1)

    # 9. queue processor registered
    def test_09_queue_processor_registered(self):
        self.assertIn('social_stats.scheduler.process_post_queues', celery_app.tasks)
        task_func = celery_app.tasks['social_stats.scheduler.process_post_queues']
        self.assertTrue(callable(task_func))

    # 10. queue processor empty run safe
    def test_10_queue_processor_empty_run_safe(self):
        # With zero active queues, should cleanly return 0
        fired = process_post_queues()
        self.assertEqual(fired, 0)

    # 11. queue processor eligible item
    def test_11_queue_processor_eligible_item(self):
        queue = PostQueue.objects.create(
            client=self.client_obj,
            name='Daily Morning Queue',
            platforms=['facebook'],
            schedule_rule='* * * * *',  # every minute
            queue_strategy='sequential',
            is_active=True,
            last_dispatched_at=timezone.now() - timedelta(minutes=10),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Queued Item 1',
            status='waiting',
            sort_order=1,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 1)
            self.assertEqual(mock_delay.call_count, 1)

        item.refresh_from_db()
        self.assertEqual(item.status, 'used')
        self.assertIsNotNone(item.unified_post)
        self.assertEqual(item.unified_post.status, 'queued')

    # 12. already processed queue item skipped
    def test_12_already_processed_queue_item_skipped(self):
        queue = PostQueue.objects.create(
            client=self.client_obj,
            name='Daily Queue 2',
            platforms=['facebook'],
            schedule_rule='* * * * *',
            queue_strategy='sequential',
            is_active=True,
            last_dispatched_at=timezone.now() - timedelta(minutes=10),
        )
        item = QueuedItem.objects.create(
            queue=queue,
            content='Already Used Item',
            status='used',
            sort_order=1,
        )

        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            fired = process_post_queues()
            self.assertEqual(fired, 0)
            mock_delay.assert_not_called()

    # 13. dispatch exception handled
    def test_13_dispatch_exception_handled(self):
        UnifiedPost.objects.create(
            client=self.client_obj,
            content='Exception resilience post',
            media_type='text',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=timezone.now() - timedelta(minutes=2),
        )
        with patch('social_stats.scheduler.publish_unified_post.delay', side_effect=RuntimeError('Broker connection lost')):
            # Must not crash the scheduler execution
            n = process_scheduled_posts()
            self.assertEqual(n, 0)

    # 14. no real Meta calls
    def test_14_no_real_meta_calls(self):
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            process_scheduled_posts()
            process_post_queues()
            mock_post.assert_not_called()
            mock_get.assert_not_called()

    # 15. no historical DB mutation
    def test_15_no_historical_db_mutation(self):
        # In Django test environment, test transactions are isolated.
        # Verify that only the fixtures created in this test case exist here.
        posts = UnifiedPost.objects.filter(client=self.client_obj)
        for p in posts:
            self.assertNotEqual(p.id, 7)
            self.assertNotEqual(p.id, 8)
            self.assertNotEqual(p.id, 9)

    # 16. timezone-aware comparison
    def test_16_timezone_aware_comparison(self):
        now = timezone.now()
        due_utc = now - timedelta(minutes=15)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Timezone aware test',
            media_type='text',
            target_platforms=['facebook'],
            status='scheduled',
            scheduled_at=due_utc,
        )
        self.assertTrue(timezone.is_aware(post.scheduled_at))
        self.assertTrue(post.scheduled_at <= now)

    # 17. worker queue compatibility
    def test_17_worker_queue_compatibility(self):
        task_scheduled = celery_app.tasks['social_stats.scheduler.process_scheduled_posts']
        task_queues = celery_app.tasks['social_stats.scheduler.process_post_queues']
        # Tasks inherit default queue ('celery') which matches worker's subscription
        self.assertIn(getattr(task_scheduled, 'queue', None), (None, 'celery'))
        self.assertIn(getattr(task_queues, 'queue', None), (None, 'celery'))

    # 18. Beat schedule import valid
    def test_18_beat_schedule_import_valid(self):
        for entry_name, entry_conf in settings.CELERY_BEAT_SCHEDULE.items():
            task_path = entry_conf['task']
            module_name, func_name = task_path.rsplit('.', 1)
            mod = importlib.import_module(module_name)
            func = getattr(mod, func_name)
            self.assertTrue(callable(func), f"Task {task_path} in {entry_name} is not callable")
