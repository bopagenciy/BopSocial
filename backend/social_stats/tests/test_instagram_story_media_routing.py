"""
BS-3F.6C: Test suite for Instagram Story Media-Type Routing & Verification Hardening.

Covers:
1. explicit IMAGE routing
2. explicit VIDEO routing
3. signed MP4 URL fallback
4. signed JPEG URL fallback
5. unknown extension failure
6. image_url payload
7. video_url payload
8. image has zero polling
9. video invokes polling
10. caption omitted for image
11. caption omitted for video
12. image Story regression
13. video Story success
14. provider media type VIDEO verification
15. provider media type IMAGE verification
16. VIDEO -> IMAGE mismatch
17. IMAGE -> VIDEO mismatch
18. mismatch no automatic retry
19. exactly one media_publish on mismatch
20. orchestrator forwards image type
21. orchestrator forwards video type
22. Reel regression
23. Carousel regression
24. presigned URL exact defect regression
25. zero real Meta calls
"""
import urllib.parse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone

from social_stats.models import (
    Client, PlatformCredential, UnifiedPost, PlatformPublishLog, MediaAsset,
)
from social_stats.publishers import get_publisher, PublishError, PublishResult
from social_stats.orchestrator import publish_to_platform, _resolve_story_media_kind


def _fake_credential(**overrides):
    base = {
        'access_token':         'page-tok-12345',
        'page_id':              '100110011001',
        'instagram_account_id': '17841400000000000',
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _resp(status=200, json_body=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body or {}
    m.text = '{}'
    m.headers = {}
    return m


@patch('social_stats.publishers.instagram.time.sleep', lambda *_: None)
class InstagramStoryPublisherUnitTests(SimpleTestCase):
    """Publisher-level unit tests for Instagram Story routing & verification."""

    # 1. explicit IMAGE routing
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_01_explicit_image_routing(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-img'}),
            _resp(200, {'id': 'm-img'}),
            _resp(200, {'id': 'm-img', 'permalink': 'https://www.instagram.com/stories/user/1/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/asset.jpg', media_type='IMAGE')
        first_call = m.call_args_list[0].kwargs['data']
        self.assertEqual(first_call.get('media_type'), 'STORIES')
        self.assertEqual(first_call.get('image_url'), 'https://s3.amazonaws.com/bucket/asset.jpg')
        self.assertNotIn('video_url', first_call)
        self.assertTrue(res.success)
        self.assertEqual(res.error_code, '')

    # 2. explicit VIDEO routing
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_02_explicit_video_routing(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-vid'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm-vid'}),
            _resp(200, {'id': 'm-vid', 'permalink': 'https://www.instagram.com/stories/user/2/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/asset.mp4', media_type='VIDEO')
        first_call = m.call_args_list[0].kwargs['data']
        self.assertEqual(first_call.get('media_type'), 'STORIES')
        self.assertEqual(first_call.get('video_url'), 'https://s3.amazonaws.com/bucket/asset.mp4')
        self.assertNotIn('image_url', first_call)
        self.assertTrue(res.success)
        self.assertEqual(res.error_code, '')

    # 3. signed MP4 URL fallback
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_03_signed_mp4_url_fallback(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-s3-vid'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm-s3-vid'}),
            _resp(200, {'id': 'm-s3-vid', 'permalink': 'https://www.instagram.com/stories/user/3/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        s3_url = 'https://s3.amazonaws.com/bucket/clip.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=123'
        res = pub.publish_story(_fake_credential(), s3_url)
        first_call = m.call_args_list[0].kwargs['data']
        self.assertEqual(first_call.get('media_type'), 'STORIES')
        self.assertEqual(first_call.get('video_url'), s3_url)
        self.assertNotIn('image_url', first_call)
        self.assertTrue(res.success)

    # 4. signed JPEG URL fallback
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_04_signed_jpeg_url_fallback(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-s3-img'}),
            _resp(200, {'id': 'm-s3-img'}),
            _resp(200, {'id': 'm-s3-img', 'permalink': 'https://www.instagram.com/stories/user/4/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        s3_url = 'https://s3.amazonaws.com/bucket/photo.jpeg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=456'
        res = pub.publish_story(_fake_credential(), s3_url)
        first_call = m.call_args_list[0].kwargs['data']
        self.assertEqual(first_call.get('media_type'), 'STORIES')
        self.assertEqual(first_call.get('image_url'), s3_url)
        self.assertNotIn('video_url', first_call)
        self.assertTrue(res.success)

    # 5. unknown extension failure
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_05_unknown_extension_failure(self, m):
        pub = get_publisher('instagram')
        unknown_url = 'https://s3.amazonaws.com/bucket/document.pdf?X-Amz-Signature=789'
        with self.assertRaises(PublishError) as ctx:
            pub.publish_story(_fake_credential(), unknown_url)
        self.assertEqual(ctx.exception.code, 'unsupported_media_type')
        self.assertEqual(m.call_count, 0)

    # 6. image_url payload
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_06_image_url_payload(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c1'}),
            _resp(200, {'id': 'm1'}),
            _resp(200, {'id': 'm1', 'permalink': 'https://www.instagram.com/stories/user/6/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/pic.jpg', media_type='IMAGE')
        data = m.call_args_list[0].kwargs['data']
        self.assertIn('image_url', data)
        self.assertNotIn('video_url', data)
        self.assertNotIn('caption', data)
        self.assertNotIn('share_to_feed', data)

    # 7. video_url payload
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_07_video_url_payload(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c2'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm2'}),
            _resp(200, {'id': 'm2', 'permalink': 'https://www.instagram.com/stories/user/7/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/clip.mp4', media_type='VIDEO')
        data = m.call_args_list[0].kwargs['data']
        self.assertIn('video_url', data)
        self.assertNotIn('image_url', data)
        self.assertNotIn('caption', data)
        self.assertNotIn('share_to_feed', data)

    # 8. image has zero polling
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_08_image_has_zero_polling(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-img-nopoll'}),
            _resp(200, {'id': 'm-img-nopoll'}),
            _resp(200, {'id': 'm-img-nopoll', 'permalink': 'https://www.instagram.com/stories/user/8/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/pic.png', media_type='IMAGE')
        # Exactly 3 requests: POST /media, POST /media_publish, GET /{media_id}
        self.assertEqual(m.call_count, 3)

    # 9. video invokes polling
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_09_video_invokes_polling(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c-vid-poll'}),
            _resp(200, {'status_code': 'IN_PROGRESS'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm-vid-poll'}),
            _resp(200, {'id': 'm-vid-poll', 'permalink': 'https://www.instagram.com/stories/user/9/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/video.mp4', media_type='VIDEO')
        # 5 requests: POST /media, GET poll 1, GET poll 2, POST /media_publish, GET /{media_id}
        self.assertEqual(m.call_count, 5)

    # 10. caption omitted for image
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_10_caption_omitted_for_image(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c10'}),
            _resp(200, {'id': 'm10'}),
            _resp(200, {'id': 'm10', 'permalink': 'https://www.instagram.com/stories/user/10/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/pic.jpg', caption='Should be ignored', media_type='IMAGE')
        data = m.call_args_list[0].kwargs['data']
        self.assertNotIn('caption', data)

    # 11. caption omitted for video
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_11_caption_omitted_for_video(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c11'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm11'}),
            _resp(200, {'id': 'm11', 'permalink': 'https://www.instagram.com/stories/user/11/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/v.mp4', caption='Ignore video caption', media_type='VIDEO')
        data = m.call_args_list[0].kwargs['data']
        self.assertNotIn('caption', data)

    # 12. image Story regression
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_12_image_story_regression(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c12'}),
            _resp(200, {'id': 'm12'}),
            _resp(200, {'id': 'm12', 'permalink': 'https://www.instagram.com/stories/user/12/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/image.jpg', media_kind='IMAGE')
        self.assertTrue(res.success)
        self.assertEqual(res.platform_post_id, 'm12')
        self.assertEqual(res.error_code, '')

    # 13. video Story success
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_13_video_story_success(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c13'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm13'}),
            _resp(200, {'id': 'm13', 'permalink': 'https://www.instagram.com/stories/user/13/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/video.mp4', media_kind='VIDEO')
        self.assertTrue(res.success)
        self.assertEqual(res.platform_post_id, 'm13')
        self.assertEqual(res.error_code, '')

    # 14. provider media type VIDEO verification
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_14_provider_media_type_video_verification(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c14'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm14'}),
            _resp(200, {'id': 'm14', 'permalink': 'https://www.instagram.com/stories/user/14/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/v.mp4', media_type='VIDEO')
        self.assertEqual(res.error_code, '')
        self.assertNotIn('mismatch', res.raw_response)

    # 15. provider media type IMAGE verification
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_15_provider_media_type_image_verification(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c15'}),
            _resp(200, {'id': 'm15'}),
            _resp(200, {'id': 'm15', 'permalink': 'https://www.instagram.com/stories/user/15/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/img.jpg', media_type='IMAGE')
        self.assertEqual(res.error_code, '')
        self.assertNotIn('mismatch', res.raw_response)

    # 16. VIDEO -> IMAGE mismatch
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_16_video_to_image_mismatch(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c16'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm16'}),
            _resp(200, {'id': 'm16', 'permalink': 'https://www.instagram.com/stories/user/16/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/v.mp4', media_type='VIDEO')
        self.assertTrue(res.success)
        self.assertEqual(res.error_code, 'provider_media_type_mismatch')
        self.assertIn('IMAGE', res.error_message)
        self.assertIn('VIDEO', res.error_message)
        self.assertTrue(res.raw_response.get('mismatch'))
        self.assertEqual(res.raw_response.get('expected_media_type'), 'VIDEO')
        self.assertEqual(res.raw_response.get('provider_media_type'), 'IMAGE')

    # 17. IMAGE -> VIDEO mismatch
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_17_image_to_video_mismatch(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c17'}),
            _resp(200, {'id': 'm17'}),
            _resp(200, {'id': 'm17', 'permalink': 'https://www.instagram.com/stories/user/17/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/img.png', media_type='IMAGE')
        self.assertTrue(res.success)
        self.assertEqual(res.error_code, 'provider_media_type_mismatch')
        self.assertIn('VIDEO', res.error_message)
        self.assertIn('IMAGE', res.error_message)
        self.assertTrue(res.raw_response.get('mismatch'))
        self.assertEqual(res.raw_response.get('expected_media_type'), 'IMAGE')
        self.assertEqual(res.raw_response.get('provider_media_type'), 'VIDEO')

    # 19. exactly one media_publish on mismatch
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_19_exactly_one_media_publish_on_mismatch(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c19'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm19'}),
            _resp(200, {'id': 'm19', 'permalink': 'https://www.instagram.com/stories/user/19/', 'media_type': 'IMAGE', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://s3.amazonaws.com/bucket/v.mp4', media_type='VIDEO')
        publish_calls = [c for c in m.call_args_list if '/media_publish' in (c.args[1] if len(c.args) > 1 else c.kwargs.get('url', ''))]
        self.assertEqual(len(publish_calls), 1)

    # 22. Reel regression
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_22_reel_regression(self, m):
        m.side_effect = [
            _resp(200, {'id': 'reel-c'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'reel-m'}),
            _resp(200, {'id': 'reel-m', 'permalink': 'https://www.instagram.com/reel/1/', 'media_type': 'VIDEO', 'media_product_type': 'REELS'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_reel(_fake_credential(), 'https://s3.amazonaws.com/bucket/reel.mp4', 'Great reel')
        first_call = m.call_args_list[0].kwargs['data']
        self.assertEqual(first_call.get('media_type'), 'REELS')
        self.assertEqual(first_call.get('video_url'), 'https://s3.amazonaws.com/bucket/reel.mp4')
        self.assertEqual(first_call.get('caption'), 'Great reel')
        self.assertTrue(res.success)
        self.assertEqual(res.platform_post_id, 'reel-m')

    # 23. Carousel regression
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_23_carousel_regression(self, m):
        m.side_effect = [
            _resp(200, {'id': 'child-1'}),
            _resp(200, {'id': 'child-2'}),
            _resp(200, {'id': 'carousel-p'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'carousel-m'}),
            _resp(200, {'id': 'carousel-m', 'permalink': 'https://www.instagram.com/p/1/'}),
        ]
        pub = get_publisher('instagram')
        res = pub.publish_carousel(_fake_credential(), 'Carousel text', ['https://s3.amazonaws.com/bucket/1.jpg', 'https://s3.amazonaws.com/bucket/2.jpg'])
        self.assertTrue(res.success)
        self.assertEqual(res.platform_post_id, 'carousel-m')

    # 24. presigned URL exact defect regression
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_24_presigned_url_exact_defect_regression(self, m):
        m.side_effect = [
            _resp(200, {'id': 'c24'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'm24'}),
            _resp(200, {'id': 'm24', 'permalink': 'https://www.instagram.com/stories/user/24/', 'media_type': 'VIDEO', 'media_product_type': 'STORY'}),
        ]
        pub = get_publisher('instagram')
        s3_url = (
            'https://bopsocial-staging-media.s3.amazonaws.com/media_assets/tenant_3/2026/10/'
            'bopsocial5_ab7d8cff.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIAYE6R6SGVBLCXGOQ2'
            '%2F20261020%2Fus-east-2%2Fs3%2Faws4_request&X-Amz-Date=20261020T035619Z&X-Amz-Expires=3600'
            '&X-Amz-SignedHeaders=host&X-Amz-Signature=097ed7da5fde5807497a68f466a5410c4c6a9863917cad19ea21948eda20ee2b'
        )
        res = pub.publish_story(_fake_credential(), s3_url)
        data = m.call_args_list[0].kwargs['data']
        self.assertEqual(data.get('media_type'), 'STORIES')
        self.assertEqual(data.get('video_url'), s3_url)
        self.assertNotIn('image_url', data)
        self.assertTrue(res.success)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class InstagramStoryOrchestratorIntegrationTests(TestCase):
    """Orchestrator-level integration tests for Story MIME routing and mismatch handling."""

    def setUp(self):
        self.client_obj = Client.objects.create(
            name='Test Client', company='Test Co', email=f'test-{id(self)}@co.test',
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_obj,
            platform='instagram',
            access_token='tok-ig-999',
            page_id='100',
            instagram_account_id='17841499999999999',
            is_active=True,
        )

    # 18. mismatch no automatic retry
    @patch('social_stats.media_service.get_provider_media_url', return_value='https://s3.amazonaws.com/b/v.mp4')
    @patch('social_stats.publishers.instagram.InstagramPublisher.publish_story')
    def test_18_mismatch_no_automatic_retry(self, mock_pub, mock_url):
        mock_pub.return_value = PublishResult(
            success=True,
            platform_post_id='media-mismatch-18',
            platform_url='https://ig/story/18',
            error_code='provider_media_type_mismatch',
            error_message='Instagram published media media-mismatch-18 as IMAGE, expected VIDEO',
            raw_response={'mismatch': True, 'expected_media_type': 'VIDEO', 'provider_media_type': 'IMAGE'},
        )
        asset = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=1000,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            media_type='story',
            target_platforms=['instagram'],
            media_urls=[f'asset:{asset.id}'],
            status='publishing',
        )
        post.media_assets.add(asset)

        publish_to_platform(post.id, 'instagram')

        post.refresh_from_db()
        log = PlatformPublishLog.objects.get(unified_post=post, platform='instagram')

        # Invariant: status is 'published' so no auto-retry occurs
        self.assertEqual(post.status, 'published')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.platform_post_id, 'media-mismatch-18')
        self.assertEqual(log.error_code, 'provider_media_type_mismatch')
        self.assertIn('expected VIDEO', log.error_message)

    # 20. orchestrator forwards image type
    @patch('social_stats.media_service.get_provider_media_url', return_value='https://s3.amazonaws.com/b/img.png')
    @patch('social_stats.publishers.instagram.InstagramPublisher.publish_story')
    def test_20_orchestrator_forwards_image_type(self, mock_pub, mock_url):
        mock_pub.return_value = PublishResult(
            success=True, platform_post_id='img-ok', platform_url='https://ig/story/20',
        )
        asset = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/png',
            file_size=500,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            media_type='story',
            target_platforms=['instagram'],
            media_urls=[f'asset:{asset.id}'],
            status='publishing',
        )
        post.media_assets.add(asset)

        publish_to_platform(post.id, 'instagram')
        mock_pub.assert_called_once()
        kwargs = mock_pub.call_args.kwargs
        self.assertEqual(kwargs.get('media_type'), 'IMAGE')
        self.assertEqual(kwargs.get('media_kind'), 'IMAGE')

    # 21. orchestrator forwards video type
    @patch('social_stats.media_service.get_provider_media_url', return_value='https://s3.amazonaws.com/b/vid.mp4')
    @patch('social_stats.publishers.instagram.InstagramPublisher.publish_story')
    def test_21_orchestrator_forwards_video_type(self, mock_pub, mock_url):
        mock_pub.return_value = PublishResult(
            success=True, platform_post_id='vid-ok', platform_url='https://ig/story/21',
        )
        asset = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5000,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            media_type='story',
            target_platforms=['instagram'],
            media_urls=[f'asset:{asset.id}'],
            status='publishing',
        )
        post.media_assets.add(asset)

        publish_to_platform(post.id, 'instagram')
        mock_pub.assert_called_once()
        kwargs = mock_pub.call_args.kwargs
        self.assertEqual(kwargs.get('media_type'), 'VIDEO')
        self.assertEqual(kwargs.get('media_kind'), 'VIDEO')

    # Helper tests for _resolve_story_media_kind
    def test_resolve_story_media_kind_unsupported_mime(self):
        asset = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='application/zip',
            file_size=500,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            media_type='story',
            target_platforms=['instagram'],
            media_urls=[f'asset:{asset.id}'],
        )
        post.media_assets.add(asset)
        with self.assertRaises(PublishError) as ctx:
            _resolve_story_media_kind(post, [f'asset:{asset.id}'])
        self.assertEqual(ctx.exception.code, 'unsupported_media_type')

    def test_resolve_story_media_kind_zero_media(self):
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            media_type='story',
            target_platforms=['instagram'],
            media_urls=[],
        )
        with self.assertRaises(PublishError) as ctx:
            _resolve_story_media_kind(post, [])
        self.assertEqual(ctx.exception.code, 'missing_media')

    # 25. zero real Meta calls is guaranteed by mocking in all tests above.
