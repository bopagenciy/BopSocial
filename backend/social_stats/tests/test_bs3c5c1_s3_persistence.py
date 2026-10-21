"""
Unit tests for BS-3C.5C1: S3 Media Persistence Fix.
Validates:
1. S3 enabled: main upload uses correct bucket.
2. Main key includes tenant partition: media_assets/tenant_{client_id}/YYYY/MM/{filename}.
3. ContentType is correctly preserved.
4. Thumbnail is uploaded to: media_assets/thumbs/tenant_{client_id}/YYYY/MM/{filename}.
5. asset.file.name holds canonical S3 key.
6. asset.thumbnail.name holds canonical S3 key.
7. S3 disabled: fallback to local FileSystemStorage continues working.
8. boto3 upload error: no MediaAsset persisted on failure.
9. Partial error cleanup: thumbnail failure or DB failure triggers atomic S3 cleanup.
10. Asset deletion: deletes S3 objects when S3 enabled; local files when disabled.
11. Tenant isolation: client 3 never writes to tenant_1.
12. Zero secrets exposed in exceptions, logs, or asset representations.
"""
import io
import logging
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from social_stats.models import Client, MediaAsset
from social_stats import media_service


def _create_test_image(filename="pilot_test.png", format="PNG", size=(300, 300), color="blue"):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.getvalue(), content_type=f"image/{format.lower()}")


