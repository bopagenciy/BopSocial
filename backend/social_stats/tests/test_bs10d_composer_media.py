import io
import tempfile
from PIL import Image

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.models import Client, ClientUserRole, UserProfile


def _make_png(name='promo.png', color=(20, 120, 220)):
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), color=color).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class ComposerMediaUploadAndPreviewTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='agency_owner_10d',
            email='agency_owner_10d@test.local',
            password='Password123!',
        )
        self.agency = Agency.objects.create(
            name='Agency 10D',
            slug='agency-10d',
            owner_user=self.owner,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.owner,
            role='owner',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency,
        )
        self.client_obj = Client.objects.create(
            name='Pilot 10D',
            company='Pilot 10D',
            email='pilot10d@test.local',
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_obj,
            status='active',
            permissions={'draft_posts': True},
        )

        self.foreign_user = User.objects.create_user(
            username='foreign_10d',
            email='foreign_10d@test.local',
            password='Password123!',
        )
        self.foreign_client = Client.objects.create(
            name='Foreign 10D',
            company='Foreign 10D',
            email='foreign10d@test.local',
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

    def test_upload_returns_signed_urls_serves_image_and_enforces_tenant_isolation(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                self.api.force_authenticate(user=self.owner)
                res = self.api.post(
                    '/api/composer/media/',
                    {'file': _make_png('promo.png'), 'client': str(self.client_obj.id)},
                    format='multipart',
                    HTTP_X_CLIENT_ID=str(self.client_obj.id),
                )
                self.assertEqual(res.status_code, 201, res.data)
                asset_id = res.data['id']
                file_url = res.data['file_url']
                thumb_url = res.data['thumbnail_url']

                self.assertIn(f'/api/media/serve/{asset_id}/', file_url)
                self.assertIn('token=', file_url)
                self.assertIn(f'/api/media/serve/{asset_id}/', thumb_url)
                self.assertIn('token=', thumb_url)

                # Browser <img> loads signed URL without Authorization header -> 200 image
                anon = APIClient()
                img_res = anon.get(thumb_url)
                self.assertEqual(img_res.status_code, 200)
                self.assertTrue(img_res['Content-Type'].startswith('image/'))

                file_res = anon.get(file_url)
                self.assertEqual(file_res.status_code, 200)
                self.assertEqual(file_res['Content-Type'], 'image/png')

                # Unauthenticated direct endpoint without token -> 401
                self.assertEqual(anon.get(f'/api/composer/media/{asset_id}/thumbnail/').status_code, 401)
                self.assertEqual(anon.get(f'/api/media/serve/{asset_id}/').status_code, 401)

                # Foreign tenant access -> 403 / 404
                foreign = APIClient()
                foreign.force_authenticate(user=self.foreign_user)
                self.assertIn(foreign.get(f'/api/media/serve/{asset_id}/').status_code, (403, 404))
                self.assertIn(foreign.get(f'/api/composer/media/{asset_id}/thumbnail/').status_code, (403, 404))

                # Draft persistence with asset:<id> reference
                draft_res = self.api.post(
                    f'/api/composer/posts/?client_id={self.client_obj.id}',
                    {
                        'title': 'Promo Draft',
                        'content': 'Promoción especial',
                        'media_type': 'image',
                        'target_platforms': ['facebook', 'instagram'],
                        'media_urls': [f'asset:{asset_id}'],
                    },
                    format='json',
                )
                self.assertEqual(draft_res.status_code, 201, draft_res.data)
                reopen_res = self.api.get(
                    f"/api/composer/posts/{draft_res.data['id']}/?client_id={self.client_obj.id}",
                )
                self.assertEqual(reopen_res.status_code, 200)
                self.assertEqual(reopen_res.data['media_urls'], [f'asset:{asset_id}'])

    def test_bulk_upload_returns_signed_urls_for_carousel(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                self.api.force_authenticate(user=self.owner)
                res = self.api.post(
                    f'/api/composer/media/bulk_upload/?client_id={self.client_obj.id}',
                    {'files': [_make_png('c1.png'), _make_png('c2.png')]},
                    format='multipart',
                )
                self.assertEqual(res.status_code, 201, res.data)
                self.assertEqual(len(res.data['created']), 2)
                for item in res.data['created']:
                    self.assertIn('/api/media/serve/', item['file_url'])
                    self.assertIn('token=', item['file_url'])
                    self.assertIn('/api/media/serve/', item['thumbnail_url'])
                    self.assertIn('token=', item['thumbnail_url'])
