import io
import tempfile
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from social_stats import media_service
from social_stats.models import Client, ClientUserRole, UnifiedPost, UserProfile


def _make_png(name='cal.png'):
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), color=(40, 100, 200)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class BS10E3CalendarMultiplatformTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cal_owner_10e3',
            email='cal_owner_10e3@test.local',
            password='Password123!',
        )
        self.client_obj = Client.objects.create(
            name='Bop Calendar',
            company='Bop Calendar',
            email='cal10e3@test.local',
            owner_user=self.user,
            timezone='America/Bogota',
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
        self.api = APIClient()

    def test_calendar_returns_multiplatform_post_with_authorized_media_and_filters_without_duplication(self):
        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media), patch('social_stats.media_service._s3_enabled', return_value=False):
                asset = media_service.upload_media(
                    _make_png(),
                    client_id=self.client_obj.id,
                    uploaded_by_id=self.user.id,
                )
                post = UnifiedPost.objects.create(
                    client=self.client_obj,
                    created_by=self.user,
                    title='BOP-001',
                    content='Multiplatform scheduled post',
                    media_type='image',
                    media_urls=[f'asset:{asset.id}'],
                    target_platforms=['facebook', 'instagram'],
                    status='pending_approval',
                    scheduled_at=datetime(2026, 11, 27, 15, 0, tzinfo=dt_timezone.utc),
                )

                self.api.force_authenticate(user=self.user)

                # All platforms -> single non-duplicated record with authorized media URL
                res_all = self.api.get(
                    '/api/calendar/posts/',
                    {'client_id': self.client_obj.id, 'month': 11, 'year': 2026},
                )
                self.assertEqual(res_all.status_code, 200)
                day_items = res_all.data.get('2026-11-27', [])
                self.assertEqual(len(day_items), 1)
                item = day_items[0]
                self.assertEqual(item['unified_post_id'], post.id)
                self.assertEqual(item['target_platforms'], ['facebook', 'instagram'])
                self.assertEqual(item['status'], 'pending_approval')
                self.assertIn(f'/api/media/serve/{asset.id}/', item['media_url'])
                self.assertIn('token=', item['media_url'])
                self.assertEqual(item['media_urls'], [item['media_url']])

                # Facebook filter finds the post
                res_fb = self.api.get(
                    '/api/calendar/posts/',
                    {'client_id': self.client_obj.id, 'month': 11, 'year': 2026, 'platform': 'facebook'},
                )
                self.assertEqual(len(res_fb.data.get('2026-11-27', [])), 1)

                # Instagram filter finds the post
                res_ig = self.api.get(
                    '/api/calendar/posts/',
                    {'client_id': self.client_obj.id, 'month': 11, 'year': 2026, 'platform': 'instagram'},
                )
                self.assertEqual(len(res_ig.data.get('2026-11-27', [])), 1)

                # Unselected platform filter excludes the post
                res_li = self.api.get(
                    '/api/calendar/posts/',
                    {'client_id': self.client_obj.id, 'month': 11, 'year': 2026, 'platform': 'linkedin'},
                )
                self.assertEqual(len(res_li.data.get('2026-11-27', [])), 0)