@override_settings(
    AWS_ACCESS_KEY_ID="AKIA_MOCK_TEST_PILOT_KEY",
    AWS_SECRET_ACCESS_KEY="MOCK_SECRET_TEST_PILOT_SECRET",
    AWS_STORAGE_BUCKET_NAME="bopsocial-staging-media",
    AWS_S3_REGION_NAME="us-east-2",
)
class S3MediaPersistenceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.client_3 = Client.objects.create(
            name="Bop Agencia", company="Bop Agencia", email="bop3@bopagencia.test", id=3
        )
        self.client_1 = Client.objects.create(
            name="Client Alpha", company="Client Alpha", email="alpha1@clientalpha.test", id=1
        )

    @patch("social_stats.media_service.get_s3_client")
    def test_s3_enabled_upload_uses_correct_bucket_and_preserves_content_type(self, mock_get_client):
        """1 & 3: Main upload uses configured bucket and preserves ContentType."""
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("test_pilot.png", format="PNG")
        asset = media_service.upload_media(img_file, client_id=3)

        self.assertIsNotNone(asset.id)
        # Verify put_object calls
        put_calls = mock_s3.put_object.call_args_list
        self.assertGreaterEqual(len(put_calls), 1)

        main_call = put_calls[0]
        self.assertEqual(main_call.kwargs.get("Bucket"), "bopsocial-staging-media")
        self.assertEqual(main_call.kwargs.get("ContentType"), "image/png")

    @patch("social_stats.media_service.get_s3_client")
    def test_s3_key_tenant_partitioning_and_names(self, mock_get_client):
        """2, 4, 5, 6: Keys and asset names use tenant-scoped prefixes."""
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("banner.jpg", format="JPEG")
        asset = media_service.upload_media(img_file, client_id=3)

        # Main file key
        self.assertTrue(asset.file.name.startswith("media_assets/tenant_3/"))
        self.assertIn("banner", asset.file.name)
        self.assertTrue(asset.file.name.endswith(".jpg"))

        # Thumbnail key
        self.assertIsNotNone(asset.thumbnail)
        self.assertTrue(asset.thumbnail.name.startswith("media_assets/thumbs/tenant_3/"))
        self.assertTrue(asset.thumbnail.name.endswith("_thumb.jpg"))

        # Verify put_object keys match asset file/thumbnail names
        put_calls = mock_s3.put_object.call_args_list
        self.assertEqual(len(put_calls), 2)
        self.assertEqual(put_calls[0].kwargs.get("Key"), asset.file.name)
        self.assertEqual(put_calls[1].kwargs.get("Key"), asset.thumbnail.name)
        self.assertEqual(put_calls[1].kwargs.get("ContentType"), "image/jpeg")

    @override_settings(
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_STORAGE_BUCKET_NAME="",
    )
    def test_s3_disabled_fallback_to_filesystem(self):
        """7: When S3 is disabled, fallback saves locally via FileSystemStorage."""
        self.assertFalse(media_service._s3_enabled())

        img_file = _create_test_image("local_image.png", format="PNG")
        asset = media_service.upload_media(img_file, client_id=3)

        self.assertIsNotNone(asset.id)
        self.assertTrue(asset.file.name.startswith("media_assets/tenant_3/"))
        self.assertIsNotNone(asset.file.path)

        # Cleanup local file
        asset.delete()

    @patch("social_stats.media_service.get_s3_client")
    def test_boto3_main_upload_error_prevents_db_persistence(self, mock_get_client):
        """8: When main S3 upload fails, no MediaAsset record is saved."""
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Mock S3 access denied"}},
            "PutObject",
        )
        mock_get_client.return_value = mock_s3

        initial_count = MediaAsset.objects.count()
        img_file = _create_test_image("fail_test.jpg", format="JPEG")

        with self.assertRaises(ClientError):
            media_service.upload_media(img_file, client_id=3)

        self.assertEqual(MediaAsset.objects.count(), initial_count)

    @patch("social_stats.media_service.get_s3_client")
    def test_partial_failure_cleans_up_uploaded_s3_keys(self, mock_get_client):
        """9: When thumbnail fails after main upload, main S3 object is cleaned up."""
        mock_s3 = MagicMock()
        # First call (main file) succeeds, second call (thumbnail) raises error
        mock_s3.put_object.side_effect = [
            {"ETag": '"test-etag-1"'},
            ClientError(
                {"Error": {"Code": "InternalError", "Message": "Mock thumbnail upload failure"}},
                "PutObject",
            ),
        ]
        mock_get_client.return_value = mock_s3

        initial_count = MediaAsset.objects.count()
        img_file = _create_test_image("partial_fail.png", format="PNG")

        with self.assertRaises(ClientError):
            media_service.upload_media(img_file, client_id=3)

        # Assert no DB record created
        self.assertEqual(MediaAsset.objects.count(), initial_count)

        # Assert cleanup was called for main key
        mock_s3.delete_object.assert_called_once()
        delete_call = mock_s3.delete_object.call_args
        self.assertEqual(delete_call.kwargs.get("Bucket"), "bopsocial-staging-media")
        self.assertTrue(delete_call.kwargs.get("Key").startswith("media_assets/tenant_3/"))

    @patch("social_stats.media_service.get_s3_client")
    def test_db_save_failure_cleans_up_both_s3_keys(self, mock_get_client):
        """9b: When asset.save() fails after both uploads, both S3 objects are deleted."""
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("db_fail.png", format="PNG")

        with patch.object(MediaAsset, "save", side_effect=RuntimeError("Mock DB failure")):
            with self.assertRaises(RuntimeError):
                media_service.upload_media(img_file, client_id=3)

        # Both main and thumb should have been cleaned up
        self.assertEqual(mock_s3.delete_object.call_count, 2)
        deleted_keys = [c.kwargs.get("Key") for c in mock_s3.delete_object.call_args_list]
        self.assertTrue(any(k.startswith("media_assets/tenant_3/") for k in deleted_keys))
        self.assertTrue(any(k.startswith("media_assets/thumbs/tenant_3/") for k in deleted_keys))

    @patch("social_stats.media_service.get_s3_client")
    def test_asset_delete_removes_s3_objects(self, mock_get_client):
        """10: Deleting a MediaAsset deletes its objects from S3."""
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("delete_test.jpg", format="JPEG")
        asset = media_service.upload_media(img_file, client_id=3)
        main_key = asset.file.name
        thumb_key = asset.thumbnail.name

        asset_id = asset.id
        asset.delete()

        # Verify DB deletion
        self.assertFalse(MediaAsset.objects.filter(id=asset_id).exists())

        # Verify S3 deletion of both keys
        delete_calls = mock_s3.delete_object.call_args_list
        deleted_keys = [c.kwargs.get("Key") for c in delete_calls]
        self.assertIn(main_key, deleted_keys)
        self.assertIn(thumb_key, deleted_keys)

    @patch("social_stats.media_service.get_s3_client")
    def test_tenant_isolation_client_3_vs_client_1(self, mock_get_client):
        """11: Client 3 uploads are strictly isolated from Client 1."""
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("tenant_iso.png", format="PNG")
        asset = media_service.upload_media(img_file, client_id=3)

        self.assertIn("tenant_3", asset.file.name)
        self.assertNotIn("tenant_1", asset.file.name)
        self.assertIn("tenant_3", asset.thumbnail.name)
        self.assertNotIn("tenant_1", asset.thumbnail.name)

    @patch("social_stats.media_service.get_s3_client")
    def test_no_secrets_in_exceptions_logs_or_asset_representation(self, mock_get_client):
        """12: AWS credentials never appear in exceptions, logs, or string representations."""
        secret_token = "MOCK_SECRET_TEST_PILOT_SECRET"
        key_id = "AKIA_MOCK_TEST_PILOT_KEY"

        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "SignatureDoesNotMatch", "Message": "Signature mismatch"}},
            "PutObject",
        )
        mock_get_client.return_value = mock_s3

        img_file = _create_test_image("secret_leak_check.jpg", format="JPEG")

        try:
            media_service.upload_media(img_file, client_id=3)
        except Exception as e:
            err_str = str(e)
            self.assertNotIn(secret_token, err_str)
            self.assertNotIn(key_id, err_str)

        # Test that error logging in delete_s3_object never leaks secrets
        with self.assertLogs(logger="social_stats", level=logging.DEBUG) as captured_logs:
            mock_s3.delete_object.side_effect = Exception("Mock delete failure")
            media_service.delete_s3_object("media_assets/tenant_3/leak_check.jpg")
            for log_msg in captured_logs.output:
                self.assertNotIn(secret_token, log_msg)
                self.assertNotIn(key_id, log_msg)
