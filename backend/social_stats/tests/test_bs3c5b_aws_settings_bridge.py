"""
Unit tests for BS-3C.5B: Django AWS Settings Bridge & S3 Preflight Configuration.
Verifies that:
1. Django settings exposes AWS S3 configuration attributes.
2. Environment variables are correctly mapped into dashboard.settings.
3. Bucket aliases (AWS_STORAGE_BUCKET_NAME <-> AWS_S3_BUCKET) work symmetrically.
4. Region aliases (AWS_S3_REGION_NAME <-> AWS_S3_REGION) work symmetrically.
5. AWS_PRESIGNED_URL_EXPIRY is parsed as an integer.
6. validate_s3_configuration() returns valid=True with a complete environment.
7. AWS secrets and keys are strictly excluded from validation outputs and logs.
"""
import importlib
import logging
import os
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings

import dashboard.settings as raw_settings
from social_stats.media_service import (
    validate_s3_configuration,
    get_s3_bucket_name,
    get_s3_region_name,
)


class AWSSettingsBridgeTests(SimpleTestCase):
    def tearDown(self):
        # Ensure raw_settings is reloaded back to current environment after any test reload
        importlib.reload(raw_settings)

    def test_settings_declares_aws_attributes(self):
        """Verify settings module exports all required AWS S3 configuration keys."""
        expected_keys = [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_STORAGE_BUCKET_NAME',
            'AWS_S3_BUCKET',
            'AWS_S3_REGION_NAME',
            'AWS_S3_REGION',
            'AWS_S3_CUSTOM_DOMAIN',
            'AWS_PRESIGNED_URL_EXPIRY',
        ]
        for key in expected_keys:
            self.assertTrue(
                hasattr(raw_settings, key),
                f"dashboard.settings is missing attribute: {key}"
            )

    def test_settings_receives_aws_env_vars(self):
        """Verify environment variables map directly to dashboard.settings attributes."""
        mock_env = {
            'AWS_ACCESS_KEY_ID': 'TEST_KEY_ID_MOCK',
            'AWS_SECRET_ACCESS_KEY': 'TEST_SECRET_KEY_MOCK',
            'AWS_STORAGE_BUCKET_NAME': 'mock-media-bucket',
            'AWS_S3_REGION_NAME': 'us-east-2',
            'AWS_S3_CUSTOM_DOMAIN': 'https://cdn.bopsocial.mock',
            'AWS_PRESIGNED_URL_EXPIRY': '1800',
        }
        with patch.dict(os.environ, mock_env, clear=False):
            importlib.reload(raw_settings)
            self.assertEqual(raw_settings.AWS_ACCESS_KEY_ID, 'TEST_KEY_ID_MOCK')
            self.assertEqual(raw_settings.AWS_SECRET_ACCESS_KEY, 'TEST_SECRET_KEY_MOCK')
            self.assertEqual(raw_settings.AWS_STORAGE_BUCKET_NAME, 'mock-media-bucket')
            self.assertEqual(raw_settings.AWS_S3_BUCKET, 'mock-media-bucket')
            self.assertEqual(raw_settings.AWS_S3_REGION_NAME, 'us-east-2')
            self.assertEqual(raw_settings.AWS_S3_REGION, 'us-east-2')
            self.assertEqual(raw_settings.AWS_S3_CUSTOM_DOMAIN, 'https://cdn.bopsocial.mock')
            self.assertEqual(raw_settings.AWS_PRESIGNED_URL_EXPIRY, 1800)
            self.assertIsInstance(raw_settings.AWS_PRESIGNED_URL_EXPIRY, int)

    def test_bucket_alias_fallback(self):
        """Verify AWS_S3_BUCKET env var populates AWS_STORAGE_BUCKET_NAME when canonical is absent."""
        mock_env = {
            'AWS_S3_BUCKET': 'aliased-bucket-name',
        }
        # Pop canonical key if present in parent environment
        with patch.dict(os.environ, mock_env, clear=False):
            os.environ.pop('AWS_STORAGE_BUCKET_NAME', None)
            importlib.reload(raw_settings)
            self.assertEqual(raw_settings.AWS_STORAGE_BUCKET_NAME, 'aliased-bucket-name')
            self.assertEqual(raw_settings.AWS_S3_BUCKET, 'aliased-bucket-name')

    def test_region_alias_fallback(self):
        """Verify AWS_S3_REGION env var populates AWS_S3_REGION_NAME when canonical is absent."""
        mock_env = {
            'AWS_S3_REGION': 'eu-west-1',
        }
        with patch.dict(os.environ, mock_env, clear=False):
            os.environ.pop('AWS_S3_REGION_NAME', None)
            importlib.reload(raw_settings)
            self.assertEqual(raw_settings.AWS_S3_REGION_NAME, 'eu-west-1')
            self.assertEqual(raw_settings.AWS_S3_REGION, 'eu-west-1')

    def test_presigned_url_expiry_parsing(self):
        """Verify AWS_PRESIGNED_URL_EXPIRY parses numeric strings into integers."""
        with patch.dict(os.environ, {'AWS_PRESIGNED_URL_EXPIRY': '7200'}, clear=False):
            importlib.reload(raw_settings)
            self.assertEqual(raw_settings.AWS_PRESIGNED_URL_EXPIRY, 7200)
            self.assertIsInstance(raw_settings.AWS_PRESIGNED_URL_EXPIRY, int)

    def test_presigned_url_expiry_default(self):
        """Verify AWS_PRESIGNED_URL_EXPIRY defaults to 3600 when unset."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('AWS_PRESIGNED_URL_EXPIRY', None)
            importlib.reload(raw_settings)
            self.assertEqual(raw_settings.AWS_PRESIGNED_URL_EXPIRY, 3600)
            self.assertIsInstance(raw_settings.AWS_PRESIGNED_URL_EXPIRY, int)

    @override_settings(
        AWS_ACCESS_KEY_ID='AKIA_COMPLETE_ENV_KEY',
        AWS_SECRET_ACCESS_KEY='SECRET_COMPLETE_ENV_KEY',
        AWS_STORAGE_BUCKET_NAME='bopsocial-complete-bucket',
        AWS_S3_REGION_NAME='us-east-1',
        AWS_S3_CUSTOM_DOMAIN='',
    )
    def test_validate_s3_configuration_returns_valid_with_complete_env(self):
        """validate_s3_configuration() returns valid=True and 0 errors when all vars are configured."""
        result = validate_s3_configuration()
        self.assertTrue(result['valid'])
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['bucket_configured'])
        self.assertTrue(result['credentials_configured'])

    @override_settings(
        AWS_ACCESS_KEY_ID='AKIA_SUPER_SECRET_KEY_ID_9999',
        AWS_SECRET_ACCESS_KEY='SUPER_SENSITIVE_SECRET_TOKEN_DO_NOT_LEAK',
        AWS_STORAGE_BUCKET_NAME='bopsocial-private-media',
        AWS_S3_REGION_NAME='us-east-1',
    )
    def test_secrets_never_appear_in_validation_output_or_logs(self):
        """Ensure AWS credentials never leak into validation dictionary, errors, warnings, or logs."""
        sensitive_key = 'AKIA_SUPER_SECRET_KEY_ID_9999'
        sensitive_secret = 'SUPER_SENSITIVE_SECRET_TOKEN_DO_NOT_LEAK'

        with self.assertLogs(logger='social_stats', level=logging.DEBUG) as captured_logs:
            # Emit a debug/info log inside context to test log stream
            logger = logging.getLogger('social_stats')
            logger.info("Executing validate_s3_configuration test")
            result = validate_s3_configuration()

            # Ensure secret keys never leak into the validation return structure
            result_str = str(result)
            self.assertNotIn(sensitive_key, result_str)
            self.assertNotIn(sensitive_secret, result_str)
            self.assertNotIn(sensitive_key, str(result['errors']))
            self.assertNotIn(sensitive_secret, str(result['errors']))
            self.assertNotIn(sensitive_key, str(result['warnings']))
            self.assertNotIn(sensitive_secret, str(result['warnings']))

            # Ensure secrets are not in captured logs
            for log_msg in captured_logs.output:
                self.assertNotIn(sensitive_key, log_msg)
                self.assertNotIn(sensitive_secret, log_msg)
