import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from social_stats.models import Client, PlatformCredential, DailyMetric, PostMetric, SyncLog
from social_stats.tasks import sync_instagram, _has_instagram_insights_capability
from social_stats.serializers import PlatformCredentialSerializer


def _mock_response(status_code=200, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else {}
    return mock


class InstagramAnalyticsResilienceTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name=f"Client-{uuid.uuid4().hex[:6]}",
            company="Test Agency",
            email=f"client-{uuid.uuid4().hex[:6]}@agency.test"
        )

    def _create_credential(self, scope, is_active=True, ig_account_id="ig_user_17841464843082253"):
        return PlatformCredential.objects.create(
            client=self.client_obj,
            platform="instagram",
            instagram_account_id=ig_account_id,
            page_id="fb_page_657647337668646",
            page_name="Bo Projects",
            access_token="mock_valid_ig_token_xyz",
            is_active=is_active,
            scope=scope
        )

    # -------------------------------------------------------------------------
    # CASE 1: Capability helper returns False without instagram_manage_insights
    # -------------------------------------------------------------------------
    def test_case_1_capability_helper_without_insights_scope(self):
        cred = self._create_credential(
            scope="read_insights, instagram_basic, instagram_content_publish, pages_show_list, business_management, pages_read_engagement"
        )
        self.assertFalse(_has_instagram_insights_capability(cred))

    # -------------------------------------------------------------------------
    # CASE 2: Capability helper returns True with instagram_manage_insights
    # -------------------------------------------------------------------------
    def test_case_2_capability_helper_with_insights_scope(self):
        cred = self._create_credential(
            scope="read_insights, instagram_basic, instagram_manage_insights, instagram_content_publish"
        )
        self.assertTrue(_has_instagram_insights_capability(cred))

    # -------------------------------------------------------------------------
    # CASE 3: Sync without insights scope skips insights calls, saves media, partial status
    # -------------------------------------------------------------------------
    @patch('requests.get')
    def test_case_3_sync_without_insights_scope_degrades_gracefully(self, mock_get):
        cred = self._create_credential(
            scope="read_insights, instagram_basic, instagram_content_publish, pages_show_list, business_management, pages_read_engagement"
        )

        def get_router(url, params=None, timeout=None):
            if f"/{cred.instagram_account_id}/media" in url:
                return _mock_response(200, {'data': [
                    {
                        'id': '17991627227860965',
                        'caption': 'Test pilot image',
                        'media_type': 'IMAGE',
                        'permalink': 'https://www.instagram.com/p/Derx_mjEb62/',
                        'timestamp': '2026-10-18T20:00:00+0000',
                        'media_url': 'https://scontent.cdninstagram.com/test.jpg'
                    }
                ]})
            elif "/17991627227860965" in url and "insights" not in url:
                return _mock_response(200, {
                    'like_count': 12,
                    'comments_count': 3
                })
            elif "/insights" in url:
                # Should NOT be reached in degraded mode
                raise AssertionError(f"Unexpected call to insights endpoint: {url}")
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_instagram(self.client_obj.id, days=30)

        # In degraded mode:
        # 1. DailyMetric should be 0 (no fake zeroes created)
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj, platform='instagram').count(), 0)

        # 2. PostMetric should be 1 with public likes/comments
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj, platform='instagram').count(), 1)
        pm = PostMetric.objects.get(client=self.client_obj, platform='instagram')
        self.assertEqual(pm.post_id, '17991627227860965')
        self.assertEqual(pm.likes, 12)
        self.assertEqual(pm.comments, 3)
        self.assertEqual(pm.reach, 0)
        self.assertEqual(pm.impressions, 0)

        # 3. SyncLog should be partial, records_synced=1, truthful warning
        log = SyncLog.objects.filter(client=self.client_obj, platform='instagram').latest('started_at')
        self.assertEqual(log.status, 'partial')
        self.assertEqual(log.records_synced, 1)
        self.assertIn("Instagram advanced insights unavailable for current credential", log.error_message)

    # -------------------------------------------------------------------------
    # CASE 4: Sync with insights scope calls insights and creates DailyMetric + PostMetric
    # -------------------------------------------------------------------------
    @patch('requests.get')
    def test_case_4_sync_with_insights_scope_full_success(self, mock_get):
        cred = self._create_credential(
            scope="instagram_manage_insights, instagram_basic"
        )

        def get_router(url, params=None, timeout=None):
            if f"/{cred.instagram_account_id}/insights" in url:
                metric = params.get('metric', '')
                if 'reach,follower_count' in metric:
                    return _mock_response(200, {'data': [
                        {'name': 'reach', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 150}]},
                        {'name': 'follower_count', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 320}]},
                    ]})
                elif 'profile_views' in metric:
                    return _mock_response(200, {'data': [
                        {'name': 'profile_views', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 45}]},
                    ]})
            elif f"/{cred.instagram_account_id}/media" in url:
                return _mock_response(200, {'data': [
                    {
                        'id': 'ig_media_201',
                        'caption': 'Full insights media',
                        'media_type': 'IMAGE',
                        'permalink': 'https://www.instagram.com/p/ABC123xyz/',
                        'timestamp': '2026-10-18T10:00:00+0000',
                    }
                ]})
            elif "/ig_media_201/insights" in url:
                return _mock_response(200, {'data': [
                    {'name': 'reach', 'values': [{'value': 85}]},
                    {'name': 'saved', 'values': [{'value': 7}]},
                    {'name': 'shares', 'values': [{'value': 4}]},
                ]})
            elif "/ig_media_201" in url:
                return _mock_response(200, {
                    'like_count': 25,
                    'comments_count': 5
                })
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_instagram(self.client_obj.id, days=30)

        # 1. DailyMetric created
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj, platform='instagram').count(), 1)
        dm = DailyMetric.objects.get(client=self.client_obj, platform='instagram')
        self.assertEqual(dm.reach, 150)
        self.assertEqual(dm.followers, 320)
        self.assertEqual(dm.profile_views, 45)

        # 2. PostMetric created with media insights
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj, platform='instagram').count(), 1)
        pm = PostMetric.objects.get(client=self.client_obj, platform='instagram')
        self.assertEqual(pm.reach, 85)
        self.assertEqual(pm.saves, 7)
        self.assertEqual(pm.shares, 4)
        self.assertEqual(pm.likes, 25)

        # 3. SyncLog status success, records_synced = 1 + 1 = 2
        log = SyncLog.objects.filter(client=self.client_obj, platform='instagram').latest('started_at')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.records_synced, 2)
        self.assertEqual(log.error_message, '')

    # -------------------------------------------------------------------------
    # CASE 5: Per-post like/comment call failure does not drop post record
    # -------------------------------------------------------------------------
    @patch('requests.get')
    def test_case_5_post_detail_failure_still_records_post(self, mock_get):
        cred = self._create_credential(scope="instagram_basic")

        def get_router(url, params=None, timeout=None):
            if f"/{cred.instagram_account_id}/media" in url:
                return _mock_response(200, {'data': [
                    {
                        'id': 'ig_media_fail_detail',
                        'caption': 'Post with detail error',
                        'media_type': 'IMAGE',
                        'permalink': 'https://www.instagram.com/p/FAIL123/',
                        'timestamp': '2026-10-18T10:00:00+0000',
                    }
                ]})
            elif "/ig_media_fail_detail" in url:
                # Detail call fails
                return _mock_response(500, {'error': {'message': 'Temporary internal error'}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_instagram(self.client_obj.id, days=30)

        # Post is still saved with defaults (0 likes, 0 comments)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj, platform='instagram').count(), 1)
        pm = PostMetric.objects.get(client=self.client_obj, platform='instagram')
        self.assertEqual(pm.post_id, 'ig_media_fail_detail')
        self.assertEqual(pm.likes, 0)
        self.assertEqual(pm.comments, 0)

    # -------------------------------------------------------------------------
    # CASE 6: Media fetch HTTP error sets status partial or failed gracefully
    # -------------------------------------------------------------------------
    @patch('requests.get')
    def test_case_6_media_fetch_error_marks_failed_if_no_records(self, mock_get):
        cred = self._create_credential(scope="instagram_basic")

        def get_router(url, params=None, timeout=None):
            if f"/{cred.instagram_account_id}/media" in url:
                return _mock_response(400, {'error': {'message': 'OAuthException: Session expired', 'code': 190}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_instagram(self.client_obj.id, days=30)

        log = SyncLog.objects.filter(client=self.client_obj, platform='instagram').latest('started_at')
        self.assertEqual(log.status, 'failed')
        self.assertEqual(log.records_synced, 0)
        self.assertIn("Media fetch failed", log.error_message)

    # -------------------------------------------------------------------------
    # CASE 7: Missing credential raises retry and logs failed
    # -------------------------------------------------------------------------
    def test_case_7_missing_credential_raises(self):
        other_client = Client.objects.create(name="NoCred Client", email=f"nocred-{uuid.uuid4().hex[:6]}@agency.test")
        with self.assertRaises(Exception):
            sync_instagram(other_client.id, days=30)

        log = SyncLog.objects.filter(client=other_client, platform='instagram').latest('started_at')
        self.assertEqual(log.status, 'failed')
        self.assertIn("does not exist", log.error_message.lower())

    # -------------------------------------------------------------------------
    # CASE 8: Redaction of access token in error message
    # -------------------------------------------------------------------------
    def test_case_8_access_token_redacted_on_exception(self):
        secret_token = "SECRET_TOKEN_999888777"
        cred = self._create_credential(scope="instagram_manage_insights")
        cred.access_token = secret_token
        cred.save()

        # Let _date_range raise an unhandled exception that includes secret_token
        with patch('social_stats.tasks._date_range', side_effect=RuntimeError(f"Critical failure with {secret_token}")):
            with self.assertRaises(Exception):
                sync_instagram(self.client_obj.id, days=30)

        log = SyncLog.objects.filter(client=self.client_obj, platform='instagram').latest('started_at')
        self.assertEqual(log.status, 'failed')
        self.assertNotIn(secret_token, log.error_message)
        self.assertIn("[REDACTED]", log.error_message)

    # -------------------------------------------------------------------------
    # CASE 9: PlatformCredentialSerializer analytics_level field
    # -------------------------------------------------------------------------
    def test_case_9_serializer_analytics_level(self):
        client2 = Client.objects.create(
            name=f"Client2-{uuid.uuid4().hex[:6]}",
            company="Agency Two",
            email=f"client2-{uuid.uuid4().hex[:6]}@agency.test"
        )
        basic_cred = self._create_credential(
            scope="read_insights, instagram_basic, instagram_content_publish"
        )
        adv_cred = PlatformCredential.objects.create(
            client=client2,
            platform="instagram",
            instagram_account_id="ig_user_adv_123",
            access_token="tok_adv",
            is_active=True,
            scope="read_insights, instagram_manage_insights, instagram_basic"
        )

        basic_data = PlatformCredentialSerializer(basic_cred).data
        self.assertEqual(basic_data['analytics_level'], 'basic')

        adv_data = PlatformCredentialSerializer(adv_cred).data
        self.assertEqual(adv_data['analytics_level'], 'advanced')

    # -------------------------------------------------------------------------
    # CASE 10: Client summary endpoint capabilities structure
    # -------------------------------------------------------------------------
    def test_case_10_client_summary_capabilities(self):
        self._create_credential(
            scope="read_insights, instagram_basic, instagram_content_publish"
        )
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            page_id="fb_page_123",
            access_token="fb_token",
            is_active=True,
            scope="read_insights, pages_show_list"
        )

        from rest_framework.test import APIRequestFactory
        from social_stats.views import ClientViewSet
        from social_stats.models import UserProfile
        from django.contrib.auth.models import User

        user = User.objects.create_superuser(username=f"admin_{uuid.uuid4().hex[:6]}", email="admin@test.com", password="password")
        UserProfile.objects.create(user=user, role='superadmin')

        factory = APIRequestFactory()
        view = ClientViewSet.as_view({'get': 'summary'})

        request = factory.get(f'/api/clients/{self.client_obj.id}/summary/')
        from rest_framework.test import force_authenticate
        force_authenticate(request, user=user)

        response = view(request, pk=self.client_obj.id)
        self.assertEqual(response.status_code, 200)
        caps = response.data.get('capabilities', {})

        self.assertIn('instagram', caps)
        self.assertEqual(caps['instagram']['analytics_level'], 'basic')
        self.assertFalse(caps['instagram']['supports_timeseries'])
        self.assertTrue(caps['instagram']['supports_media_metrics'])
        self.assertIn('instagram_manage_insights', caps['instagram']['reason'])

        self.assertIn('facebook', caps)
        self.assertEqual(caps['facebook']['analytics_level'], 'advanced')
        self.assertTrue(caps['facebook']['supports_timeseries'])
