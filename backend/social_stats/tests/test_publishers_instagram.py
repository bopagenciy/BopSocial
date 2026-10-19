"""
Unit tests for InstagramPublisher.

The 2-step container API + readiness polling is the trickiest piece, so we
mock both the HTTP layer and `time.sleep` so polling completes instantly.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from social_stats.publishers import (
    get_publisher, PublishError, TokenExpiredError, RateLimitError,
)


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
class InstagramPublisherTests(SimpleTestCase):
    # ── Single image ─────────────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_image_single(self, m):
        m.side_effect = [
            _resp(200, {'id': 'container-1'}),
            _resp(200, {'id': 'media-1'}),
            _resp(200, {'id': 'media-1', 'permalink': 'https://www.instagram.com/p/SHORTCODE1/'}),
        ]
        pub = get_publisher('instagram')
        result = pub.publish_image(_fake_credential(), 'caption!',
                                   ['https://x/img.jpg'])

        # 3 calls: create container, publish container, get permalink
        self.assertEqual(m.call_count, 3)
        first, second, third = m.call_args_list

        # Step 1: container with image_url
        self.assertIn('/17841400000000000/media', first.kwargs['url'])
        self.assertEqual(first.kwargs['data']['image_url'], 'https://x/img.jpg')
        self.assertEqual(first.kwargs['data']['caption'], 'caption!')

        # Step 2: media_publish with creation_id
        self.assertIn('/17841400000000000/media_publish', second.kwargs['url'])
        self.assertEqual(second.kwargs['data']['creation_id'], 'container-1')

        # Step 3: GET permalink
        self.assertIn('/media-1', third.kwargs['url'])
        self.assertEqual(third.kwargs['params']['fields'], 'permalink')

        self.assertTrue(result.success)
        self.assertEqual(result.platform_post_id, 'media-1')
        self.assertEqual(result.platform_url, 'https://www.instagram.com/p/SHORTCODE1/')

    # ── Video with container readiness polling ──────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_video_polls_container(self, m):
        m.side_effect = [
            _resp(200, {'id': 'container-v'}),                 # create
            _resp(200, {'status_code': 'IN_PROGRESS'}),        # poll #1
            _resp(200, {'status_code': 'IN_PROGRESS'}),        # poll #2
            _resp(200, {'status_code': 'FINISHED'}),           # poll #3
            _resp(200, {'id': 'media-v'}),                     # publish
            _resp(200, {'id': 'media-v', 'permalink': 'https://www.instagram.com/p/SHORTCODEV/'}), # permalink
        ]
        pub = get_publisher('instagram')
        result = pub.publish_video(_fake_credential(), 'video caption',
                                   'https://x/v.mp4')

        self.assertEqual(m.call_count, 6)
        # First call creates the VIDEO container
        first = m.call_args_list[0].kwargs
        self.assertEqual(first['data']['media_type'], 'VIDEO')
        self.assertEqual(first['data']['video_url'], 'https://x/v.mp4')

        # The 3 middle calls poll status_code
        for poll in m.call_args_list[1:4]:
            self.assertEqual(poll.kwargs['method'], 'GET')
            self.assertIn('/container-v', poll.kwargs['url'])
            self.assertEqual(poll.kwargs['params']['fields'], 'status_code,status')

        # Fifth call publishes
        publish = m.call_args_list[4].kwargs
        self.assertIn('/media_publish', publish['url'])
        self.assertEqual(publish['data']['creation_id'], 'container-v')
        self.assertEqual(result.platform_post_id, 'media-v')
        self.assertEqual(result.platform_url, 'https://www.instagram.com/p/SHORTCODEV/')

    @patch('social_stats.publishers._graph_client.requests.request')
    def test_video_container_error_raises(self, m):
        m.side_effect = [
            _resp(200, {'id': 'container-v'}),
            _resp(200, {'status_code': 'ERROR', 'status': 'Video format not supported'}),
        ]
        pub = get_publisher('instagram')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_video(_fake_credential(), 'hi', 'https://x/v.mp4')
        self.assertEqual(ctx.exception.code, 'container_error')

    # ── Reels ────────────────────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_reel(self, m):
        m.side_effect = [
            _resp(200, {'id': 'container-r'}),
            _resp(200, {'status_code': 'FINISHED'}),
            _resp(200, {'id': 'media-r'}),
            _resp(200, {'id': 'media-r', 'permalink': 'https://www.instagram.com/reel/SHORTCODER/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_reel(_fake_credential(), 'https://x/v.mp4', 'reel caption',
                         share_to_feed=True, cover_url='https://x/cov.jpg')

        first = m.call_args_list[0].kwargs
        self.assertEqual(first['data']['media_type'], 'REELS')
        self.assertEqual(first['data']['video_url'], 'https://x/v.mp4')
        self.assertEqual(first['data']['share_to_feed'], 'true')
        self.assertEqual(first['data']['cover_url'], 'https://x/cov.jpg')

    # ── Story (image) ────────────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_story_image(self, m):
        m.side_effect = [
            _resp(200, {'id': 'container-s'}),
            _resp(200, {'id': 'media-s'}),
            _resp(200, {'id': 'media-s', 'permalink': 'https://www.instagram.com/stories/user/SHORTCODES/'}),
        ]
        pub = get_publisher('instagram')
        pub.publish_story(_fake_credential(), 'https://x/img.jpg')

        first = m.call_args_list[0].kwargs
        self.assertEqual(first['data']['media_type'], 'STORIES')
        self.assertEqual(first['data']['image_url'], 'https://x/img.jpg')
        # 3 calls: create story container, media_publish, get permalink
        self.assertEqual(m.call_count, 3)

    # ── Carousel ─────────────────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_carousel_3_images(self, m):
        m.side_effect = [
            _resp(200, {'id': 'child-1'}),
            _resp(200, {'id': 'child-2'}),
            _resp(200, {'id': 'child-3'}),
            _resp(200, {'id': 'parent'}),                  # CAROUSEL container
            _resp(200, {'status_code': 'FINISHED'}),       # poll
            _resp(200, {'id': 'media-c'}),                 # publish
            _resp(200, {'id': 'media-c', 'permalink': 'https://www.instagram.com/p/SHORTCODEC/'}), # permalink
        ]
        pub = get_publisher('instagram')
        result = pub.publish_carousel(
            _fake_credential(),
            'caption!',
            ['https://x/1.jpg', 'https://x/2.jpg', 'https://x/3.jpg'],
        )

        # 3 children + 1 parent + 1 poll + 1 publish + 1 permalink = 7
        self.assertEqual(m.call_count, 7)

        # Each child has is_carousel_item=true
        for i in range(3):
            self.assertEqual(m.call_args_list[i].kwargs['data']['is_carousel_item'], 'true')

        # Parent: media_type=CAROUSEL with comma-joined children
        parent = m.call_args_list[3].kwargs
        self.assertEqual(parent['data']['media_type'], 'CAROUSEL')
        self.assertEqual(parent['data']['children'], 'child-1,child-2,child-3')
        self.assertEqual(parent['data']['caption'], 'caption!')

        self.assertEqual(result.platform_post_id, 'media-c')
        self.assertEqual(result.platform_url, 'https://www.instagram.com/p/SHORTCODEC/')

    def test_carousel_too_few_items(self):
        pub = get_publisher('instagram')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_carousel(_fake_credential(), 'x', ['https://x/1.jpg'])
        self.assertEqual(ctx.exception.code, 'missing_media')

    def test_carousel_too_many_items(self):
        pub = get_publisher('instagram')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_carousel(_fake_credential(), 'x',
                                  [f'https://x/{i}.jpg' for i in range(11)])
        self.assertEqual(ctx.exception.code, 'too_many_media')

    # ── Text only is unsupported ─────────────────────────────────────────
    def test_text_only_unsupported(self):
        pub = get_publisher('instagram')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_text(_fake_credential(), 'no media')
        self.assertFalse(ctx.exception.supported)

    # ── Replies ──────────────────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_reply_to_comment(self, m):
        m.return_value = _resp(200, {'id': 'reply-1'})
        pub = get_publisher('instagram')
        out = pub.reply_to_comment(_fake_credential(), 'comment-9', 'thanks!')
        self.assertIn('/comment-9/replies', m.call_args.kwargs['url'])
        self.assertEqual(m.call_args.kwargs['data']['message'], 'thanks!')
        self.assertEqual(out.platform_post_id, 'reply-1')

    @patch('social_stats.publishers._graph_client.requests.request')
    def test_reply_to_dm(self, m):
        m.return_value = _resp(200, {'message_id': 'msg-1'})
        pub = get_publisher('instagram')
        pub.reply_to_dm(_fake_credential(), 'recipient-igsid', 'hello!')
        kwargs = m.call_args.kwargs
        self.assertIn('/17841400000000000/messages', kwargs['url'])
        self.assertEqual(kwargs['json']['recipient']['id'], 'recipient-igsid')
        self.assertEqual(kwargs['json']['message']['text'], 'hello!')

    # ── Token expiry mapping ─────────────────────────────────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_token_expired_maps(self, m):
        m.return_value = _resp(401, {'error': {'code': 190, 'message': 'Session expired'}})
        pub = get_publisher('instagram')
        with self.assertRaises(TokenExpiredError):
            pub.publish_image(_fake_credential(), 'hi', ['https://x/img.jpg'])

    # ── Config guard ─────────────────────────────────────────────────────
    def test_missing_ig_id_raises(self):
        pub = get_publisher('instagram')
        cred = _fake_credential(instagram_account_id='')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_image(cred, 'hi', ['https://x/img.jpg'])
        self.assertEqual(ctx.exception.code, 'missing_config')

    # ── Canonical permalink regression tests (BS-3D.6A) ─────────────────
    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_container_fetches_canonical_permalink(self, m):
        """Case 1: media_publish returns id, GET permalink returns canonical URL."""
        m.side_effect = [
            _resp(200, {'id': 'container-img-1'}),
            _resp(200, {'id': '17991627227860965'}),
            _resp(200, {'id': '17991627227860965', 'permalink': 'https://www.instagram.com/p/Derx_mjEb62/'}),
        ]
        pub = get_publisher('instagram')
        result = pub.publish_image(_fake_credential(), 'caption!', ['https://x/img.jpg'])

        self.assertEqual(m.call_count, 3)
        self.assertTrue(result.success)
        self.assertEqual(result.platform_post_id, '17991627227860965')
        self.assertEqual(result.platform_url, 'https://www.instagram.com/p/Derx_mjEb62/')
        third = m.call_args_list[2]
        self.assertEqual(third.kwargs['method'], 'GET')
        self.assertIn('/17991627227860965', third.kwargs['url'])
        self.assertEqual(third.kwargs['params']['fields'], 'permalink')

    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_container_permalink_lookup_fails_gracefully(self, m):
        """Case 2: permalink GET fails -> publication succeeds, platform_url is empty, no duplicate publish."""
        m.side_effect = [
            _resp(200, {'id': 'container-img-2'}),
            _resp(200, {'id': '17991627227860965'}),
            Exception('Network error during permalink lookup'),
        ]
        pub = get_publisher('instagram')
        with self.assertLogs('social_stats.publishers.instagram', level='WARNING') as log_ctx:
            result = pub.publish_image(_fake_credential(), 'caption!', ['https://x/img.jpg'])

        self.assertEqual(m.call_count, 3)
        self.assertTrue(result.success)
        self.assertEqual(result.platform_post_id, '17991627227860965')
        self.assertEqual(result.platform_url, '')
        self.assertNotIn('https://www.instagram.com/p/17991627227860965', result.platform_url)
        self.assertTrue(any('permalink lookup failed' in record.message for record in log_ctx.records))

    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_container_media_publish_missing_id_raises(self, m):
        """Case 3: media_publish does not return id -> raises PublishError."""
        m.side_effect = [
            _resp(200, {'id': 'container-img-3'}),
            _resp(200, {}),
        ]
        pub = get_publisher('instagram')
        with self.assertRaises(PublishError) as ctx:
            pub.publish_image(_fake_credential(), 'caption!', ['https://x/img.jpg'])
        self.assertIn('did not return media id', str(ctx.exception).lower())

    @patch('social_stats.publishers._graph_client.requests.request')
    def test_publish_container_permalink_empty_returns_blank(self, m):
        """Case 4: permalink response has no permalink key -> platform_url is empty (no synthetic fallback)."""
        m.side_effect = [
            _resp(200, {'id': 'container-img-4'}),
            _resp(200, {'id': '17991627227860965'}),
            _resp(200, {'id': '17991627227860965'}),
        ]
        pub = get_publisher('instagram')
        result = pub.publish_image(_fake_credential(), 'caption!', ['https://x/img.jpg'])

        self.assertEqual(m.call_count, 3)
        self.assertTrue(result.success)
        self.assertEqual(result.platform_post_id, '17991627227860965')
        self.assertEqual(result.platform_url, '')
        self.assertNotIn('https://www.instagram.com/p/17991627227860965', result.platform_url)
