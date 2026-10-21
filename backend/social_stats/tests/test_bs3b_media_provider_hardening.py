"""
Tests for Phase BS-3B: Media Pipeline & Provider Hardening.
Covers:
- S3 configuration validation
- Provider-safe public HTTPS URL validation (rejecting localhost, RFC1918 private IPs)
- Provider media resolution (Meta requires public HTTPS; direct-upload providers allow local storage)
- Publisher registry & unsupported platform defense
- Composer serializer rejection of unsupported platforms
- Facebook/Instagram publisher media validation guardrails
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from social_stats.media_service import (
    validate_s3_configuration,
    is_public_https_url,
    get_provider_media_url,
    validate_media_url_for_provider,
)
from social_stats.publishers import (
    is_platform_supported,
    SUPPORTED_PUBLISHERS,
    UNSUPPORTED_PUBLISHERS,
    get_publisher,
    PublishError,
)
from social_stats.composer_serializers import UnifiedPostSerializer
from social_stats.publishers.facebook import FacebookPublisher
from social_stats.publishers.instagram import InstagramPublisher


class S3ConfigurationValidationTests(SimpleTestCase):
    @override_settings(
        AWS_ACCESS_KEY_ID='AKIA_MOCK_TEST_123',
        AWS_SECRET_ACCESS_KEY='secret_mock_test_key_456',
        AWS_STORAGE_BUCKET_NAME='bopsocial-media-prod',
        AWS_S3_REGION_NAME='us-east-1',
        AWS_S3_CUSTOM_DOMAIN='cdn.bopsocial.com',
    )
    def test_valid_s3_configuration(self):
        result = validate_s3_configuration()
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)
        self.assertTrue(result['bucket_configured'])
        self.assertTrue(result['credentials_configured'])

    @override_settings(
        AWS_ACCESS_KEY_ID='',
        AWS_SECRET_ACCESS_KEY='',
        AWS_STORAGE_BUCKET_NAME='',
        AWS_S3_BUCKET='',
    )
    def test_missing_s3_credentials_and_bucket(self):
        result = validate_s3_configuration()
        self.assertFalse(result['valid'])
        self.assertFalse(result['bucket_configured'])
        self.assertFalse(result['credentials_configured'])
        err_str = ' '.join(result['errors'])
        self.assertIn('AWS_STORAGE_BUCKET_NAME', err_str)
        self.assertIn('AWS_ACCESS_KEY_ID is missing or empty', err_str)
        self.assertIn('AWS_SECRET_ACCESS_KEY is missing or empty', err_str)

    @override_settings(
        AWS_ACCESS_KEY_ID='AKIA_MOCK',
        AWS_SECRET_ACCESS_KEY='secret_mock',
        AWS_STORAGE_BUCKET_NAME='mybucket',
        AWS_S3_CUSTOM_DOMAIN='http://localhost:9000/mybucket',
    )
    def test_s3_custom_domain_localhost_rejected(self):
        result = validate_s3_configuration()
        self.assertFalse(result['valid'])
        self.assertTrue(any('localhost' in e for e in result['errors']))


class PublicHttpsUrlValidationTests(SimpleTestCase):
    def test_valid_public_https_domains(self):
        valid_urls = [
            'https://bopsocial-media.s3.amazonaws.com/uploads/2026/img.jpg',
            'https://cdn.bopsocial.com/media/assets/pic.png',
            'https://media.myclient.org/video.mp4',
        ]
        for url in valid_urls:
            ok, reason = is_public_https_url(url)
            self.assertTrue(ok, f"Expected {url} to be valid, got: {reason}")
            self.assertEqual(reason, '')

    def test_rejects_non_https(self):
        ok, reason = is_public_https_url('http://cdn.bopsocial.com/media/pic.jpg')
        self.assertFalse(ok)
        self.assertIn('HTTPS', reason)

    def test_rejects_localhost_and_loopback(self):
        rejected = [
            'https://localhost:8000/media/pic.jpg',
            'https://127.0.0.1:8000/media/pic.jpg',
            'https://127.0.0.1/video.mp4',
            'https://testserver/media/pic.jpg',
            'https://web/media/pic.jpg',
        ]
        for url in rejected:
            ok, reason = is_public_https_url(url)
            self.assertFalse(ok, f"Expected {url} to be rejected, but it passed")

    def test_rejects_private_rfc1918_ips(self):
        private_urls = [
            'https://10.0.0.15/uploads/img.jpg',
            'https://192.168.1.100:8443/media/pic.jpg',
            'https://172.16.0.5/media/video.mp4',
        ]
        for url in private_urls:
            ok, reason = is_public_https_url(url)
            self.assertFalse(ok, f"Expected private IP {url} to be rejected")
            self.assertIn('private IP', reason)

    def test_rejects_empty_or_none(self):
        self.assertFalse(is_public_https_url('')[0])
        self.assertFalse(is_public_https_url(None)[0])


class ProviderMediaUrlResolutionTests(SimpleTestCase):
    def _mock_asset(self, url='http://localhost:8000/media/uploads/photo.jpg', name='photo.jpg'):
        file_mock = MagicMock()
        file_mock.url = url
        file_mock.name = name
        asset = SimpleNamespace(
            id=123,
            file=file_mock,
            get_public_publishing_url=MagicMock(return_value=url),
        )
        return asset

    @override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='', AWS_STORAGE_BUCKET_NAME='', BACKEND_PUBLIC_URL='')
    def test_meta_rejects_local_media_url_without_public_hosting(self):
        asset = self._mock_asset('http://localhost:8000/media/uploads/photo.jpg')
        with self.assertRaises(PublishError) as ctx:
            get_provider_media_url(asset, 'instagram', lang='en')
        self.assertEqual(ctx.exception.code, 'public_media_required')
        self.assertIn('Public media hosting is required', str(ctx.exception))

    @override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='', AWS_STORAGE_BUCKET_NAME='', BACKEND_PUBLIC_URL='')
    def test_meta_rejects_with_spanish_locale(self):
        asset = self._mock_asset('http://localhost:8000/media/uploads/photo.jpg')
        with self.assertRaises(PublishError) as ctx:
            get_provider_media_url(asset, 'facebook', lang='es')
        self.assertEqual(ctx.exception.code, 'public_media_required')
        self.assertIn('Se requiere alojamiento público multimedia', str(ctx.exception))

    @override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='', AWS_STORAGE_BUCKET_NAME='', BACKEND_PUBLIC_URL='')
    def test_direct_upload_providers_allow_local_storage(self):
        local_url = 'http://localhost:8000/media/uploads/video.mp4'
        asset = self._mock_asset(local_url)
        for prov in ('youtube', 'linkedin', 'google_my_business', 'gmb'):
            resolved = get_provider_media_url(asset, prov)
            self.assertEqual(resolved, local_url)

    @override_settings(
        AWS_ACCESS_KEY_ID='AKIA_MOCK',
        AWS_SECRET_ACCESS_KEY='secret_mock',
        AWS_STORAGE_BUCKET_NAME='bopsocial-prod',
        AWS_S3_REGION_NAME='us-east-1',
    )
    @patch('social_stats.media_service.presigned_url')
    def test_meta_accepts_valid_public_s3_url(self, mock_presign):
        mock_presign.return_value = 'https://bopsocial-prod.s3.us-east-1.amazonaws.com/uploads/photo.jpg'
        asset = self._mock_asset()
        resolved = get_provider_media_url(asset, 'instagram')
        self.assertEqual(resolved, 'https://bopsocial-prod.s3.us-east-1.amazonaws.com/uploads/photo.jpg')

    def test_validate_media_url_for_provider_rejects_localhost(self):
        with self.assertRaises(PublishError) as ctx:
            validate_media_url_for_provider('http://localhost:8000/img.jpg', 'facebook', lang='en')
        self.assertEqual(ctx.exception.code, 'invalid_media_url')

    def test_validate_media_url_for_provider_accepts_valid_https(self):
        url = 'https://cdn.bopsocial.com/img.jpg'
        out = validate_media_url_for_provider(url, 'facebook')
        self.assertEqual(out, url)


class ProviderCapabilityRegistryTests(SimpleTestCase):
    def test_supported_publishers_registry(self):
        for p in ('facebook', 'instagram', 'youtube', 'linkedin', 'google_my_business', 'gmb'):
            self.assertTrue(is_platform_supported(p), f"{p} should be supported")
            self.assertIn(p, SUPPORTED_PUBLISHERS)

    def test_unsupported_publishers_registry(self):
        for p in ('tiktok', 'twitter', 'x', 'pinterest'):
            self.assertFalse(is_platform_supported(p), f"{p} should be marked unsupported")
            self.assertIn(p, UNSUPPORTED_PUBLISHERS)

    def test_get_publisher_raises_for_unsupported_platform(self):
        for p in ('tiktok', 'twitter', 'pinterest'):
            with self.assertRaises(PublishError) as ctx:
                get_publisher(p)
            self.assertEqual(ctx.exception.code, 'unsupported_platform')
            self.assertFalse(ctx.exception.supported)


class ComposerSerializerValidationTests(SimpleTestCase):
    def test_serializer_rejects_unsupported_platforms(self):
        serializer = UnifiedPostSerializer()
        with self.assertRaises(ValidationError) as ctx:
            serializer.validate_target_platforms(['facebook', 'tiktok'])
        self.assertIn('not currently supported', str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            serializer.validate_target_platforms(['twitter'])
        self.assertIn('not currently supported', str(ctx.exception))

    def test_serializer_accepts_supported_platforms(self):
        serializer = UnifiedPostSerializer()
        valid = ['facebook', 'instagram', 'youtube', 'linkedin', 'google_my_business']
        validated = serializer.validate_target_platforms(valid)
        self.assertEqual(validated, valid)


class PublisherMediaGuardrailTests(SimpleTestCase):
    def _fake_credential(self):
        return SimpleNamespace(
            access_token='tok-123',
            page_id='10001',
            instagram_account_id='17840001',
            page_name='Test',
        )

    def test_facebook_publisher_rejects_localhost_image(self):
        pub = FacebookPublisher()
        with self.assertRaises(PublishError) as ctx:
            pub.publish_image(self._fake_credential(), 'Test', ['http://localhost:8000/img.jpg'])
        self.assertEqual(ctx.exception.code, 'invalid_media_url')

    def test_facebook_publisher_rejects_localhost_video(self):
        pub = FacebookPublisher()
        with self.assertRaises(PublishError) as ctx:
            pub.publish_video(self._fake_credential(), 'Test', 'http://127.0.0.1:8000/v.mp4')
        self.assertEqual(ctx.exception.code, 'invalid_media_url')

    def test_instagram_publisher_rejects_localhost_image(self):
        pub = InstagramPublisher()
        with self.assertRaises(PublishError) as ctx:
            pub.publish_image(self._fake_credential(), 'Test', ['http://localhost:8000/img.jpg'])
        self.assertEqual(ctx.exception.code, 'invalid_media_url')

    def test_instagram_publisher_rejects_localhost_video(self):
        pub = InstagramPublisher()
        with self.assertRaises(PublishError) as ctx:
            pub.publish_video(self._fake_credential(), 'Test', 'https://localhost:8000/v.mp4')
        self.assertEqual(ctx.exception.code, 'invalid_media_url')
