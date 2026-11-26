import io
import tempfile
from unittest.mock import patch
from PIL import Image

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.models import Client, ClientUserRole, UnifiedPost, UserProfile


def _make_png():
    buf = io.BytesIO()
    Image.new('RGB', (24, 24), color=(10, 90, 200)).save(buf, format='PNG')
    return SimpleUploadedFile('bob.png', buf.getvalue(), content_type='image/png')


class DraftManagementIntegrationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_10d2',
            email='owner_10d2@test.local',
            password='Password123!',
        )
        self.agency = Agency.objects.create(
            name='Agency 10D2',
            slug='agency-10d2',
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

        self.client_a = Client.objects.create(name='Client A 10D2', company='Client A 10D2', email='ca10d2@test.local')
        self.client_b = Client.objects.create(name='Client B 10D2', company='Client B 10D2', email='cb10d2@test.local')
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_a,
            status='active',
            permissions={'draft_posts': True, 'delete_posts': True},
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_b,
            status='active',
            permissions={'draft_posts': True, 'delete_posts': True},
        )

        self.foreign_user = User.objects.create_user(
            username='foreign_10d2',
            email='foreign_10d2@test.local',
            password='Password123!',
        )
        self.foreign_client = Client.objects.create(name='Foreign 10D2', company='Foreign 10D2', email='f10d2@test.local')
        UserProfile.objects.create(
            user=self.foreign_user,
            role='client',
            account_type='end_user',
            client=self.foreign_client,
        )
        ClientUserRole.objects.create(user=self.foreign_user, client=self.foreign_client, role='owner')

        self.api = APIClient()

    def test_save_list_reopen_edit_no_duplicate_and_tenant_isolation(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                self.api.force_authenticate(user=self.owner)

                # 1. Upload promotional image
                up_res = self.api.post(
                    '/api/composer/media/',
                    {'file': _make_png(), 'client': str(self.client_a.id)},
                    format='multipart',
                )
                self.assertEqual(up_res.status_code, 201, up_res.data)
                asset_id = up_res.data['id']

                # 2. Save draft
                create_res = self.api.post(
                    f'/api/composer/posts/?client_id={self.client_a.id}',
                    {
                        'title': 'BOP-001 | Captación',
                        'content': '¿Cuántos clientes está perdiendo tu negocio #BopAgencia',
                        'media_type': 'image',
                        'target_platforms': ['facebook', 'instagram'],
                        'media_urls': [f'asset:{asset_id}'],
                    },
                    format='json',
                )
                self.assertEqual(create_res.status_code, 201, create_res.data)
                draft_id = create_res.data['id']

                # 3. List drafts for Client A -> includes thumbnail_url and media_urls
                list_a = self.api.get(f'/api/composer/posts/?client_id={self.client_a.id}&status=draft')
                self.assertEqual(list_a.status_code, 200)
                results_a = list_a.data.get('results', list_a.data)
                self.assertEqual(len(results_a), 1)
                self.assertEqual(results_a[0]['id'], draft_id)
                self.assertIn('/api/media/serve/', results_a[0]['thumbnail_url'])
                self.assertIn('token=', results_a[0]['thumbnail_url'])
                self.assertEqual(results_a[0]['media_urls'], [f'asset:{asset_id}'])

                # 4. Workspace switch to Client B -> zero drafts leaked
                list_b = self.api.get(f'/api/composer/posts/?client_id={self.client_b.id}&status=draft')
                self.assertEqual(list_b.status_code, 200)
                self.assertEqual(len(list_b.data.get('results', list_b.data)), 0)

                # 5. Reopen draft -> resolved_media_assets populated with signed URLs
                reopen = self.api.get(f'/api/composer/posts/{draft_id}/?client_id={self.client_a.id}')
                self.assertEqual(reopen.status_code, 200)
                self.assertEqual(len(reopen.data['resolved_media_assets']), 1)
                self.assertEqual(reopen.data['resolved_media_assets'][0]['id'], asset_id)
                self.assertIn('token=', reopen.data['resolved_media_assets'][0]['thumbnail_url'])

                # 6. Edit existing draft without duplication
                patch_res = self.api.patch(
                    f'/api/composer/posts/{draft_id}/?client_id={self.client_a.id}',
                    {'content': 'Texto editado #BopAgencia'},
                    format='json',
                )
                self.assertEqual(patch_res.status_code, 200)
                self.assertEqual(UnifiedPost.objects.filter(client=self.client_a).count(), 1)

                # 7. Foreign user rejected
                foreign_api = APIClient()
                foreign_api.force_authenticate(user=self.foreign_user)
                self.assertIn(
                    foreign_api.get(f'/api/composer/posts/{draft_id}/?client_id={self.client_a.id}').status_code,
                    (403, 404),
                )
                self.assertIn(
                    foreign_api.delete(f'/api/composer/posts/{draft_id}/?client_id={self.client_a.id}').status_code,
                    (403, 404),
                )
