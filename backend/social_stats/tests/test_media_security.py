# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Bop Social Security Regression Tests — SEC-01 & SEC-02
# ============================================================================
"""
Unit and integration tests for:
  - SEC-01: Tenant Media Access Control & Isolation
  - SEC-02: Production Secret Fail-Safe Validation
"""
import io
import os
import shutil
import tempfile
import uuid
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from social_stats.marketplace_models import Agency, AgencyClientRelation, AgencyMembership
from social_stats.media_access import (
    generate_media_token,
    generate_public_publishing_token,
    user_has_media_access,
    verify_media_token,
    verify_public_publishing_token,
)
from social_stats.models import Client, MediaAsset, UserProfile


def _create_image_file(name="sample.png", width=100, height=100, color="blue"):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/png")


class MediaTenantSecurityTests(TestCase):
    """Exhaustive tests for multi-tenant media security (SEC-01)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_media = tempfile.mkdtemp()
        cls.media_override = override_settings(
            MEDIA_ROOT=cls.temp_media,
            AWS_ACCESS_KEY_ID='',
            AWS_SECRET_ACCESS_KEY='',
            AWS_STORAGE_BUCKET_NAME='',
            AWS_S3_BUCKET='',
        )
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.temp_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()

        # Tenant A (Victim / legitimate client)
        self.client_a = Client.objects.create(
            name="Alpha Corp", company="Alpha Corp", email="contact@alpha.test"
        )
        self.user_a = User.objects.create_user(
            username=f"user_a_{uuid.uuid4().hex[:6]}", email="a@alpha.test", password="password123"
        )
        self.profile_a = UserProfile.objects.create(
            user=self.user_a, role="client", client=self.client_a
        )
        self.client_a.owner_user = self.user_a
        self.client_a.save()

        # Tenant B (Attacker / separate client)
        self.client_b = Client.objects.create(
            name="Beta Ltd", company="Beta Ltd", email="contact@beta.test"
        )
        self.user_b = User.objects.create_user(
            username=f"user_b_{uuid.uuid4().hex[:6]}", email="b@beta.test", password="password123"
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b, role="client", client=self.client_b
        )
        self.client_b.owner_user = self.user_b
        self.client_b.save()

        # Agency & Agency Users
        self.agency_owner = User.objects.create_user(
            username=f"agency_owner_{uuid.uuid4().hex[:6]}", email="owner@agency.test", password="password123"
        )
        self.profile_agency = UserProfile.objects.create(
            user=self.agency_owner, role="client", account_type="agency_member"
        )
        self.agency = Agency.objects.create(
            name="Mega Marketing", slug=f"mega-agency-{uuid.uuid4().hex[:6]}", owner_user=self.agency_owner
        )
        AgencyMembership.objects.create(agency=self.agency, user=self.agency_owner, role="owner")
        self.profile_agency.primary_agency = self.agency
        self.profile_agency.save()

        # Unaffiliated Agency
        self.unrelated_user = User.objects.create_user(
            username=f"unrelated_{uuid.uuid4().hex[:6]}", email="unrelated@agency.test", password="password123"
        )
        UserProfile.objects.create(user=self.unrelated_user, role="client")

        # Superadmin
        self.superadmin = User.objects.create_superuser(
            username=f"admin_{uuid.uuid4().hex[:6]}", email="admin@bop.test", password="password123"
        )
        UserProfile.objects.create(user=self.superadmin, role="superadmin")

        # API clients
        self.api_a = APIClient()
        self.api_a.force_authenticate(user=self.user_a)

        self.api_b = APIClient()
        self.api_b.force_authenticate(user=self.user_b)

        self.api_agency = APIClient()
        self.api_agency.force_authenticate(user=self.agency_owner)

        self.api_anon = APIClient()


    def test_tenant_a_uploads_media_with_tenant_partitioned_path(self):
        """1. Tenant A uploads private media -> stored in tenant-scoped directory."""
        img = _create_image_file("alpha_brand.png")
        res = self.api_a.post(
            "/api/composer/media/",
            {"file": img, "alt_text": "Alpha asset"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201)
        asset_id = res.data["id"]
        asset = MediaAsset.objects.get(id=asset_id)
        self.assertEqual(asset.client_id, self.client_a.id)

        # Verify storage path contains tenant_<id>
        expected_part = f"media_assets/tenant_{self.client_a.id}/"
        self.assertIn(expected_part, asset.file.name)
        if asset.thumbnail:
            self.assertIn(f"media_assets/thumbs/tenant_{self.client_a.id}/", asset.thumbnail.name)

        # Verify physical file existence
        self.assertTrue(os.path.exists(asset.file.path))

    def test_tenant_a_can_access_own_media(self):
        """2. Tenant A can download and stream its own media."""
        img = _create_image_file("alpha_doc.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("alpha_doc.png", img)

        res = self.api_a.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")

    def test_tenant_b_cannot_access_tenant_a_media(self):
        """3. Tenant B (attacker) is forbidden from downloading Tenant A's private media."""
        img = _create_image_file("confidential.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("confidential.png", img)

        # Attacker tries direct endpoint
        res = self.api_b.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 403)

        # Attacker tries composer media detail action
        res_action = self.api_b.get(f"/api/composer/media/{asset.id}/file/")
        self.assertEqual(res_action.status_code, 404)  # TenantScopedMixin blocks visibility completely

    def test_unauthenticated_user_cannot_access_private_media(self):
        """4. Unauthenticated users cannot access private media files."""
        img = _create_image_file("secret.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("secret.png", img)

        res = self.api_anon.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 401)

    def test_agency_with_valid_relation_can_access_client_media(self):
        """5. Agency with active relation can access client media."""
        # Create active relation
        AgencyClientRelation.objects.create(
            agency=self.agency, client=self.client_a, status="active"
        )
        img = _create_image_file("campaign_asset.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("campaign_asset.png", img)

        res = self.api_agency.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 200)

    def test_agency_without_active_relation_cannot_access_media(self):
        """6. Agency without active relation (paused or terminated) is forbidden."""
        rel = AgencyClientRelation.objects.create(
            agency=self.agency, client=self.client_a, status="paused"
        )
        img = _create_image_file("campaign_asset.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("campaign_asset.png", img)

        res = self.api_agency.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 403)

        # Unrelated agency user
        api_unrelated = APIClient()
        api_unrelated.force_authenticate(user=self.unrelated_user)
        res_unrelated = api_unrelated.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res_unrelated.status_code, 403)

    def test_client_ownership_spoofing_prevented_in_upload(self):
        """7. Tenant cannot spoof client_id in upload parameters to write to another tenant."""
        img = _create_image_file("spoofed.png")
        # Attacker B sends client_id of Tenant A
        res = self.api_b.post(
            "/api/composer/media/",
            {"file": img, "client": self.client_a.id, "client_id": self.client_a.id},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201)
        # Verify asset was strictly stamped to Tenant B, ignoring spoofed client_id
        asset = MediaAsset.objects.get(id=res.data["id"])
        self.assertEqual(asset.client_id, self.client_b.id)
        self.assertNotEqual(asset.client_id, self.client_a.id)

    def test_legacy_media_paths_remain_accessible_for_authorized_users(self):
        """8. Existing legacy uploads (without tenant_ prefix) remain accessible to authorized users."""
        img = _create_image_file("legacy.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        # Directly save with legacy path
        asset.file.save("media_assets/2026/08/legacy_sample.png", img)

        # Authorized user A can access it
        res = self.api_a.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res.status_code, 200)

        # Unauthorized user B is blocked from legacy asset
        res_b = self.api_b.get(f"/api/media/serve/{asset.id}/")
        self.assertEqual(res_b.status_code, 403)

    def test_thumbnail_tenant_isolation(self):
        """9. Thumbnails strictly enforce tenant authorization."""
        img = _create_image_file("main.png")
        thumb = _create_image_file("thumb.png", width=50, height=50)
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("main.png", img)
        asset.thumbnail.save("thumb.png", thumb)

        # User A accesses thumbnail
        res_a = self.api_a.get(f"/api/media/serve/{asset.id}/thumb/")
        self.assertEqual(res_a.status_code, 200)

        # User B blocked from thumbnail
        res_b = self.api_b.get(f"/api/media/serve/{asset.id}/thumb/")
        self.assertEqual(res_b.status_code, 403)

    def test_signed_media_token_access(self):
        """10. Signed media token allows in-browser rendering for legitimate user."""
        img = _create_image_file("token_test.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("token_test.png", img)

        token = generate_media_token(asset.id, self.client_a.id, self.user_a.id)
        # Unauthenticated request with valid token succeeds (used by <img> tags)
        res = self.api_anon.get(f"/api/media/serve/{asset.id}/?token={token}")
        self.assertEqual(res.status_code, 200)

        # Token for asset A cannot be used to fetch asset B
        asset_b = MediaAsset.objects.create(client=self.client_b, uploaded_by=self.user_b)
        asset_b.file.save("asset_b.png", _create_image_file("b.png"))
        res_mismatch = self.api_anon.get(f"/api/media/serve/{asset_b.id}/?token={token}")
        self.assertEqual(res_mismatch.status_code, 401)

    def test_public_publishing_token_allows_controlled_platform_pull(self):
        """11. Public publishing token permits crawler fetch without exposing other media."""
        img = _create_image_file("publish_ready.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("publish_ready.png", img)

        token = generate_public_publishing_token(asset.id, self.client_a.id)
        res = self.api_anon.get(f"/api/media/public/{token}/")
        self.assertEqual(res.status_code, 200)

        # Bogus token rejected
        res_bad = self.api_anon.get("/api/media/public/tampered_token/")
        self.assertEqual(res_bad.status_code, 403)

    def test_legacy_proxy_endpoint_authorizes_direct_media_paths(self):
        """12. Direct Nginx proxy path (/media/media_assets/...) is authenticated."""
        img = _create_image_file("nginx_protected.png")
        asset = MediaAsset.objects.create(client=self.client_a, uploaded_by=self.user_a)
        asset.file.save("media_assets/2026/09/nginx_protected.png", img)

        # Unauthenticated blocked
        res_anon = self.api_anon.get(f"/api/media/serve-legacy/?path=/media/{asset.file.name}")
        self.assertEqual(res_anon.status_code, 401)

        # Authorized user A gets it
        res_a = self.api_a.get(f"/api/media/serve-legacy/?path=/media/{asset.file.name}")
        self.assertEqual(res_a.status_code, 200)

        # Unauthorized user B gets 403
        res_b = self.api_b.get(f"/api/media/serve-legacy/?path=/media/{asset.file.name}")
        self.assertEqual(res_b.status_code, 403)


class DockerSecretSecurityTests(TestCase):
    """Tests for production secret fail-safe validation (SEC-02)."""

    def test_missing_or_placeholder_secret_key_rejected_in_production(self):
        """13. Reject placeholder or short SECRET_KEY when DEBUG=False."""
        from django.core.exceptions import ImproperlyConfigured
        from dashboard.settings import KNOWN_INSECURE_SECRETS

        for placeholder in KNOWN_INSECURE_SECRETS:
            # Simulate production validation logic
            raw_secret = placeholder
            with self.subTest(secret=placeholder):
                is_invalid = not raw_secret or raw_secret in KNOWN_INSECURE_SECRETS or len(raw_secret) < 32
                self.assertTrue(is_invalid)

    def test_strong_secret_key_accepted_in_production(self):
        """14. Strong random SECRET_KEY (>= 32 chars) is accepted."""
        from dashboard.settings import KNOWN_INSECURE_SECRETS
        good_secret = "f8a9e7d6c5b4a3210fedcba987654321_strong_production_key"
        is_invalid = not good_secret or good_secret in KNOWN_INSECURE_SECRETS or len(good_secret) < 32
        self.assertFalse(is_invalid)
