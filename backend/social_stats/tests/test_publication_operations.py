# ============================================================================
#  Social Stats — BS-3H Publication Operations & Console Test Suite
# ============================================================================
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from social_stats.models import (
    Client, PlatformCredential, PostQueue, QueuedItem, UnifiedPost,
    PlatformPublishLog, UserProfile, ActionLog,
)
from social_stats.marketplace_models import Agency, AgencyMembership, AgencyClientRelation
from social_stats.publication_ops import (
    classify_publication, get_publication_timeline,
    serialize_publication_operation, execute_safe_recovery,
)

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PublicationOperationsTests(TestCase):
    def setUp(self):
        # Tenant 1: requires_approval = True
        self.client_appr = Client.objects.create(
            name='Tenant Approval Ops',
            company='Approval Ops Corp',
            email=f'client-appr-{id(self)}@test.com',
            timezone='America/Bogota',
            requires_approval=True,
            is_active=True,
        )
        self.cred_fb1 = PlatformCredential.objects.create(
            client=self.client_appr,
            platform='facebook',
            access_token='mock_secret_token_fb1',
            page_id='page_appr_123',
            is_active=True,
        )

        # Tenant 2: requires_approval = False
        self.client_no_appr = Client.objects.create(
            name='Tenant No-Approval Ops',
            company='No-Approval Ops Corp',
            email=f'client-noappr-{id(self)}@test.com',
            timezone='UTC',
            requires_approval=False,
            is_active=True,
        )

        # Tenant 3: Inactive client
        self.client_inactive = Client.objects.create(
            name='Tenant Inactive Ops',
            company='Inactive Ops Corp',
            email=f'client-inactive-{id(self)}@test.com',
            timezone='UTC',
            requires_approval=False,
            is_active=False,
        )

        # Users
        self.user_a = User.objects.create_user(
            username=f'operator_a_{id(self)}',
            email=f'operator_a_{id(self)}@test.com',
            password='testpassword123',
            first_name='Alice',
            last_name='Operator',
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            client=self.client_appr,
            role='client',
        )

        self.user_b = User.objects.create_user(
            username=f'operator_b_{id(self)}',
            email=f'operator_b_{id(self)}@test.com',
            password='testpassword123',
            first_name='Bob',
            last_name='Operator',
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            client=self.client_no_appr,
            role='client',
        )

        # API Clients
        self.api_a = APIClient()
        self.api_a.force_authenticate(user=self.user_a)

        self.api_b = APIClient()
        self.api_b.force_authenticate(user=self.user_b)

    # =========================================================================
    # CLASSIFICATION & ATTENTION TESTS (Cases 1-12)
    # =========================================================================

    def test_01_normal_published_classification(self):
        """Case 1: status='published' maps to PUBLISHED_SUCCESS, no attention required."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Published post',
            status='published',
            published_at=timezone.now(),
        )
        res = classify_publication(post)
        self.assertEqual(res['classification'], 'PUBLISHED_SUCCESS')
        self.assertFalse(res['attention_required'])
        self.assertEqual(res['severity'], 'INFO')
        self.assertFalse(res['can_recover'])

    def test_02_fresh_queued_classification(self):
        """Case 2: status='queued' within grace period maps to QUEUED_FRESH."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Freshly queued post',
            status='queued',
            queued_at=now - timedelta(seconds=60),
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'QUEUED_FRESH')
        self.assertFalse(res['attention_required'])
        self.assertFalse(res['can_recover'])

    def test_03_recoverable_queued_classification(self):
        """Case 3: status='queued' age >= 5m with 0 logs maps to QUEUED_RECOVERABLE."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Orphaned queued post',
            status='queued',
            queued_at=now - timedelta(minutes=6),
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'QUEUED_RECOVERABLE')
        self.assertTrue(res['attention_required'])
        self.assertEqual(res['severity'], 'WARNING')
        self.assertTrue(res['can_recover'])

    def test_04_queued_with_logs_ambiguous_manual_review(self):
        """Case 4: status='queued' with pre-existing logs maps to QUEUED_AMBIGUOUS or MANUAL_REVIEW."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Queued post with logs',
            status='queued',
            queued_at=now - timedelta(minutes=6),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='pending',
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'QUEUED_AMBIGUOUS')
        self.assertTrue(res['attention_required'])
        self.assertFalse(res['can_recover'])

        # With success log -> MANUAL_REVIEW_REQUIRED
        PlatformPublishLog.objects.filter(unified_post=post).update(status='success', platform_post_id='fb_123')
        res2 = classify_publication(post, now=now)
        self.assertEqual(res2['classification'], 'MANUAL_REVIEW_REQUIRED')
        self.assertEqual(res2['severity'], 'CRITICAL')
        self.assertFalse(res2['can_recover'])

    def test_05_active_publishing_classification(self):
        """Case 5: status='publishing' with recent attempt maps to PUBLISHING_ACTIVE."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='In flight post',
            status='publishing',
            queued_at=now - timedelta(minutes=3),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='publishing',
            attempted_at=now - timedelta(minutes=1),
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'PUBLISHING_ACTIVE')
        self.assertFalse(res['attention_required'])
        self.assertFalse(res['can_recover'])

    def test_06_stalled_publishing_classification(self):
        """Case 6: status='publishing' fanout pending > 15m maps to PUBLISHING_STALLED."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Stalled post',
            status='publishing',
            queued_at=now - timedelta(minutes=20),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='pending',
            attempted_at=None,
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'PUBLISHING_STALLED')
        self.assertTrue(res['attention_required'])
        self.assertEqual(res['severity'], 'WARNING')
        self.assertFalse(res['can_recover'])

    def test_07_provider_ambiguity_classification(self):
        """Case 7: status='publishing' attempted > 15m without platform ID maps to MANUAL_REVIEW_REQUIRED."""
        now = timezone.now()
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Ambiguous post',
            status='publishing',
            queued_at=now - timedelta(minutes=25),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='publishing',
            attempted_at=now - timedelta(minutes=20),
            platform_post_id='',
        )
        res = classify_publication(post, now=now)
        self.assertEqual(res['classification'], 'MANUAL_REVIEW_REQUIRED')
        self.assertTrue(res['attention_required'])
        self.assertEqual(res['severity'], 'CRITICAL')
        self.assertIn('Provider acceptance cannot be determined safely', res['attention_reason'])
        self.assertFalse(res['can_recover'])

    def test_08_partial_publication_classification(self):
        """Case 8: status='partial' maps to PARTIAL_FAILURE with ERROR severity."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Partial post',
            status='partial',
            target_platforms=['facebook', 'instagram'],
        )
        PlatformPublishLog.objects.create(unified_post=post, platform='facebook', status='success', platform_post_id='fb_1')
        PlatformPublishLog.objects.create(unified_post=post, platform='instagram', status='failed', error_message='Rate limited')
        res = classify_publication(post)
        self.assertEqual(res['classification'], 'PARTIAL_FAILURE')
        self.assertTrue(res['attention_required'])
        self.assertEqual(res['severity'], 'ERROR')
        self.assertFalse(res['can_recover'])

    def test_09_failed_classification(self):
        """Case 9: status='failed' maps to FAILED_TERMINAL with ERROR severity."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Failed post',
            status='failed',
        )
        res = classify_publication(post)
        self.assertEqual(res['classification'], 'FAILED_TERMINAL')
        self.assertTrue(res['attention_required'])
        self.assertEqual(res['severity'], 'ERROR')
        self.assertFalse(res['can_recover'])

    def test_10_pending_approval_classification(self):
        """Case 10: status='pending_approval' maps to PENDING_APPROVAL."""
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Awaiting signoff',
            status='pending_approval',
        )
        res = classify_publication(post)
        self.assertEqual(res['classification'], 'PENDING_APPROVAL')
        self.assertTrue(res['attention_required'])
        self.assertFalse(res['can_recover'])

    def test_11_attention_required_logic(self):
        """Case 11: attention_required is strictly true for operational anomalies."""
        post_pub = UnifiedPost.objects.create(client=self.client_no_appr, status='published')
        self.assertFalse(classify_publication(post_pub)['attention_required'])

        post_fresh = UnifiedPost.objects.create(client=self.client_no_appr, status='queued', queued_at=timezone.now())
        self.assertFalse(classify_publication(post_fresh)['attention_required'])

        post_stale = UnifiedPost.objects.create(client=self.client_no_appr, status='queued', queued_at=timezone.now() - timedelta(minutes=10))
        self.assertTrue(classify_publication(post_stale)['attention_required'])

    def test_12_severity_logic(self):
        """Case 12: Validate deterministic severity hierarchy (INFO, WARNING, ERROR, CRITICAL)."""
        post_info = UnifiedPost.objects.create(client=self.client_no_appr, status='published')
        self.assertEqual(classify_publication(post_info)['severity'], 'INFO')

        post_warn = UnifiedPost.objects.create(client=self.client_no_appr, status='queued', queued_at=timezone.now() - timedelta(minutes=6))
        self.assertEqual(classify_publication(post_warn)['severity'], 'WARNING')

        post_err = UnifiedPost.objects.create(client=self.client_no_appr, status='failed')
        self.assertEqual(classify_publication(post_err)['severity'], 'ERROR')

        post_crit = UnifiedPost.objects.create(client=self.client_no_appr, status='publishing')
        PlatformPublishLog.objects.create(
            unified_post=post_crit, platform='facebook', status='publishing',
            attempted_at=timezone.now() - timedelta(minutes=20), platform_post_id='',
        )
        self.assertEqual(classify_publication(post_crit)['severity'], 'CRITICAL')

    # =========================================================================
    # TIMELINE & PROVENANCE TESTS (Cases 13-17)
    # =========================================================================

    def test_13_timeline_reconstruction(self):
        """Case 13: Reconstruct chronological event timeline."""
        t0 = timezone.now() - timedelta(hours=1)
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Timeline test',
            status='published',
            created_by=self.user_a,
            created_at=t0,
            approved_by=self.user_a,
            approved_at=t0 + timedelta(minutes=5),
            queued_at=t0 + timedelta(minutes=6),
            published_at=t0 + timedelta(minutes=10),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            attempted_at=t0 + timedelta(minutes=7),
            completed_at=t0 + timedelta(minutes=9),
            platform_post_id='fb_tl_123',
        )

        timeline = get_publication_timeline(post)
        self.assertGreaterEqual(len(timeline), 4)

        types = [e['event_type'] for e in timeline]
        self.assertIn('post_created', types)
        self.assertIn('post_approved', types)
        self.assertIn('post_queued', types)
        self.assertIn('platform_attempt', types)
        self.assertIn('platform_completed', types)
        self.assertIn('post_published', types)

        # Strictly ordered
        timestamps = [e['timestamp'] for e in timeline]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_14_multi_platform_mixed_state(self):
        """Case 14: Multi-platform outcome exposes individual platform statuses independently."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Multi platform post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(unified_post=post, platform='facebook', status='success', platform_post_id='fb_ok')
        PlatformPublishLog.objects.create(unified_post=post, platform='instagram', status='failed', error_message='Image aspect ratio rejected')

        data = serialize_publication_operation(post)
        progress = {p['platform']: p['status'] for p in data['platform_progress']}
        self.assertEqual(progress['facebook'], 'success')
        self.assertEqual(progress['instagram'], 'failed')

    def test_15_postqueue_provenance(self):
        """Case 15: PostQueue origin surfaces POST_QUEUE provenance and queue details."""
        queue = PostQueue.objects.create(
            client=self.client_no_appr,
            name='Daily Evergreen',
            schedule_rule='0 9 * * *',
        )
        item = QueuedItem.objects.create(queue=queue, content='Item 1', status='used')
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Item 1',
            source_queue=queue,
            source_queued_item=item,
            status='queued',
            queued_at=timezone.now(),
        )
        data = serialize_publication_operation(post)
        self.assertEqual(data['source']['type'], 'POST_QUEUE')
        self.assertEqual(data['source']['queue_id'], queue.id)
        self.assertEqual(data['source']['queue_name'], 'Daily Evergreen')
        self.assertEqual(data['source']['queued_item_id'], item.id)

    def test_16_scheduled_provenance(self):
        """Case 16: Scheduled origin surfaces SCHEDULED provenance."""
        sched_time = timezone.now() + timedelta(hours=5)
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Future announcement',
            status='scheduled',
            scheduled_at=sched_time,
        )
        data = serialize_publication_operation(post)
        self.assertEqual(data['source']['type'], 'SCHEDULED')
        self.assertEqual(data['source']['scheduled_at'], sched_time.isoformat())

    def test_17_recovered_provenance(self):
        """Case 17: Post recovered by operator records an ActionLog event in the timeline."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Recovered post',
            status='queued',
            queued_at=timezone.now() - timedelta(minutes=10),
        )
        with patch('social_stats.publication_ops.publish_unified_post.delay'):
            res = execute_safe_recovery(post.id, self.user_b)
            self.assertTrue(res['success'])

        timeline = get_publication_timeline(post)
        actions = [e for e in timeline if e['event_type'] == 'composer.manual_recovery']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['source'], self.user_b.username)

    # =========================================================================
    # TENANT ISOLATION & GOVERNANCE TESTS (Cases 18-21)
    # =========================================================================

    def test_18_tenant_a_cannot_access_tenant_b(self):
        """Case 18: User A cannot see or access User B's publications."""
        post_b = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Tenant B Secret Content',
            status='queued',
            queued_at=timezone.now() - timedelta(minutes=10),
        )

        # List endpoint as User A does not include post B
        resp = self.api_a.get('/api/social/publications/operations/')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data['results']]
        self.assertNotIn(post_b.id, ids)

        # Detail endpoint as User A returns 404
        resp_detail = self.api_a.get(f'/api/social/publications/operations/{post_b.id}/')
        self.assertEqual(resp_detail.status_code, 404)

        # Timeline endpoint as User A returns 403 or 404
        resp_tl = self.api_a.get(f'/api/social/publications/{post_b.id}/timeline/')
        self.assertIn(resp_tl.status_code, (403, 404))

    def test_19_agency_scope_works_correctly(self):
        """Case 19: Agency operator with active relation can access client publications."""
        agency = Agency.objects.create(
            name='Global Agency Partner',
            slug=f'agency-{id(self)}',
            owner_user=self.user_a,
        )
        AgencyMembership.objects.create(user=self.user_a, agency=agency, is_active=True, role='member')
        AgencyClientRelation.objects.create(agency=agency, client=self.client_no_appr, status='active')

        # Update user profile primary_agency
        self.profile_a.primary_agency_id = agency.id
        self.profile_a.save()

        post_b = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Managed Client Post',
            status='queued',
            queued_at=timezone.now(),
        )

        resp = self.api_a.get('/api/social/publications/operations/')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data['results']]
        self.assertIn(post_b.id, ids)

    def test_20_unauthorized_operator_recovery_rejected(self):
        """Case 20: User A attempting recovery on User B's post is rejected."""
        post_b = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Tenant B Orphan',
            status='queued',
            queued_at=timezone.now() - timedelta(minutes=10),
        )

        resp = self.api_a.post(f'/api/social/publications/operations/{post_b.id}/recover/')
        self.assertIn(resp.status_code, (403, 404))

    def test_21_approval_bypass_impossible(self):
        """Case 21: Post on approval-requiring tenant missing approval cannot be recovered."""
        post = UnifiedPost.objects.create(
            client=self.client_appr,
            content='Unapproved orphan',
            status='queued',
            queued_at=timezone.now() - timedelta(minutes=10),
            approved_by=None,
            approved_at=None,
        )

        resp = self.api_a.post(f'/api/social/publications/operations/{post.id}/recover/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('approval', resp.data['detail'].lower())

    # =========================================================================
    # RECOVERY BOUNDARIES & SAFETY (Cases 22-26)
    # =========================================================================

    def test_22_recovery_action_revalidates_db_state(self):
        """Case 22: Recovery re-checks classification under row lock and rejects if stale."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='State changes before recovery',
            status='published', # not recoverable
        )
        res = execute_safe_recovery(post.id, self.user_b)
        self.assertFalse(res['success'])
        self.assertEqual(res['status_code'], 400)

    def test_23_recovery_action_cannot_duplicate_existing_logs(self):
        """Case 23: Recovery is rejected if any PlatformPublishLog row exists."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Queued with log',
            status='queued',
            queued_at=timezone.now() - timedelta(minutes=10),
        )
        PlatformPublishLog.objects.create(
            unified_post=post, platform='facebook', status='pending',
        )
        res = execute_safe_recovery(post.id, self.user_b)
        self.assertFalse(res['success'])
        self.assertIn('PlatformPublishLog', res['error'])

    def test_24_published_post_cannot_be_retried(self):
        """Case 24: POST recover on published post returns 400 Bad Request."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Published already',
            status='published',
        )
        resp = self.api_b.post(f'/api/social/publications/operations/{post.id}/recover/')
        self.assertEqual(resp.status_code, 400)

    def test_25_publishing_post_cannot_be_retried(self):
        """Case 25: POST recover on actively publishing post returns 400 Bad Request."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Publishing in flight',
            status='publishing',
        )
        resp = self.api_b.post(f'/api/social/publications/operations/{post.id}/recover/')
        self.assertEqual(resp.status_code, 400)

    def test_26_partial_post_cannot_be_generically_retried(self):
        """Case 26: POST recover on partial post returns 400 to prevent duplicate publishing."""
        post = UnifiedPost.objects.create(
            client=self.client_no_appr,
            content='Partial success post',
            status='partial',
        )
        resp = self.api_b.post(f'/api/social/publications/operations/{post.id}/recover/')
        self.assertEqual(resp.status_code, 400)

    # =========================================================================
    # API FILTERING, PAGINATION & SERIALIZATION (Cases 27-30)
    # =========================================================================

    def test_27_api_filtering(self):
        """Case 27: List endpoint supports status, platform, source_type, and attention filtering."""
        p1 = UnifiedPost.objects.create(client=self.client_no_appr, status='queued', queued_at=timezone.now() - timedelta(minutes=10), target_platforms=['facebook'])
        p2 = UnifiedPost.objects.create(client=self.client_no_appr, status='published', target_platforms=['instagram'])

        resp = self.api_b.get('/api/social/publications/operations/?platform=facebook')
        self.assertEqual(resp.status_code, 200)
        ids = [p['id'] for p in resp.data['results']]
        self.assertIn(p1.id, ids)
        self.assertNotIn(p2.id, ids)

        resp_att = self.api_b.get('/api/social/publications/operations/?attention_required=true')
        ids_att = [p['id'] for p in resp_att.data['results']]
        self.assertIn(p1.id, ids_att)
        self.assertNotIn(p2.id, ids_att)

    def test_28_api_pagination(self):
        """Case 28: List endpoint respects page and page_size."""
        for i in range(5):
            UnifiedPost.objects.create(client=self.client_no_appr, content=f'Post {i}')

        resp = self.api_b.get('/api/social/publications/operations/?page=1&page_size=2')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 2)
        self.assertEqual(resp.data['page'], 1)
        self.assertEqual(resp.data['page_size'], 2)
        self.assertGreaterEqual(resp.data['total_pages'], 3)

    def test_29_frontend_status_mapping(self):
        """Case 29: Every classification returns valid label, severity, and reason."""
        post = UnifiedPost.objects.create(client=self.client_no_appr, status='queued', queued_at=timezone.now() - timedelta(minutes=10))
        data = serialize_publication_operation(post)
        cls = data['classification']
        self.assertIn('classification', cls)
        self.assertIn('attention_required', cls)
        self.assertIn('attention_reason', cls)
        self.assertIn('severity', cls)
        self.assertIn('can_recover', cls)

    def test_30_no_secret_fields_serialized(self):
        """Case 30: Serialization does not leak tokens, secrets, or password hashes."""
        post = UnifiedPost.objects.create(client=self.client_appr, content='Sensitive data test')
        data = serialize_publication_operation(post)
        raw_text = str(data)
        self.assertNotIn('mock_secret_token_fb1', raw_text)
        self.assertNotIn('access_token', raw_text)
        self.assertNotIn('password', raw_text)
