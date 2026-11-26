import io
import tempfile
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats import media_service
from social_stats.models import (
    Client,
    ClientUserRole,
    MediaAsset,
    PlatformCredential,
    UnifiedPost,
    UserProfile,
)
from social_stats.orchestrator import _resolve_media_urls


def _make_png_upload(name='promo.png', size=(1122, 1402), mode='RGB', color=(30, 140, 220)):
    buf = io.BytesIO()
    img = Image.new(mode, size, color=color)
    if mode == 'RGBA':
        # Top-left quadrant transparent, bottom-right opaque red
        for x in range(size[0] // 2):
            for y in range(size[1] // 2):
                img.putpixel((x, y), (0, 0, 0, 0))
    img.save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class BS10D3MediaCompatibilityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='bop_owner_10d3',
            email='bop_owner_10d3@test.local',
            password='Password123!',
        )
        self.client_obj = Client.objects.create(
            name='Bop Agencia Test',
            company='Bop Agencia Test',
            email='bop10d3@test.local',
            owner_user=self.user,
            requires_approval=True,
        )
        UserProfile.objects.create(
            user=self.user,
            role='client',
            account_type='end_user',
            client=self.client_obj,
        )
        ClientUserRole.objects.create(
            user=self.user,
            client=self.client_obj,
            role='owner',
        )
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform='facebook',
            access_token='tok_fb',
            is_active=True,
        )
        PlatformCredential.objects.create(
            client=self.client_obj,
            platform='instagram',
            instagram_account_id='ig-1',
            access_token='tok_ig',
            is_active=True,
        )

        self.foreign_user = User.objects.create_user(
            username='foreign_10d3',
            email='foreign_10d3@test.local',
            password='Password123!',
        )
        self.foreign_client = Client.objects.create(
            name='Foreign Tenant',
            company='Foreign Tenant',
            email='foreign10d3@test.local',
            owner_user=self.foreign_user,
        )
        UserProfile.objects.create(
            user=self.foreign_user,
            role='client',
            account_type='end_user',
            client=self.foreign_client,
        )
        ClientUserRole.objects.create(
            user=self.foreign_user,
            client=self.foreign_client,
            role='owner',
        )

        self.api = APIClient()

    def test_png_to_jpeg_conversion_and_original_preserved(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png_upload('robot.png', size=(1122, 1402)),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                orig_file_name = asset.file.name
                orig_size = asset.file_size

                # Facebook keeps original PNG
                fb_asset = media_service.ensure_platform_compatible_media(asset, 'facebook', 'image')
                self.assertEqual(fb_asset.id, asset.id)
                self.assertEqual(fb_asset.mime_type, 'image/png')

                # Instagram gets a JPEG variant preserving aspect ratio
                ig_asset = media_service.ensure_platform_compatible_media(asset, 'instagram', 'image')
                self.assertNotEqual(ig_asset.id, asset.id)
                self.assertEqual(ig_asset.source_asset_id, asset.id)
                self.assertEqual(ig_asset.client_id, self.client_obj.id)
                self.assertEqual(ig_asset.mime_type, 'image/jpeg')
                self.assertEqual((ig_asset.width, ig_asset.height), (1122, 1402))
                self.assertIn(f'tenant_{self.client_obj.id}', ig_asset.file.name)

                # Original asset is completely untouched
                asset.refresh_from_db()
                self.assertEqual(asset.file.name, orig_file_name)
                self.assertEqual(asset.mime_type, 'image/png')
                self.assertEqual(asset.file_size, orig_size)
                self.assertEqual((asset.width, asset.height), (1122, 1402))

                # Media library list hides internal variants
                self.api.force_authenticate(user=self.user)
                list_res = self.api.get('/api/composer/media/', HTTP_X_CLIENT_ID=str(self.client_obj.id))
                self.assertEqual(list_res.status_code, 200)
                returned_ids = [item['id'] for item in (list_res.data.get('results', list_res.data))]
                self.assertIn(asset.id, returned_ids)
                self.assertNotIn(ig_asset.id, returned_ids)

    def test_transparent_png_conversion_composites_white_background(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png_upload('alpha.png', size=(800, 800), mode='RGBA', color=(220, 40, 40, 255)),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                ig_asset = media_service.ensure_platform_compatible_media(asset, 'instagram', 'image')
                self.assertEqual(ig_asset.mime_type, 'image/jpeg')
                self.assertEqual((ig_asset.width, ig_asset.height), (800, 800))

                ig_asset.file.open('rb')
                try:
                    with Image.open(ig_asset.file) as converted:
                        self.assertEqual(converted.format, 'JPEG')
                        self.assertEqual(converted.mode, 'RGB')
                        # Transparent corner should be white (~255,255,255), not black
                        tl = converted.getpixel((10, 10))
                        self.assertGreater(tl[0], 240)
                        self.assertGreater(tl[1], 240)
                        self.assertGreater(tl[2], 240)
                finally:
                    ig_asset.file.close()

    def test_compatible_variant_reuse_avoids_duplicate_conversions(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png_upload('reuse.png', size=(1080, 1080)),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                v1 = media_service.ensure_platform_compatible_media(asset, 'instagram', 'image')
                v2 = media_service.ensure_platform_compatible_media(asset, 'instagram', 'image')
                v3 = media_service.ensure_platform_compatible_media(asset, 'instagram', 'carousel')

                self.assertEqual(v1.id, v2.id)
                self.assertEqual(v1.id, v3.id)
                self.assertEqual(
                    MediaAsset.objects.filter(source_asset=asset, variant_platform='instagram').count(),
                    1,
                )

    def test_tenant_isolation_for_variants_and_serving(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png_upload('private.png', size=(1080, 1080)),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                ig_variant = media_service.ensure_platform_compatible_media(asset, 'instagram', 'image')

                # Foreign tenant cannot serve the variant
                self.api.force_authenticate(user=self.foreign_user)
                res_serve = self.api.get(f'/api/media/serve/{ig_variant.id}/')
                self.assertEqual(res_serve.status_code, 403)

                # Foreign tenant preflight cannot resolve client #3's asset
                res_preflight = self.api.post(
                    '/api/composer/preflight/',
                    {
                        'content': 'Test',
                        'media_type': 'image',
                        'media_urls': [f'asset:{asset.id}'],
                        'target_platforms': ['instagram'],
                    },
                    format='json',
                )
                self.assertEqual(res_preflight.status_code, 200)
                self.assertEqual(
                    MediaAsset.objects.filter(source_asset=asset, client=self.foreign_client).count(),
                    0,
                )

    @patch('requests.post')
    @patch('requests.get')
    def test_preflight_and_publishing_format_consistency(self, mock_get, mock_post):
        with tempfile.TemporaryDirectory() as tmp_media:
            with (
                override_settings(
                    MEDIA_ROOT=tmp_media,
                    BACKEND_PUBLIC_URL='https://media.bopagencia.example',
                ),
                patch('social_stats.media_service._s3_enabled', return_value=False),
            ):
                asset = media_service.upload_media(
                    _make_png_upload('commercial.png', size=(1122, 1402)),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                post = UnifiedPost.objects.create(
                    client=self.client_obj,
                    created_by=self.user,
                    title='BOP-001',
                    content='Commercial draft',
                    media_type='image',
                    media_urls=[f'asset:{asset.id}'],
                    target_platforms=['facebook', 'instagram'],
                    status='draft',
                )

                self.api.force_authenticate(user=self.user)
                preflight_res = self.api.post(
                    '/api/composer/preflight/',
                    {
                        'content': post.content,
                        'media_type': post.media_type,
                        'media_urls': post.media_urls,
                        'target_platforms': post.target_platforms,
                        'client': self.client_obj.id,
                    },
                    format='json',
                    HTTP_X_CLIENT_ID=str(self.client_obj.id),
                )
                self.assertEqual(preflight_res.status_code, 200, preflight_res.data)
                self.assertTrue(preflight_res.data['ok'], preflight_res.data)
                self.assertTrue(preflight_res.data['platforms']['facebook']['ok'])
                self.assertTrue(preflight_res.data['platforms']['instagram']['ok'])

                # No external Meta API calls during preflight
                mock_get.assert_not_called()
                mock_post.assert_not_called()

                # Publishing URL resolution uses the exact same compatible variant for IG and original for FB
                ig_variant = MediaAsset.objects.get(source_asset=asset, variant_platform='instagram')
                fb_urls = _resolve_media_urls(post, post.media_urls, platform='facebook', media_type='image')
                ig_urls = _resolve_media_urls(post, post.media_urls, platform='instagram', media_type='image')

                self.assertEqual(len(fb_urls), 1)
                self.assertEqual(len(ig_urls), 1)

                # Verify tokens resolve to original asset for FB and JPEG variant for IG
                from social_stats.media_access import verify_public_publishing_token
                fb_token = fb_urls[0].rstrip('/').split('/')[-1]
                ig_token = ig_urls[0].rstrip('/').split('/')[-1]

                fb_ok, fb_aid, _ = verify_public_publishing_token(fb_token)
                ig_ok, ig_aid, _ = verify_public_publishing_token(ig_token)
                self.assertTrue(fb_ok)
                self.assertTrue(ig_ok)
                self.assertEqual(fb_aid, asset.id)
                self.assertEqual(ig_aid, ig_variant.id)
