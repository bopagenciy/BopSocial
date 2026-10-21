# ============================================================================
#  Social Stats — BS-3I Platform-Level Idempotency & Safe Retry Test Suite
# ============================================================================
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.models import (
    ActionLog, Client, PlatformCredential, PlatformPublishLog,
    UnifiedPost, UserProfile,
)
from social_stats.marketplace_models import Agency
from social_stats.orchestrator import (
    MODE_INITIAL_PUBLISH, MODE_PLATFORM_RETRY,
    publish_to_platform, publish_unified_post,
    update_unified_post_status,
)
from social_stats.publication_ops import (
    PLATFORM_AMBIGUOUS, PLATFORM_BLOCKED, PLATFORM_FAILED_RETRYABLE,
    PLATFORM_NOT_TARGETED, PLATFORM_PENDING_SAFE, PLATFORM_PUBLISHING_ACTIVE,
    PLATFORM_SUCCESS, classify_platform_target, retry_failed_platform,
    serialize_publication_operation,
)
from social_stats.publishers import PublishResult, PublishError

User = get_user_model()


class PlatformRetryIdempotencyTests(TestCase):
    """Exhaustive test suite for platform-level idempotency and safe retry (BS-3I)."""

    def setUp(self):
        uid = f"{id(self)}_{timezone.now().timestamp()}".replace('.', '_')
        self.user = User.objects.create_user(username=f'op_{uid}', email=f'op_{uid}@test.com', password='password123')
        self.other_user = User.objects.create_user(username=f'other_{uid}', email=f'other_{uid}@test.com', password='password123')

        self.client_a = Client.objects.create(
            name=f'Tenant A {uid}',
            company=f'Tenant A Corp {uid}',
            email=f'client_a_{uid}@test.com',
            is_active=True,
            requires_approval=False,
        )
        self.client_b = Client.objects.create(
            name=f'Tenant B {uid}',
            company=f'Tenant B Corp {uid}',
            email=f'client_b_{uid}@test.com',
            is_active=True,
            requires_approval=False,
        )

        self.profile_a = UserProfile.objects.create(
            user=self.user,
            client=self.client_a,
            role='client',
        )

        self.profile_b = UserProfile.objects.create(
            user=self.other_user,
            client=self.client_b,
            role='client',
        )

        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # ── 1. Initial Untouched Dispatches Both ─────────────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_initial_untouched_dispatches_all_targets(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Multi-platform post',
            target_platforms=['facebook', 'instagram'],
            status='queued',
            created_by=self.user,
        )

        publish_unified_post(post.id)

        self.assertEqual(mock_delay.call_count, 2)
        mock_delay.assert_any_call(post.id, 'facebook')
        mock_delay.assert_any_call(post.id, 'instagram')

        post.refresh_from_db()
        self.assertEqual(post.status, 'publishing')
        self.assertEqual(post.publish_logs.count(), 2)

    # ── 2 & 3. Partial Post: Facebook Success + Instagram Failed ────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_partial_retry_instagram_only_skips_facebook(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Partial post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
            created_by=self.user,
        )
        fb_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_12345',
            completed_at=timezone.now(),
        )
        ig_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_message='IG container timeout',
            completed_at=timezone.now(),
        )

        res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertIn('facebook', res['untouched_platforms'])

        # Verified: publish_to_platform was called ONLY for instagram
        mock_delay.assert_called_once_with(post.id, 'instagram')

        # Facebook log was untouched
        fb_log.refresh_from_db()
        self.assertEqual(fb_log.status, 'success')
        self.assertEqual(fb_log.platform_post_id, 'fb_12345')

    # ── 4 & 5. Success Immutability: Success log & ID never reset ───────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_success_log_never_reset_and_prevents_retry(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Success post',
            target_platforms=['facebook'],
            status='published',
            created_by=self.user,
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_immutable_99',
            completed_at=timezone.now(),
        )

        # Attempting platform retry on a successful platform must fail closed
        res = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertFalse(res['success'])
        self.assertEqual(res['status_code'], 400)
        self.assertIn('already published successfully', res['error'])
        mock_delay.assert_not_called()

        # Re-running fan-out publish_unified_post also preserves success
        publish_unified_post(post.id)
        mock_delay.assert_not_called()

        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'fb_immutable_99')

    # ── 6. Failed Platform Retry Allowed ────────────────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_failed_platform_retry_allowed(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Failed post',
            target_platforms=['instagram'],
            status='failed',
            created_by=self.user,
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_code='network_error',
            error_message='Connection reset by peer',
            completed_at=timezone.now(),
        )

        res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        mock_delay.assert_called_once_with(post.id, 'instagram')

        log.refresh_from_db()
        self.assertEqual(log.status, 'pending')
        self.assertEqual(log.error_code, '')

    # ── 7 & 8. Ambiguous & Actively Publishing States Blocked ────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_ambiguous_and_actively_publishing_retry_blocked(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='In flight post',
            target_platforms=['instagram'],
            status='publishing',
            created_by=self.user,
        )
        # Actively publishing (< 15 min)
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            attempted_at=timezone.now() - timedelta(minutes=3),
        )

        res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertFalse(res['success'])
        self.assertIn('actively publishing', res['error'])
        mock_delay.assert_not_called()

        # Ambiguous: publishing > 15 min with no platform ID
        log.attempted_at = timezone.now() - timedelta(minutes=20)
        log.save()

        res2 = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertFalse(res2['success'])
        self.assertIn('timed out', res2['error'])
        mock_delay.assert_not_called()

    # ── 9 & 10. No Generic Retry-All for Partial / Published ────────────────
    def test_partial_and_published_generic_recovery_blocked(self):
        post_partial = UnifiedPost.objects.create(
            client=self.client_a,
            content='Partial post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
            created_by=self.user,
        )
        # Generic recovery endpoint must reject
        url = f'/api/social/publications/operations/{post_partial.id}/recover/'
        res = self.api.post(url)
        self.assertEqual(res.status_code, 400)
        self.assertIn('cannot be generically retried', res.data['detail'])

        post_published = UnifiedPost.objects.create(
            client=self.client_a,
            content='Published post',
            target_platforms=['facebook'],
            status='published',
            created_by=self.user,
        )
        url2 = f'/api/social/publications/operations/{post_published.id}/recover/'
        res2 = self.api.post(url2)
        self.assertEqual(res2.status_code, 400)

    # ── 11. Single Platform Post Retries Only Failed Target ─────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_single_platform_post_retries_only_failed_target(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Single platform',
            target_platforms=['facebook'],
            status='failed',
            created_by=self.user,
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
            error_message='Token expired',
        )

        # Attempting wrong platform fails
        res_wrong = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertFalse(res_wrong['success'])
        self.assertIn('not targeted', res_wrong['error'])
        mock_delay.assert_not_called()

        # Correct platform succeeds
        res_correct = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertTrue(res_correct['success'])
        mock_delay.assert_called_once_with(post.id, 'facebook')

    # ── 12. Retry Recomputes Partial -> Published When Final Succeeds ──────
    def test_retry_recomputes_partial_to_published_when_final_succeeds(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Recomputed post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
            created_by=self.user,
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_111',
        )
        ig_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
        )

        # Now Instagram succeeds on retry
        ig_log.status = 'success'
        ig_log.platform_post_id = 'ig_222'
        ig_log.save()

        update_unified_post_status(post.id)
        post.refresh_from_db()
        self.assertEqual(post.status, 'published')
        self.assertIsNotNone(post.published_at)

    # ── 13. Retry Remains Partial When Retry Fails ──────────────────────────
    def test_retry_remains_partial_when_retry_fails(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Still partial',
            target_platforms=['facebook', 'instagram'],
            status='partial',
            created_by=self.user,
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_111',
        )
        ig_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_message='Another failure',
        )

        update_unified_post_status(post.id)
        post.refresh_from_db()
        self.assertEqual(post.status, 'partial')

    # ── 14. Cross-Tenant Retry Blocked ──────────────────────────────────────
    def test_cross_tenant_retry_blocked(self):
        post_b = UnifiedPost.objects.create(
            client=self.client_b,
            content='Tenant B Post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post_b,
            platform='facebook',
            status='failed',
        )

        # user belongs to Client A, attempts to retry Client B
        url = f'/api/social/publications/operations/{post_b.id}/retry-platform/'
        res = self.api.post(url, {'platform': 'facebook'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── 15. Approval Requirement Enforced ───────────────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_approval_requirement_enforced_on_retry(self, mock_delay):
        self.client_a.requires_approval = True
        self.client_a.save()

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Needs approval post',
            target_platforms=['facebook'],
            status='failed',
            approved_by=None,
            approved_at=None,
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
        )

        res = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertFalse(res['success'])
        self.assertIn('requires approval', res['error'])
        mock_delay.assert_not_called()

        # Once approved, retry succeeds
        post.approved_by = self.user
        post.approved_at = timezone.now()
        post.save()

        res2 = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertTrue(res2['success'])
        mock_delay.assert_called_once_with(post.id, 'facebook')

    # ── 16. Inactive Tenant Blocked ─────────────────────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_inactive_tenant_retry_blocked(self, mock_delay):
        self.client_a.is_active = False
        self.client_a.save()

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Inactive tenant post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
        )

        res = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertFalse(res['success'])
        self.assertIn('inactive', res['error'])
        mock_delay.assert_not_called()

    # ── 17. Concurrent Platform Retries Dispatch Once ──────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_concurrent_platform_retry_dispatches_once(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Concurrency post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
        )

        res1 = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertTrue(res1['success'])

        # Immediate second invocation before worker picks it up
        res2 = retry_failed_platform(post.id, 'facebook', user=self.user)
        self.assertFalse(res2['success'])
        self.assertIn('pending initial worker dispatch', res2['error'])

        # Only one dispatch occurred
        self.assertEqual(mock_delay.call_count, 1)

    # ── 18 & 19. Audit Log Generated & No Secrets Serialized ────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_audit_log_generated_without_secrets(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Audit test post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_999',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_message='Rate limited',
        )

        res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])

        audit = ActionLog.objects.filter(
            client=self.client_a,
            object_type='UnifiedPost',
            object_id=str(post.id),
            action='composer.platform_retry',
        ).first()

        self.assertIsNotNone(audit)
        self.assertEqual(audit.platform, 'instagram')
        self.assertIn('facebook', audit.details.get('untouched_successful_platforms', []))

        # Check for absolute secrets safety
        details_str = json.dumps(audit.details)
        for secret_kw in ['token', 'secret', 'password', 'key', 'access_token']:
            self.assertNotIn(f'"{secret_kw}"', details_str.lower())

    # ── 20 & 21. Success Platform ID & Attempted_At Preserved ───────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_success_platform_post_id_and_attempted_at_preserved(self, mock_delay):
        orig_attempted = timezone.now() - timedelta(hours=1)
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Preserve test',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        fb_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_keep_me',
            attempted_at=orig_attempted,
            completed_at=orig_attempted + timedelta(seconds=5),
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
        )

        retry_failed_platform(post.id, 'instagram', user=self.user)

        fb_log.refresh_from_db()
        self.assertEqual(fb_log.platform_post_id, 'fb_keep_me')
        self.assertEqual(fb_log.attempted_at, orig_attempted)
        self.assertEqual(fb_log.status, 'success')

    # ── 22. Provider Error Does Not Corrupt Success Platform ────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_provider_error_does_not_corrupt_success_platform(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Error test',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        fb_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_untouched',
        )
        ig_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
        )

        # Simulate provider failure during retry execution
        with patch('social_stats.orchestrator.get_publisher') as mock_get_pub:
            mock_pub = MagicMock()
            mock_pub.publish_text.side_effect = PublishError('Instagram 500 error', code='ig_down')
            mock_get_pub.return_value = mock_pub

            PlatformCredential.objects.create(
                client=self.client_a, platform='instagram', is_active=True,
            )

            publish_to_platform(post.id, 'instagram')

        fb_log.refresh_from_db()
        self.assertEqual(fb_log.status, 'success')
        self.assertEqual(fb_log.platform_post_id, 'fb_untouched')

        ig_log.refresh_from_db()
        self.assertEqual(ig_log.status, 'failed')
        self.assertIn('Instagram 500 error', ig_log.error_message)

    # ── 23 & 24. Operations API Exposes Retryable and Hides for Success ─────
    def test_operations_api_exposes_retryable_and_protects_success(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Operations view test',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_done',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_message='Timeout',
        )

        url = f'/api/social/publications/operations/{post.id}/'
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)

        progress = {p['platform']: p for p in res.data['platform_progress']}
        self.assertFalse(progress['facebook']['can_retry'])
        self.assertTrue(progress['facebook']['is_immutable'])
        self.assertEqual(progress['facebook']['state'], PLATFORM_SUCCESS)

        self.assertTrue(progress['instagram']['can_retry'])
        self.assertFalse(progress['instagram']['is_immutable'])
        self.assertEqual(progress['instagram']['state'], PLATFORM_FAILED_RETRYABLE)

    # ── 27 & 28. Ambiguous State Displays Manual Review & Determinism ───────
    def test_ambiguous_state_displays_manual_review_deterministically(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Ambiguous test',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            attempted_at=timezone.now() - timedelta(minutes=25),
        )

        now = timezone.now()
        eval_res = classify_platform_target(post, 'instagram', log, now)
        self.assertEqual(eval_res['state'], PLATFORM_AMBIGUOUS)
        self.assertFalse(eval_res['can_retry'])
        self.assertIn('manual provider review required', eval_res['retry_ineligible_reason'])

    # ── 29. Legacy PlatformPublishLog Rows Compatibility ────────────────────
    def test_legacy_platform_publish_log_compatibility(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Legacy test',
            target_platforms=['facebook'],
            status='partial',
        )
        # Legacy row with blank traceability fields
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_legacy_1',
            provider_request_id='',
            provider_container_id='',
            provider_attempt_token='',
        )

        now = timezone.now()
        eval_res = classify_platform_target(post, 'facebook', log, now)
        self.assertEqual(eval_res['state'], PLATFORM_SUCCESS)
        self.assertTrue(eval_res['is_immutable'])
        self.assertFalse(eval_res['can_retry'])

    # ── 30. Direct publish_to_platform Aborts on Existing Success ───────────
    @patch('social_stats.orchestrator.get_publisher')
    def test_publish_to_platform_direct_abort_on_success_log(self, mock_get_pub):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Direct abort test',
            target_platforms=['facebook'],
            status='partial',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_already_done',
        )

        publish_to_platform(post.id, 'facebook')

        # Publisher must NEVER be called
        mock_get_pub.assert_not_called()
        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'fb_already_done')

    # ── 31. Direct publish_to_platform Aborts on Non-Empty Post ID ──────────
    @patch('social_stats.orchestrator.get_publisher')
    def test_publish_to_platform_direct_abort_on_platform_post_id(self, mock_get_pub):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Post ID abort test',
            target_platforms=['facebook'],
            status='partial',
        )
        # Even if status was somehow pending, having a platform_post_id aborts
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='pending',
            platform_post_id='fb_already_has_id',
        )

        publish_to_platform(post.id, 'facebook')

        mock_get_pub.assert_not_called()

    # ── 32. _mark_failed Never Overwrites Success ───────────────────────────
    def test_mark_failed_does_not_overwrite_success(self):
        from social_stats.orchestrator import _mark_failed

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Mark failed test',
            target_platforms=['facebook'],
            status='published',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_success_protect',
        )

        _mark_failed(log, code='unexpected_error', message='Some crash')

        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'fb_success_protect')
        self.assertEqual(log.error_code, '')

    # ── 33. Platform Retry API Endpoint End-to-End Success ──────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_platform_retry_api_endpoint_success(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='API retry post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_success_api',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            error_message='Token expired',
        )

        url = f'/api/social/publications/operations/{post.id}/retry-platform/'
        res = self.api.post(url, {'platform': 'instagram'}, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['platform'], 'instagram')
        self.assertIn('facebook', res.data['untouched_platforms'])

        mock_delay.assert_called_once_with(post.id, 'instagram')

    # ── 34. Platform Retry API Endpoint Rejects Invalid Payload ─────────────
    def test_platform_retry_api_endpoint_validation_error(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Bad payload post',
            target_platforms=['facebook'],
            status='failed',
        )
        url = f'/api/social/publications/operations/{post.id}/retry-platform/'

        # Missing platform
        res = self.api.post(url, {}, format='json')
        self.assertEqual(res.status_code, 400)

        # Non-targeted platform
        res2 = self.api.post(url, {'platform': 'linkedin'}, format='json')
        self.assertEqual(res2.status_code, 400)
        self.assertIn('not targeted', res2.data['detail'])

    # ── 35. Agency Scoped User Access Control ───────────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_platform_retry_agency_scoped_user(self, mock_delay):
        from social_stats.marketplace_models import AgencyClientRelation, AgencyMembership

        agency = Agency.objects.create(
            name=f'Agency Retry {id(self)}',
            slug=f'agency-retry-{id(self)}',
            owner_user=self.user,
        )
        AgencyClientRelation.objects.create(
            agency=agency,
            client=self.client_a,
            status='active',
            initiated_by='agency',
        )
        AgencyMembership.objects.create(
            agency=agency,
            user=self.user,
            role='manager',
            is_active=True,
        )
        self.profile_a.primary_agency = agency
        self.profile_a.role = 'agency_admin'
        self.profile_a.save()

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Agency post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
        )

        url = f'/api/social/publications/operations/{post.id}/retry-platform/'
        res = self.api.post(url, {'platform': 'facebook'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])

        # Now test that agency user cannot retry post from Client B (not in agency)
        post_b = UnifiedPost.objects.create(
            client=self.client_b,
            content='Client B post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post_b,
            platform='facebook',
            status='failed',
        )
        url_b = f'/api/social/publications/operations/{post_b.id}/retry-platform/'
        res_b = self.api.post(url_b, {'platform': 'facebook'}, format='json')
        self.assertEqual(res_b.status_code, 403)

    # ── 36. Timeline Includes Platform Retry Event ──────────────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_timeline_includes_platform_retry_event(self, mock_delay):
        from social_stats.publication_ops import get_publication_timeline

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Timeline retry post',
            target_platforms=['facebook'],
            status='failed',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='failed',
        )

        retry_failed_platform(post.id, 'facebook', user=self.user)

        timeline = get_publication_timeline(post)
        event_types = [e['event_type'] for e in timeline]
        self.assertIn('composer.platform_retry', event_types)

    # ── 37. Traceability Fields Persisted on Success ─────────────────────────
    @patch('social_stats.orchestrator.get_publisher')
    def test_traceability_fields_persisted_on_success(self, mock_get_pub):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Traceability post',
            target_platforms=['instagram'],
            status='queued',
        )
        PlatformCredential.objects.create(
            client=self.client_a, platform='instagram', is_active=True,
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='pending',
        )

        mock_pub = MagicMock()
        mock_result = PublishResult(
            platform_post_id='ig_live_123',
            platform_url='https://instagram.com/p/123',
            raw_response={'id': 'ig_live_123'},
        )
        mock_result.provider_container_id = 'container_9988'
        mock_result.provider_request_id = 'req_7766'
        mock_pub.publish_text.return_value = mock_result
        mock_get_pub.return_value = mock_pub

        publish_to_platform(post.id, 'instagram')

        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'ig_live_123')
        self.assertEqual(log.provider_container_id, 'container_9988')
        self.assertEqual(log.provider_request_id, 'req_7766')

    # ── 38. Retry Mode in publish_unified_post Dispatches Only Selected ─────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_retry_mode_in_publish_unified_post(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Mode test',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_mode_done',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
        )

        publish_unified_post(post.id, mode=MODE_PLATFORM_RETRY, target_platform='instagram')

        mock_delay.assert_called_once_with(post.id, 'instagram')

    # ── 39. Initial Publish Fan-Out Skips Succeeded Platform ────────────────
    @patch('social_stats.orchestrator.publish_to_platform.delay')
    def test_initial_publish_mode_skips_succeeded_platform(self, mock_delay):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Skip success post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_already_done',
        )
        # Instagram was never attempted (no log)
        publish_unified_post(post.id, mode=MODE_INITIAL_PUBLISH)

        # Instagram was dispatched, Facebook was skipped
        mock_delay.assert_called_once_with(post.id, 'instagram')

    # ── 40. Platform Retry Invalid Post Returns 404 ─────────────────────────
    def test_platform_retry_invalid_post_returns_404(self):
        url = '/api/social/publications/operations/99999999/retry-platform/'
        res = self.api.post(url, {'platform': 'facebook'}, format='json')
        self.assertEqual(res.status_code, 404)


