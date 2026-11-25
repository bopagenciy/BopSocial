import io
import tempfile
from PIL import Image

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.models import Client, ClientUserRole, UserProfile


def _make_png_bytes(color=(34, 139, 34)):
    buf = io.BytesIO()
    img = Image.new('RGB', (16, 16), color=color)
    img.save(buf, format='PNG')
    return buf.getvalue()


class BusinessProfileSaveTests(APITestCase):
    def setUp(self):
        self.agency_owner = User.objects.create_user(
            username='agency_owner_10b',
            email='agency_owner_10b@test.local',
            password='Password123!',
        )
        self.agency = Agency.objects.create(
            name='Test Agency 10B',
            slug='test-agency-10b',
            owner_user=self.agency_owner,
        )
        AgencyMembership.objects.create(
            agency=self.agency,
            user=self.agency_owner,
            role='owner',
            is_active=True,
        )
        UserProfile.objects.create(
            user=self.agency_owner,
            role='client',
            account_type='agency_member',
            primary_agency=self.agency,
        )

        self.client_obj = Client.objects.create(
            name='Pilot Workspace 10B',
            company='Pilot Workspace 10B',
            email='pilot10b@test.local',
            timezone='America/New_York',
            default_language='es',
            currency='USD',
        )
        AgencyClientRelation.objects.create(
            agency=self.agency,
            client=self.client_obj,
            status='active',
            permissions={'manage_brand_voice': True, 'draft_posts': True},
        )

        self.foreign_user = User.objects.create_user(
            username='foreign_10b',
            email='foreign_10b@test.local',
            password='Password123!',
        )
        self.foreign_client = Client.objects.create(
            name='Foreign Workspace 10B',
            company='Foreign Workspace 10B',
            email='foreign10b@test.local',
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

    def test_combined_profile_save_with_temp_logo_and_10_product_images(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                self.api.force_authenticate(user=self.agency_owner)
                png_bytes = _make_png_bytes()

                # TemporaryUploadedFile wraps BufferedRandom (like >2.5MB uploads in production)
                temp_logo = TemporaryUploadedFile(
                    name='company_logo.png',
                    content_type='image/png',
                    size=len(png_bytes),
                    charset=None,
                )
                temp_logo.write(png_bytes)
                temp_logo.seek(0)

                payload = {
                    'name': 'Pilot Workspace 10B Updated',
                    'company': 'Pilot Workspace 10B S.A.',
                    'brand_description': 'Modern digital agency helping local brands grow.',
                    'brand_tone': 'professional',
                    'usp': 'Data-driven creative campaigns',
                    'target_audience': 'SMBs in Latin America',
                    'business_category': 'Professional Services',
                    'business_subcategories': '["Marketing", "Advertising"]',
                    'default_language': 'es',
                    'currency': ' usd ',
                    'profile_image': temp_logo,
                }
                for i in range(10):
                    payload[f'product_images[{i}]'] = SimpleUploadedFile(
                        f'product_{i}.png',
                        _make_png_bytes((20 + i * 10, 80, 150)),
                        content_type='image/png',
                    )

                res = self.api.patch(
                    f'/api/clients/{self.client_obj.id}/',
                    payload,
                    format='multipart',
                )
                self.assertEqual(res.status_code, 200, res.data)

                # Verify persistence after reload
                self.client_obj.refresh_from_db()
                self.assertEqual(self.client_obj.company, 'Pilot Workspace 10B S.A.')
                self.assertEqual(self.client_obj.brand_tone, 'professional')
                self.assertEqual(self.client_obj.brand_description, 'Modern digital agency helping local brands grow.')
                self.assertEqual(self.client_obj.currency, 'USD')
                self.assertTrue(bool(self.client_obj.profile_image.name))
                self.assertEqual(len(self.client_obj.product_images), 10)

                reload_res = self.api.get(f'/api/clients/{self.client_obj.id}/')
                self.assertEqual(reload_res.status_code, 200)
                self.assertEqual(len(reload_res.data['product_images']), 10)
                self.assertEqual(reload_res.data['brand_tone'], 'professional')

    def test_text_only_save_and_partial_add_remove_preserve_assets(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                self.api.force_authenticate(user=self.agency_owner)
                png_bytes = _make_png_bytes()

                # Initial save with logo + 3 product images
                init_payload = {
                    'brand_tone': 'professional',
                    'profile_image': SimpleUploadedFile('logo.png', png_bytes, content_type='image/png'),
                    'product_images[0]': SimpleUploadedFile('p0.png', png_bytes, content_type='image/png'),
                    'product_images[1]': SimpleUploadedFile('p1.png', png_bytes, content_type='image/png'),
                    'product_images[2]': SimpleUploadedFile('p2.png', png_bytes, content_type='image/png'),
                }
                res1 = self.api.patch(f'/api/clients/{self.client_obj.id}/', init_payload, format='multipart')
                self.assertEqual(res1.status_code, 200, res1.data)
                self.client_obj.refresh_from_db()
                saved_urls = list(self.client_obj.product_images)
                self.assertEqual(len(saved_urls), 3)

                # Signed URLs returned in API response work for authorized access and fail for unauth/foreign
                signed_logo_url = res1.data['profile_image']
                self.assertIn('?token=', signed_logo_url)
                logo_path, logo_qs = signed_logo_url.split('?', 1)
                tok = logo_qs.split('token=', 1)[1]

                anon_api = APIClient()
                unauth_res = anon_api.get(f'/api/media/serve-client-asset/?path={logo_path}')
                self.assertEqual(unauth_res.status_code, 401)
                bad_tok_res = anon_api.get(f'/api/media/serve-client-asset/?path={logo_path}&token=tampered')
                self.assertEqual(bad_tok_res.status_code, 401)

                foreign_api = APIClient()
                foreign_api.force_authenticate(user=self.foreign_user)
                foreign_res = foreign_api.get(f'/api/media/serve-client-asset/?path={logo_path}')
                self.assertEqual(foreign_res.status_code, 403)

                ok_res = anon_api.get(f'/api/media/serve-client-asset/?path={logo_path}&token={tok}')
                self.assertEqual(ok_res.status_code, 200)

                # Subsequent text-only save (keeps keptUrls, omits profile_image)
                import json
                res2 = self.api.patch(
                    f'/api/clients/{self.client_obj.id}/',
                    {
                        'brand_description': 'Updated description without re-uploading assets.',
                        'product_images': json.dumps(saved_urls),
                    },
                    format='multipart',
                )
                self.assertEqual(res2.status_code, 200, res2.data)
                self.client_obj.refresh_from_db()
                self.assertTrue(bool(self.client_obj.profile_image.name))
                self.assertEqual(self.client_obj.product_images, saved_urls)

                # Remove 1 existing image and add 1 new image
                kept = saved_urls[:2]
                res3 = self.api.patch(
                    f'/api/clients/{self.client_obj.id}/',
                    {
                        'product_images': json.dumps(kept),
                        'product_images[0]': SimpleUploadedFile('p3.png', png_bytes, content_type='image/png'),
                    },
                    format='multipart',
                )
                self.assertEqual(res3.status_code, 200, res3.data)
                self.client_obj.refresh_from_db()
                self.assertEqual(len(self.client_obj.product_images), 3)
                self.assertEqual(self.client_obj.product_images[:2], kept)

                # Clear logo explicitly
                res4 = self.api.patch(
                    f'/api/clients/{self.client_obj.id}/',
                    {'profile_image': ''},
                    format='multipart',
                )
                self.assertEqual(res4.status_code, 200, res4.data)
                self.client_obj.refresh_from_db()
                self.assertFalse(bool(self.client_obj.profile_image))

    def test_unauthorized_workspace_profile_update_rejected(self):
        self.api.force_authenticate(user=self.foreign_user)
        res = self.api.patch(
            f'/api/clients/{self.client_obj.id}/',
            {'brand_tone': 'Hacked'},
            format='multipart',
        )
        self.assertIn(res.status_code, (403, 404))
        self.client_obj.refresh_from_db()
        self.assertNotEqual(self.client_obj.brand_tone, 'Hacked')
