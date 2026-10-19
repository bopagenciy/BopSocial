import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from social_stats.models import Client, PlatformCredential, DailyMetric, PostMetric, SyncLog
from social_stats.tasks import sync_facebook


def _mock_response(status_code=200, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else {}
    return mock


class FacebookAnalyticsResilienceTests(TestCase):
    def setUp(self):
        self.client_obj = Client.objects.create(
            name=f"Client-{uuid.uuid4().hex[:6]}",
            company="Test Agency",
            email=f"client-{uuid.uuid4().hex[:6]}@agency.test"
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform="facebook",
            page_id="fb_page_12345",
            page_name="Test FB Page",
            access_token="mock_valid_token_xyz",
            is_active=True,
            scope="read_insights,pages_read_engagement,pages_manage_posts,pages_show_list"
        )

    @patch('requests.post')
    @patch('requests.get')
    def test_case_1_all_metrics_valid_success(self, mock_get, mock_post):
        """CASE 1: All page metrics valid -> DailyMetric, PostMetric, SyncLog success."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': [{'name': 'page_actions_post_reactions_total', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': {'like': 3, 'love': 1}}]}]})
                return _mock_response(200, {'data': [
                    {'name': 'page_post_engagements', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 12}]},
                    {'name': 'page_views_total', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 30}]},
                ]})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': [
                    {'id': 'fb_post_101', 'message': 'Pilot post #1', 'created_time': '2026-10-18T08:00:00+0000', 'permalink_url': 'https://facebook.com/p101'}
                ]})
            elif "/fb_post_101/insights" in url:
                return _mock_response(200, {'data': [
                    {'name': 'post_impressions_unique', 'values': [{'value': 50}]},
                    {'name': 'post_clicks', 'values': [{'value': 8}]}
                ]})
            elif "/fb_post_101" in url:
                return _mock_response(200, {
                    'reactions': {'summary': {'total_count': 10}},
                    'comments': {'summary': {'total_count': 4}},
                    'shares': {'count': 2}
                })
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        dm = DailyMetric.objects.get(client=self.client_obj)
        self.assertEqual(dm.likes, 12)
        self.assertEqual(dm.profile_views, 30)
        self.assertEqual(dm.reactions.get('like'), 3)

        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)
        pm = PostMetric.objects.get(client=self.client_obj)
        self.assertEqual(pm.post_id, 'fb_post_101')
        self.assertEqual(pm.impressions, 50)
        self.assertEqual(pm.likes, 10)

        log = SyncLog.objects.filter(client=self.client_obj).latest('started_at')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.records_synced, 2)  # 1 daily + 1 post
        self.assertEqual(log.error_message, '')
        mock_post.assert_not_called()

    @patch('requests.get')
    def test_case_2_invalid_page_metric_fallback_partial(self, mock_get):
        """CASE 2: One deprecated/invalid metric in batch -> fallback saves valid metrics, status partial."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if ',' in metric:
                    # Batch call fails with invalid metric error
                    return _mock_response(400, {'error': {'message': '(#100) The value must be a valid insights metric', 'code': 100}})
                elif metric == 'page_post_engagements':
                    return _mock_response(200, {'data': [{'name': 'page_post_engagements', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 20}]}]})
                elif metric == 'page_views_total':
                    return _mock_response(400, {'error': {'message': 'Invalid metric deprecated'}})
                elif 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': []})
                else:
                    return _mock_response(200, {'data': []})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': [
                    {'id': 'fb_post_202', 'message': 'Post 202', 'created_time': '2026-10-18T09:00:00+0000', 'permalink_url': 'https://facebook.com/p202'}
                ]})
            elif "/fb_post_202/insights" in url:
                return _mock_response(200, {'data': [{'name': 'post_impressions_unique', 'values': [{'value': 75}]}]})
            elif "/fb_post_202" in url:
                return _mock_response(200, {'reactions': {'summary': {'total_count': 5}}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        # Valid page metric was preserved via fallback!
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        dm = DailyMetric.objects.get(client=self.client_obj)
        self.assertEqual(dm.likes, 20)

        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)

        log = SyncLog.objects.filter(client=self.client_obj).latest('started_at')
        self.assertEqual(log.status, 'partial')
        self.assertEqual(log.records_synced, 2)
        self.assertIn("unavailable", log.error_message)

    @patch('requests.get')
    def test_case_3_page_insights_fail_posts_succeed_partial(self, mock_get):
        """CASE 3: Page insights fail completely, but post metrics succeed -> partial with records_synced > 0."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                return _mock_response(400, {'error': {'message': 'Page insights completely forbidden', 'code': 200}})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': [
                    {'id': 'fb_post_303', 'message': 'Post 303', 'created_time': '2026-10-18T10:00:00+0000'}
                ]})
            elif "/fb_post_303/insights" in url:
                return _mock_response(200, {'data': [{'name': 'post_impressions_unique', 'values': [{'value': 10}]}]})
            elif "/fb_post_303" in url:
                return _mock_response(200, {'reactions': {'summary': {'total_count': 1}}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 0)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)

        log = SyncLog.objects.filter(client=self.client_obj).latest('started_at')
        self.assertEqual(log.status, 'partial')
        self.assertEqual(log.records_synced, 1)
        self.assertIn("forbidden", log.error_message)

    @patch('requests.get')
    def test_case_4_posts_fail_page_insights_succeed_partial(self, mock_get):
        """CASE 4: Posts listing fails, but page daily insights succeed -> partial."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': []})
                return _mock_response(200, {'data': [
                    {'name': 'page_post_engagements', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 8}]}
                ]})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(500, {'error': {'message': 'Internal Server Error'}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 0)

        log = SyncLog.objects.filter(client=self.client_obj).latest('started_at')
        self.assertEqual(log.status, 'partial')
        self.assertEqual(log.records_synced, 1)
        self.assertIn("Post listing failed", log.error_message)

    @patch('requests.get')
    def test_case_5_everything_fails_error(self, mock_get):
        """CASE 5: Everything fails -> status failed, records_synced 0."""
        def get_router(url, params=None, timeout=None):
            return _mock_response(500, {'error': {'message': 'Fatal provider breakdown'}})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 0)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 0)

        log = SyncLog.objects.filter(client=self.client_obj).latest('started_at')
        self.assertEqual(log.status, 'failed')
        self.assertEqual(log.records_synced, 0)
        self.assertIn("Fatal provider breakdown", log.error_message)

    @patch('requests.get')
    def test_case_6_idempotency_second_sync(self, mock_get):
        """CASE 6: Second identical sync updates existing records, no duplicates."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': []})
                return _mock_response(200, {'data': [
                    {'name': 'page_post_engagements', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 10}]}
                ]})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': [
                    {'id': 'post_idempotent_1', 'message': 'p1', 'created_time': '2026-10-18T08:00:00+0000'}
                ]})
            elif "/post_idempotent_1/insights" in url:
                return _mock_response(200, {'data': [{'name': 'post_impressions_unique', 'values': [{'value': 10}]}]})
            elif "/post_idempotent_1" in url:
                return _mock_response(200, {'reactions': {'summary': {'total_count': 1}}})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        # Sync 1
        sync_facebook(self.client_obj.id, days=30)
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)

        # Sync 2
        sync_facebook(self.client_obj.id, days=30)
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)

    @patch('requests.get')
    def test_case_7_client_isolation(self, mock_get):
        """CASE 7: Syncing client A does not create or modify data for client B."""
        client_b = Client.objects.create(
            name="Client-B",
            company="Other Co",
            email=f"b-{uuid.uuid4().hex[:6]}@test.local"
        )
        PlatformCredential.objects.create(
            client=client_b,
            platform="facebook",
            page_id="page_b_999",
            access_token="tok_b",
            is_active=True
        )

        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': []})
                return _mock_response(200, {'data': [
                    {'name': 'page_post_engagements', 'values': [{'end_time': '2026-10-18T07:00:00+0000', 'value': 5}]}
                ]})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': [{'id': 'post_a_1', 'message': 'A post', 'created_time': '2026-10-18T08:00:00+0000'}]})
            elif "/post_a_1" in url:
                return _mock_response(200, {})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        # Client A received data
        self.assertEqual(DailyMetric.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(PostMetric.objects.filter(client=self.client_obj).count(), 1)
        self.assertEqual(SyncLog.objects.filter(client=self.client_obj).count(), 1)

        # Client B has zero data
        self.assertEqual(DailyMetric.objects.filter(client=client_b).count(), 0)
        self.assertEqual(PostMetric.objects.filter(client=client_b).count(), 0)
        self.assertEqual(SyncLog.objects.filter(client=client_b).count(), 0)

    @patch('requests.delete')
    @patch('requests.patch')
    @patch('requests.put')
    @patch('requests.post')
    @patch('requests.get')
    def test_case_8_no_meta_write_calls(self, mock_get, mock_post, mock_put, mock_patch, mock_delete):
        """CASE 8: Sync task strictly performs GET requests; zero write calls."""
        def get_router(url, params=None, timeout=None):
            if f"/{self.cred.page_id}/insights" in url:
                metric = params.get('metric', '')
                if 'page_actions_post_reactions_total' in metric:
                    return _mock_response(200, {'data': []})
                return _mock_response(200, {'data': []})
            elif f"/{self.cred.page_id}/posts" in url:
                return _mock_response(200, {'data': []})
            return _mock_response(404, {})

        mock_get.side_effect = get_router

        sync_facebook(self.client_obj.id, days=30)

        mock_post.assert_not_called()
        mock_put.assert_not_called()
        mock_patch.assert_not_called()
        mock_delete.assert_not_called()
        self.assertTrue(mock_get.called)
