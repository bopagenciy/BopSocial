# ============================================================================
#  Social Stats — BS-3J Provider Reconciliation Test Suite
# ============================================================================
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.models import (
    ActionLog, Client, PlatformCredential, PlatformPublishLog,
    UnifiedPost, UserProfile,
)
from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.orchestrator import publish_to_platform, update_unified_post_status
from social_stats.publication_ops import (
    PLATFORM_AMBIGUOUS, PLATFORM_FAILED_RETRYABLE, PLATFORM_SUCCESS,
    classify_platform_target, reconcile_platform_publication,
    retry_failed_platform, serialize_publication_operation,
)
from social_stats.reconciliation import (
    OUTCOME_AMBIGUOUS, OUTCOME_CONFIRMED_NOT_PUBLISHED,
    OUTCOME_CONFIRMED_PUBLISHED, OUTCOME_PROVIDER_ERROR,
    OUTCOME_RECONCILIATION_UNAVAILABLE, OUTCOME_STILL_PROCESSING,
    FacebookReconciliationAdapter, InstagramReconciliationAdapter,
)
from social_stats.publishers import PublishResult, PublishError

User = get_user_model()


class ProviderReconciliationTests(TestCase):
    """Exhaustive test suite for ambiguous publish reconciliation (BS-3J)."""

    def setUp(self):
        uid = f"{id(self)}_{timezone.now().timestamp()}".replace('.', '_')
        self.user = User.objects.create_user(username=f'rec_op_{uid}', email=f'rec_op_{uid}@test.com', password='password123')
        self.other_user = User.objects.create_user(username=f'other_rec_{uid}', email=f'other_rec_{uid}@test.com', password='password123')

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

        # Credentials
        self.ig_cred_a = PlatformCredential.objects.create(
            client=self.client_a,
            platform='instagram',
            instagram_account_id='ig_acc_123',
            access_token='fake_ig_token',
            is_active=True,
        )
        self.fb_cred_a = PlatformCredential.objects.create(
            client=self.client_a,
            platform='facebook',
            page_id='fb_page_123',
            access_token='fake_fb_token',
            is_active=True,
        )

        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # ── 1. Instagram Ambiguous + Container FINISHED -> Confirmed Published ─
    @patch('social_stats.reconciliation.GraphClient')
    def test_instagram_finished_container_confirms_published(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            {'status_code': 'FINISHED', 'id': 'cont_999'},  # Container query
            {'data': [{'id': 'ig_post_888', 'caption': 'Test post'}]},  # Media query
        ]
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Test post',
            target_platforms=['instagram'],
            status='publishing',
            created_by=self.user,
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_999',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertEqual(res['outcome'], OUTCOME_CONFIRMED_PUBLISHED)
        self.assertEqual(res['provider_post_id'], 'ig_post_888')

        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'ig_post_888')
        self.assertEqual(log.reconciliation_status, OUTCOME_CONFIRMED_PUBLISHED)

    # ── 2. Confirmed Published Never Retried ────────────────────────────────
    def test_confirmed_published_never_retried(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Published post',
            target_platforms=['instagram'],
            status='published',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='success',
            platform_post_id='ig_immutable_post',
            reconciliation_status=OUTCOME_CONFIRMED_PUBLISHED,
        )

        eval_res = classify_platform_target(post, 'instagram', log)
        self.assertEqual(eval_res['state'], PLATFORM_SUCCESS)
        self.assertFalse(eval_res['can_retry'])
        self.assertTrue(eval_res['is_immutable'])

        # Attempting retry must be rejected
        retry_res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertFalse(retry_res['success'])
        self.assertIn('already published successfully', retry_res['error'])

    # ── 3. Instagram Container IN_PROGRESS -> Still Processing ─────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_instagram_in_progress_container_returns_still_processing(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'status_code': 'IN_PROGRESS', 'id': 'cont_proc'}
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Processing video post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_proc',
            attempted_at=timezone.now() - timedelta(minutes=16),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertEqual(res['outcome'], OUTCOME_STILL_PROCESSING)
        self.assertFalse(res['safe_to_retry'])

        log.refresh_from_db()
        self.assertEqual(log.status, 'publishing')
        self.assertEqual(log.reconciliation_status, OUTCOME_STILL_PROCESSING)

    # ── 4. Instagram Terminal Error -> Confirmed Not Published ─────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_instagram_error_container_confirms_not_published(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {
            'status_code': 'ERROR',
            'status': 'Video duration exceeds limit',
            'id': 'cont_err',
        }
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Failing video post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_err',
            attempted_at=timezone.now() - timedelta(minutes=18),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertEqual(res['outcome'], OUTCOME_CONFIRMED_NOT_PUBLISHED)
        self.assertTrue(res['safe_to_retry'])

        log.refresh_from_db()
        self.assertEqual(log.status, 'failed')
        self.assertEqual(log.error_code, 'reconciled_not_published')
        self.assertEqual(log.reconciliation_status, OUTCOME_CONFIRMED_NOT_PUBLISHED)

        # Now platform evaluates as failed retryable
        eval_res = classify_platform_target(post, 'instagram', log)
        self.assertEqual(eval_res['state'], PLATFORM_FAILED_RETRYABLE)
        self.assertTrue(eval_res['can_retry'])

    # ── 5. Unknown Instagram Status -> Ambiguous ───────────────────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_unknown_instagram_status_returns_ambiguous(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'status_code': 'UNKNOWN_STATE_XYZ'}
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Weird post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_weird',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertEqual(res['outcome'], OUTCOME_AMBIGUOUS)
        self.assertFalse(res['safe_to_retry'])

    # ── 6. Container Lookup Timeout -> Provider Error & Blocked ────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_container_lookup_timeout_returns_provider_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.side_effect = PublishError('Connection timed out', code='timeout')
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Timeout post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_timeout',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertTrue(res['success'])
        self.assertEqual(res['outcome'], OUTCOME_PROVIDER_ERROR)
        self.assertFalse(res['safe_to_retry'])

    # ── 7. Malformed Provider Response -> Blocked ──────────────────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_malformed_provider_response_is_blocked(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {}  # Empty/missing status_code
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Malformed post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cont_malformed',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertEqual(res['outcome'], OUTCOME_AMBIGUOUS)
        self.assertFalse(res['safe_to_retry'])

    # ── 8. Missing Container ID -> Reconciliation Unavailable ──────────────
    def test_missing_container_id_returns_reconciliation_unavailable(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='No container post',
            target_platforms=['instagram'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='',  # Missing
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'instagram', user=self.user)
        self.assertEqual(res['outcome'], OUTCOME_RECONCILIATION_UNAVAILABLE)
        self.assertFalse(res['safe_to_retry'])

    # ── 9. Provider Container ID Persisted Before Media Publish ─────────────
    @patch('social_stats.publishers.instagram.GraphClient')
    def test_provider_container_id_persisted_before_media_publish(self, mock_client_cls):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Container persistence test',
            target_platforms=['instagram'],
            media_type='image',
            media_urls=['https://cdn.bopsocial.com/test.jpg'],
            status='queued',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='pending',
        )

        mock_client = MagicMock()
        # 1st call: container creation -> returns container id
        # 2nd call: media publish -> simulate crash before response!
        def mock_post(url, *args, **kwargs):
            if '/media_publish' in url:
                # Prove container id was already persisted in the DB!
                log.refresh_from_db()
                self.assertEqual(log.provider_container_id, 'cid_persisted_early')
                raise PublishError('Simulated network timeout during media_publish')
            return {'id': 'cid_persisted_early'}

        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        # Execute publish_to_platform
        publish_to_platform(post.id, 'instagram')

        log.refresh_from_db()
        self.assertEqual(log.provider_container_id, 'cid_persisted_early')

    # ── 10. Platform Post ID Stored on Successful Publish ───────────────────
    @patch('social_stats.publishers.instagram.GraphClient')
    def test_platform_post_id_stored_on_successful_publish(self, mock_client_cls):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Successful publish post',
            target_platforms=['instagram'],
            media_type='image',
            media_urls=['https://cdn.bopsocial.com/test.jpg'],
            status='queued',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='pending',
        )

        mock_client = MagicMock()
        mock_client.post.side_effect = [
            {'id': 'cid_123'},          # Container
            {'id': 'ig_final_media_99'}, # Media publish
        ]
        mock_client.get.return_value = {'permalink': 'https://instagram.com/p/99'}
        mock_client_cls.return_value = mock_client

        publish_to_platform(post.id, 'instagram')

        log.refresh_from_db()
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'ig_final_media_99')
        self.assertEqual(log.provider_container_id, 'cid_123')

    # ── 11. Facebook Deterministic Evidence -> Confirmed Published ─────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_facebook_deterministic_object_id_confirms_published(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'id': 'fb_page_123_456', 'created_time': '2026-10-21T12:00:00+0000'}
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Facebook post with known ID',
            target_platforms=['facebook'],
            status='partial',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='publishing',
            platform_post_id='fb_page_123_456',
        )

        res = reconcile_platform_publication(post.id, 'facebook', user=self.user)
        self.assertEqual(res['outcome'], OUTCOME_CONFIRMED_PUBLISHED)
        self.assertEqual(res['provider_post_id'], 'fb_page_123_456')

    # ── 12 & 13. Facebook Heuristic Matching Strictly Forbidden ────────────
    def test_facebook_without_post_id_returns_reconciliation_unavailable(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Facebook post without ID',
            target_platforms=['facebook'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='publishing',
            platform_post_id='',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        res = reconcile_platform_publication(post.id, 'facebook', user=self.user)
        self.assertEqual(res['outcome'], OUTCOME_RECONCILIATION_UNAVAILABLE)
        self.assertFalse(res['safe_to_retry'])
        self.assertIn('Heuristic feed matching is blocked by safety policy', res['detail'])

    # ── 14. Facebook Provider Error -> Retry Blocked ───────────────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_facebook_provider_error_keeps_retry_blocked(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.side_effect = PublishError('Facebook 500 server error')
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='FB error post',
            target_platforms=['facebook'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='publishing',
            platform_post_id='fb_err_id',
        )

        res = reconcile_platform_publication(post.id, 'facebook', user=self.user)
        self.assertEqual(res['outcome'], OUTCOME_PROVIDER_ERROR)
        self.assertFalse(res['safe_to_retry'])

    # ── 15. Successful Reconciliation Recomputes UnifiedPost Status ────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_successful_reconciliation_recomputes_unified_post_status(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            {'status_code': 'FINISHED', 'id': 'cid_done'},
            {'data': [{'id': 'ig_done_111', 'caption': 'Multi post'}]},
        ]
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Multi post',
            target_platforms=['facebook', 'instagram'],
            status='partial',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='facebook',
            status='success',
            platform_post_id='fb_done_222',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_done',
            attempted_at=timezone.now() - timedelta(minutes=20),
        )

        reconcile_platform_publication(post.id, 'instagram', user=self.user)

        post.refresh_from_db()
        self.assertEqual(post.status, 'published')
        self.assertIsNotNone(post.published_at)

    # ── 16. Confirmed Not Published Exposes Platform Retry ─────────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_confirmed_not_published_exposes_retry_action(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'status_code': 'EXPIRED', 'id': 'cid_exp'}
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Expired post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_exp',
            attempted_at=timezone.now() - timedelta(minutes=25),
        )

        reconcile_platform_publication(post.id, 'instagram', user=self.user)

        log.refresh_from_db()
        self.assertEqual(log.status, 'failed')

        eval_res = classify_platform_target(post, 'instagram', log)
        self.assertEqual(eval_res['state'], PLATFORM_FAILED_RETRYABLE)
        self.assertTrue(eval_res['can_retry'])

    # ── 17 & 18. Still Processing & Unavailable Do Not Expose Retry ────────
    def test_still_processing_and_unavailable_do_not_expose_retry(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='In-flight post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            reconciliation_status=OUTCOME_STILL_PROCESSING,
            attempted_at=timezone.now() - timedelta(minutes=5),
        )

        eval_res = classify_platform_target(post, 'instagram', log)
        self.assertFalse(eval_res['can_retry'])

    # ── 19. Tenant Isolation ────────────────────────────────────────────────
    def test_reconciliation_tenant_isolation(self):
        post_b = UnifiedPost.objects.create(
            client=self.client_b,
            content='Client B post',
            target_platforms=['instagram'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post_b,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_b',
        )

        url = f'/api/social/publications/operations/{post_b.id}/reconcile/'
        res = self.api.post(url, {'platform': 'instagram'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── 20. Agency Scoped Access ────────────────────────────────────────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_reconciliation_agency_scoped_access(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'status_code': 'IN_PROGRESS', 'id': 'cid_agency'}
        mock_client_cls.return_value = mock_client

        agency = Agency.objects.create(
            name=f'Agency Rec {id(self)}',
            slug=f'agency-rec-{id(self)}',
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
            content='Agency reconciliation post',
            target_platforms=['instagram'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_agency',
        )

        url = f'/api/social/publications/operations/{post.id}/reconcile/'
        res = self.api.post(url, {'platform': 'instagram'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['outcome'], OUTCOME_STILL_PROCESSING)

    # ── 21. Approval Still Required Before Retry ────────────────────────────
    def test_approval_still_required_before_retry_after_reconciliation(self):
        self.client_a.requires_approval = True
        self.client_a.save()

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Requires approval post',
            target_platforms=['instagram'],
            status='publishing',
            approved_by=None,
            approved_at=None,
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='failed',
            reconciliation_status=OUTCOME_CONFIRMED_NOT_PUBLISHED,
        )

        # Evaluating target platform must show PLATFORM_BLOCKED due to approval requirement
        eval_res = classify_platform_target(post, 'instagram', log)
        self.assertEqual(eval_res['state'], 'PLATFORM_BLOCKED')
        self.assertFalse(eval_res['can_retry'])

        # Explicit retry fails
        retry_res = retry_failed_platform(post.id, 'instagram', user=self.user)
        self.assertFalse(retry_res['success'])
        self.assertIn('requires approval', retry_res['error'])

    # ── 22, 23 & 24. Audit Log Generated & No Secrets Serialized ───────────
    @patch('social_stats.reconciliation.GraphClient')
    def test_audit_log_generated_without_secrets(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get.return_value = {'status_code': 'IN_PROGRESS', 'id': 'cid_audit'}
        mock_client_cls.return_value = mock_client

        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Audit test post',
            target_platforms=['instagram'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_audit',
        )

        reconcile_platform_publication(post.id, 'instagram', user=self.user)

        audit = ActionLog.objects.filter(
            client=self.client_a,
            object_type='UnifiedPost',
            object_id=str(post.id),
            action='composer.platform_reconcile',
        ).first()

        self.assertIsNotNone(audit)
        self.assertEqual(audit.platform, 'instagram')

        audit_str = json.dumps(audit.details).lower()
        for secret_kw in ['token', 'secret', 'password', 'key', 'access_token']:
            self.assertNotIn(f'"{secret_kw}"', audit_str)

    # ── 25. Operations API Exposes Reconciliation State ─────────────────────
    def test_operations_api_exposes_reconciliation_state(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='API test post',
            target_platforms=['instagram'],
            status='publishing',
        )
        PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='cid_inspect',
            reconciliation_status=OUTCOME_CONFIRMED_NOT_PUBLISHED,
            reconciliation_evidence_type='meta_container_status',
            last_reconciled_at=timezone.now(),
        )

        url = f'/api/social/publications/operations/{post.id}/'
        res = self.api.get(url)
        self.assertEqual(res.status_code, 200)

        prog = res.data['platform_progress'][0]
        self.assertEqual(prog['reconciliation_status'], OUTCOME_CONFIRMED_NOT_PUBLISHED)
        self.assertEqual(prog['reconciliation_evidence_type'], 'meta_container_status')
        self.assertIsNotNone(prog['last_reconciled_at'])

    # ── 29. Legacy PlatformPublishLog Rows Remain Compatible ────────────────
    def test_legacy_rows_compatibility_with_reconciliation(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Legacy post',
            target_platforms=['instagram'],
            status='publishing',
        )
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform='instagram',
            status='publishing',
            provider_container_id='',
            reconciliation_status='',
        )

        now = timezone.now()
        eval_res = classify_platform_target(post, 'instagram', log, now)
        self.assertFalse(eval_res['can_retry'])

    # ── 30. Invalid Platform Rejected in Reconciliation Endpoint ────────────
    def test_invalid_platform_rejected(self):
        post = UnifiedPost.objects.create(
            client=self.client_a,
            content='Bad platform post',
            target_platforms=['instagram'],
            status='publishing',
        )
        url = f'/api/social/publications/operations/{post.id}/reconcile/'
        res = self.api.post(url, {'platform': 'tiktok'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('not targeted', res.data['detail'])
