# ============================================================================
#  Social Stats — Instagram Carousel Uniformity Validation Tests (BS-3F.2D)
# ============================================================================
from unittest.mock import MagicMock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from social_stats.models import (
    Client, MediaAsset, UnifiedPost, PlatformCredential, UserProfile,
)
from social_stats import media_service
from social_stats.media_service import validate_carousel_for_platform, validate_for_platform

User = get_user_model()


class MockAsset:
    """Lightweight in-memory asset for unit testing carousel rules."""
    def __init__(self, width=1080, height=1080, mime_type='image/jpeg',
                 file_size=1024 * 1024, duration_seconds=None, id=None):
        self.id = id
        self.width = width
        self.height = height
        self.mime_type = mime_type
        self.file_size = file_size
        self.duration_seconds = duration_seconds


class InstagramCarouselValidationTests(TestCase):
    """
    Test suite covering CASES 1 through 12 specified in Phase BS-3F.2D:
      CASE 1:  2 JPEG images 1254x1254 + 1254x1254 -> PASS
      CASE 2:  1080x1080 + 1254x1254 -> PASS (same 1:1 aspect)
      CASE 3:  1080x1080 + 1080x1350 -> FAIL (different aspect)
      CASE 4:  3-item carousel all same ratio -> PASS
      CASE 5:  third item differs -> FAIL
      CASE 6:  too few items (< 2) -> FAIL
      CASE 7:  too many items (> 10) -> FAIL
      CASE 8:  one individual asset invalid (e.g. PNG on IG carousel) -> FAIL
      CASE 9:  mixed image/video and video ratio known (same ratio) -> PASS
      CASE 10: mixed image/video and ratio unknown (video dims None) -> safe blocking FAIL
      CASE 11: tenant isolation unchanged
      CASE 12: no Meta calls during preflight
    """

    def setUp(self):
        self.client_obj = Client.objects.create(name='Test Tenant', email='test_tenant@example.com', default_language='en')
        self.other_client = Client.objects.create(name='Other Tenant', email='other_tenant@example.com', default_language='en')

        self.user = User.objects.create_user(username='tester', email='tester@test.com', password='password123')
        self.profile = UserProfile.objects.create(user=self.user, client=self.client_obj, role='client_admin')

        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_case_1_identical_geometry_pass(self):
        """CASE 1: 2 JPEG images 1254x1254 + 1254x1254 -> PASS."""
        items = [
            MockAsset(width=1254, height=1254, mime_type='image/jpeg', id=101),
            MockAsset(width=1254, height=1254, mime_type='image/jpeg', id=102),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertTrue(res.ok)
        self.assertEqual(res.errors, [])

    def test_case_2_different_dimensions_same_ratio_pass(self):
        """CASE 2: 1080x1080 + 1254x1254 -> PASS (both 1:1 ratio)."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=201),
            MockAsset(width=1254, height=1254, mime_type='image/jpeg', id=202),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertTrue(res.ok)
        self.assertEqual(res.errors, [])

    def test_case_3_different_aspect_ratios_fail(self):
        """CASE 3: 1080x1080 + 1080x1350 -> FAIL (1:1 vs 4:5)."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=301),
            MockAsset(width=1080, height=1350, mime_type='image/jpeg', id=302),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertFalse(res.ok)
        self.assertIn("All Instagram carousel items must use the same aspect ratio.", res.errors)

        # Also verify Spanish error message
        res_es = validate_carousel_for_platform(items, 'instagram', lang='es')
        self.assertFalse(res_es.ok)
        self.assertIn("Todos los elementos del carrusel de Instagram deben usar la misma proporción.", res_es.errors)

    def test_case_4_three_items_same_ratio_pass(self):
        """CASE 4: 3-item carousel all same ratio -> PASS."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=401),
            MockAsset(width=1254, height=1254, mime_type='image/jpeg', id=402),
            MockAsset(width=800, height=800, mime_type='image/jpeg', id=403),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertTrue(res.ok)
        self.assertEqual(res.errors, [])

    def test_case_5_third_item_differs_fail(self):
        """CASE 5: 3 items where third item differs -> FAIL."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=501),
            MockAsset(width=1254, height=1254, mime_type='image/jpeg', id=502),
            MockAsset(width=1080, height=1350, mime_type='image/jpeg', id=503),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertFalse(res.ok)
        self.assertIn("All Instagram carousel items must use the same aspect ratio.", res.errors)

    def test_case_6_too_few_items_fail(self):
        """CASE 6: fewer than 2 items -> FAIL."""
        res_0 = validate_carousel_for_platform([], 'instagram')
        self.assertFalse(res_0.ok)
        self.assertIn("An Instagram carousel requires at least 2 items.", res_0.errors)

        res_1 = validate_carousel_for_platform([
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=601)
        ], 'instagram')
        self.assertFalse(res_1.ok)
        self.assertIn("An Instagram carousel requires at least 2 items.", res_1.errors)

        # Spanish check
        res_es = validate_carousel_for_platform([], 'instagram', lang='es')
        self.assertIn("Un carrusel de Instagram requiere al menos 2 elementos.", res_es.errors)

    def test_case_7_too_many_items_fail(self):
        """CASE 7: more than 10 items -> FAIL."""
        items = [MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=700 + i) for i in range(11)]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertFalse(res.ok)
        self.assertIn("An Instagram carousel cannot exceed 10 items.", res.errors)

        res_es = validate_carousel_for_platform(items, 'instagram', lang='es')
        self.assertIn("Un carrusel de Instagram no puede exceder los 10 elementos.", res_es.errors)

    def test_case_8_individual_asset_invalid_fail(self):
        """CASE 8: one individual asset invalid (e.g. image/png on IG) -> per-item validation preserved."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=801),
            MockAsset(width=1080, height=1080, mime_type='image/png', id=802),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertFalse(res.ok)
        # Verify per-item error is captured
        self.assertTrue(any('image/png' in err for err in res.errors))

    def test_case_9_mixed_image_video_known_ratio_pass(self):
        """CASE 9: mixed image and video with known identical ratio -> PASS."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=901),
            MockAsset(width=1080, height=1080, mime_type='video/mp4', duration_seconds=30, id=902),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertTrue(res.ok)
        self.assertEqual(res.errors, [])

    def test_case_10_mixed_image_video_unknown_ratio_safe_block(self):
        """CASE 10: mixed image and video with unknown ratio -> safe blocking behavior."""
        items = [
            MockAsset(width=1080, height=1080, mime_type='image/jpeg', id=1001),
            MockAsset(width=None, height=None, mime_type='video/mp4', duration_seconds=30, id=1002),
        ]
        res = validate_carousel_for_platform(items, 'instagram')
        self.assertFalse(res.ok)
        self.assertIn("Video dimensions could not be verified for Instagram carousel.", res.errors)
        self.assertIn("All Instagram carousel items must use the same aspect ratio.", res.errors)

        res_es = validate_carousel_for_platform(items, 'instagram', lang='es')
        self.assertIn("No se pudieron verificar las dimensiones del video para el carrusel de Instagram.", res_es.errors)

    def test_case_11_tenant_isolation_unchanged(self):
        """CASE 11: tenant isolation prevents preflight from seeing other tenant's assets."""
        # Create an asset for other tenant
        asset_other = MediaAsset.objects.create(
            client=self.other_client,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1080,
        )
        asset_own = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1080,
        )

        # Preflight payload referencing other tenant's asset + own asset
        # Preflight should only resolve own asset, thus finding only 1 asset (< 2 items)
        payload = {
            'content': 'Test carousel isolation',
            'media_type': 'carousel',
            'target_platforms': ['instagram'],
            'media_assets': [asset_own.id, asset_other.id],
        }
        res = self.api.post('/api/composer/preflight/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['ok'])
        ig_res = res.data['platforms']['instagram']
        self.assertFalse(ig_res['ok'])
        # Because other tenant's asset was ignored, only 1 asset was found -> too few items error
        self.assertTrue(any("at least 2 items" in err for err in ig_res['errors']))

    @patch('social_stats.publishers._graph_client.GraphClient.post')
    @patch('social_stats.publishers._graph_client.GraphClient.get')
    def test_case_12_no_meta_calls_during_preflight(self, mock_get, mock_post):
        """CASE 12: no Meta Graph API calls are made during preflight checks."""
        asset1 = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1080,
        )
        asset2 = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1080,
        )

        payload = {
            'content': 'Preflight check with no external calls',
            'media_type': 'carousel',
            'target_platforms': ['instagram'],
            'media_assets': [asset1.id, asset2.id],
        }
        res = self.api.post('/api/composer/preflight/', payload, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(mock_get.call_count, 0)

    def test_publish_now_blocks_non_uniform_carousel(self):
        """publish_now returns HTTP 400 when post has non-uniform carousel items."""
        asset1 = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1080,
        )
        asset2 = MediaAsset.objects.create(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500000,
            width=1080,
            height=1350,
        )
        post = UnifiedPost.objects.create(
            client=self.client_obj,
            content='Carousel post with mismatched ratios',
            media_type='carousel',
            media_urls=[f'asset:{asset1.id}', f'asset:{asset2.id}'],
            target_platforms=['instagram'],
            status='draft',
            created_by=self.user,
        )
        res = self.api.post(f'/api/composer/posts/{post.id}/publish_now/')
        self.assertEqual(res.status_code, 400)
        self.assertIn("All Instagram carousel items must use the same aspect ratio.", res.data.get('detail', ''))

    def test_serializer_validates_carousel_counts(self):
        """UnifiedPostSerializer validates minimum and maximum items for carousels."""
        from social_stats.composer_serializers import UnifiedPostSerializer
        # Less than 2 items
        ser1 = UnifiedPostSerializer(data={
            'client': self.client_obj.id,
            'content': 'Test',
            'media_type': 'carousel',
            'media_urls': ['asset:1'],
            'target_platforms': ['instagram'],
        })
        self.assertFalse(ser1.is_valid())
        self.assertIn('media_urls', ser1.errors)

        # More than 10 items
        ser2 = UnifiedPostSerializer(data={
            'client': self.client_obj.id,
            'content': 'Test',
            'media_type': 'carousel',
            'media_urls': [f'asset:{i}' for i in range(11)],
            'target_platforms': ['instagram'],
        })
        self.assertFalse(ser2.is_valid())
        self.assertIn('media_urls', ser2.errors)

