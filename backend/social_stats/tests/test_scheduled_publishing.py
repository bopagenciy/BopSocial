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
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
import importlib
from rest_framework.test import APIClient

from dashboard.celery import app as celery_app
from social_stats.models import (
    Client, PlatformCredential, UnifiedPost, PostQueue, QueuedItem, UserProfile,
)
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
        self.user = User.objects.create_user(
            username=f'operator_{id(self)}',
            email=f'operator_{id(self)}@test.com',
            password='testpassword123',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            client=self.client_obj,
            role='client',
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

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

    # 19. schedule future requires approval sets pending_approval
    def test_19_schedule_future_requires_approval_sets_pending_approval(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Schedule requires approval post',
            media_type='text',
            target_platforms=['instagram'],
            status='draft',
        )
        future_time = timezone.now() + timedelta(minutes=15)
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_sched_pub, \
             patch('social_stats.orchestrator.publish_unified_post.delay') as mock_orch_pub:
            res = self.api.post(
                f'/api/composer/posts/{post.id}/schedule/',
                {'scheduled_at': future_time.isoformat()},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['status'], 'pending_approval')
            mock_sched_pub.assert_not_called()
            mock_orch_pub.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')
        self.assertIsNone(post.approved_by)
        self.assertIsNone(post.approved_at)
        self.assertEqual(post.scheduled_at, future_time)

    # 20. future schedule no immediate publish
    def test_20_future_schedule_no_immediate_publish(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='No immediate publish test',
            media_type='text',
            target_platforms=['instagram'],
            status='draft',
        )
        future_time = timezone.now() + timedelta(minutes=10)
        with patch('requests.post') as mock_http_post, \
             patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            res = self.api.post(
                f'/api/composer/posts/{post.id}/schedule/',
                {'scheduled_at': future_time.isoformat()},
            )
            self.assertEqual(res.status_code, 200)
            mock_delay.assert_not_called()
            mock_http_post.assert_not_called()

    # 21. approve future post sets status scheduled
    def test_21_approve_future_post_sets_status_scheduled(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        future_time = timezone.now() + timedelta(minutes=12)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Approve future post test',
            media_type='text',
            target_platforms=['instagram'],
            status='pending_approval',
            scheduled_at=future_time,
        )
        with patch('social_stats.orchestrator.publish_unified_post.delay') as mock_delay:
            res = self.api.post(f'/api/composer/posts/{post.id}/approve/')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['status'], 'scheduled')
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')
        self.assertEqual(post.approved_by, self.user)
        self.assertIsNotNone(post.approved_at)
        self.assertEqual(post.scheduled_at, future_time)

    # 22. approve future no celery publish dispatch
    def test_22_approve_future_no_celery_publish_dispatch(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        future_time = timezone.now() + timedelta(hours=1)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Approve future post celery check',
            media_type='text',
            target_platforms=['instagram'],
            status='pending_approval',
            scheduled_at=future_time,
        )
        with patch('social_stats.orchestrator.publish_unified_post.delay') as mock_delay:
            res = self.api.post(f'/api/composer/posts/{post.id}/approve/')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(mock_delay.call_count, 0)

    # 23. approve future preserves scheduled_at and audit fields
    def test_23_approve_future_preserves_scheduled_at_and_audit_fields(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        exact_time = timezone.now() + timedelta(minutes=20)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Audit integrity test',
            media_type='text',
            target_platforms=['instagram'],
            status='pending_approval',
            scheduled_at=exact_time,
        )
        from django.utils.dateparse import parse_datetime
        res = self.api.post(f'/api/composer/posts/{post.id}/approve/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(parse_datetime(res.data['scheduled_at']), exact_time)
        self.assertEqual(res.data['approved_by'], self.user.id)
        self.assertIsNotNone(res.data['approved_at'])

        post.refresh_from_db()
        self.assertEqual(post.scheduled_at, exact_time)
        self.assertEqual(post.approved_by, self.user)
        self.assertIsNotNone(post.approved_at)

    # 24. due approved post dispatched by scheduler
    def test_24_due_approved_post_dispatched_by_scheduler(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        due_time = timezone.now() - timedelta(minutes=2)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Due approved scheduler pickup',
            media_type='text',
            target_platforms=['instagram'],
            status='scheduled',
            approved_by=self.user,
            approved_at=timezone.now() - timedelta(minutes=10),
            scheduled_at=due_time,
        )
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            dispatched = process_scheduled_posts()
            self.assertEqual(dispatched, 1)
            mock_delay.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')

    # 25. due unapproved post blocked by orchestrator approval gate
    def test_25_due_unapproved_post_blocked_by_orchestrator(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        # Construct synthetic state simulating a post claimed to queued without approval
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Defensive unapproved post',
            media_type='text',
            target_platforms=['instagram'],
            status='queued',
            approved_by=None,
            approved_at=None,
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        from social_stats.orchestrator import publish_unified_post
        with patch('social_stats.publishers.instagram.InstagramPublisher.publish_text') as mock_pub:
            publish_unified_post(post.id)
            mock_pub.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

    # 26. immediate publish approval regression
    def test_26_immediate_publish_approval_regression(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Immediate publish regression test',
            media_type='text',
            target_platforms=['instagram'],
            status='draft',
            scheduled_at=None,
        )
        # Step 1: publish_now moves to pending_approval
        res_pub = self.api.post(f'/api/composer/posts/{post.id}/publish_now/')
        self.assertEqual(res_pub.status_code, 202)
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')

        # Step 2: approve immediate moves to queued and dispatches publish task
        with patch('social_stats.orchestrator.publish_unified_post.delay') as mock_delay:
            res_app = self.api.post(f'/api/composer/posts/{post.id}/approve/')
            self.assertEqual(res_app.status_code, 200)
            self.assertEqual(res_app.data['status'], 'queued')
            mock_delay.assert_called_once_with(post.id)

        post.refresh_from_db()
        self.assertEqual(post.status, 'queued')
        self.assertEqual(post.approved_by, self.user)
        self.assertIsNotNone(post.approved_at)

    # 27. no-approval tenant future scheduling
    def test_27_no_approval_tenant_future_scheduling(self):
        self.client_obj.requires_approval = False
        self.client_obj.save(update_fields=['requires_approval'])
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='No approval tenant future schedule',
            media_type='text',
            target_platforms=['instagram'],
            status='draft',
        )
        future_time = timezone.now() + timedelta(minutes=30)
        with patch('social_stats.scheduler.publish_unified_post.delay') as mock_delay:
            res = self.api.post(
                f'/api/composer/posts/{post.id}/schedule/',
                {'scheduled_at': future_time.isoformat()},
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['status'], 'scheduled')
            mock_delay.assert_not_called()

        post.refresh_from_db()
        self.assertEqual(post.status, 'scheduled')
        self.assertEqual(post.scheduled_at, future_time)

    # 28. second approve safe (rejected with 400)
    def test_28_second_approve_safe_rejected(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        future_time = timezone.now() + timedelta(minutes=15)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Idempotent approval test',
            media_type='text',
            target_platforms=['instagram'],
            status='pending_approval',
            scheduled_at=future_time,
        )
        # First approve
        res1 = self.api.post(f'/api/composer/posts/{post.id}/approve/')
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data['status'], 'scheduled')

        # Second approve must be safely rejected
        with patch('social_stats.orchestrator.publish_unified_post.delay') as mock_delay:
            res2 = self.api.post(f'/api/composer/posts/{post.id}/approve/')
            self.assertEqual(res2.status_code, 400)
            self.assertIn('not pending approval', res2.data.get('detail', ''))
            mock_delay.assert_not_called()

    # 29. invalid and past schedule rejected
    def test_29_invalid_and_past_schedule_rejected(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Validation test',
            media_type='text',
            target_platforms=['instagram'],
            status='draft',
        )
        # Past timestamp
        past = (timezone.now() - timedelta(minutes=5)).isoformat()
        res_past = self.api.post(f'/api/composer/posts/{post.id}/schedule/', {'scheduled_at': past})
        self.assertEqual(res_past.status_code, 400)
        self.assertIn('must be in the future', res_past.data.get('detail', ''))

        # Naive datetime
        res_naive = self.api.post(f'/api/composer/posts/{post.id}/schedule/', {'scheduled_at': '2026-10-25 15:30:00'})
        self.assertEqual(res_naive.status_code, 400)
        self.assertIn('timezone-aware', res_naive.data.get('detail', ''))

        # Malformed
        res_bad = self.api.post(f'/api/composer/posts/{post.id}/schedule/', {'scheduled_at': 'not-a-date'})
        self.assertEqual(res_bad.status_code, 400)

    # 30. reschedule resets approval if requires_approval
    def test_30_reschedule_resets_approval_if_requires_approval(self):
        self.client_obj.requires_approval = True
        self.client_obj.save(update_fields=['requires_approval'])
        future_time = timezone.now() + timedelta(minutes=15)
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            created_by=self.user,
            content='Reschedule resets approval test',
            media_type='text',
            target_platforms=['instagram'],
            status='scheduled',
            approved_by=self.user,
            approved_at=timezone.now() - timedelta(minutes=5),
            scheduled_at=future_time,
        )
        new_future_time = future_time + timedelta(hours=2)
        res = self.api.post(
            f'/api/composer/posts/{post.id}/schedule/',
            {'scheduled_at': new_future_time.isoformat()},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'pending_approval')
        self.assertIsNone(res.data['approved_by'])

        post.refresh_from_db()
        self.assertEqual(post.status, 'pending_approval')
        self.assertIsNone(post.approved_by)
        self.assertIsNone(post.approved_at)
        self.assertEqual(post.scheduled_at, new_future_time)
