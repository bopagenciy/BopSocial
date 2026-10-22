"""
Unit and Integration Test Suite for BS-4E:
Analytics Dashboard Read API, Capability Badges, Reach Safety, Top-Posts Deduplication, and Tenant Isolation.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    UnifiedPost,
    PlatformPublishLog,
    PostMetric,
)


class AnalyticsDashboardAPITests(TestCase):
    """Exhaustive tests for BS-4E dashboard API contracts and semantic guarantees."""

    def setUp(self):
        self.user = User.objects.create_user(username="bs4e_user", password="password123")
        self.other_user = User.objects.create_user(username="bs4e_other", password="password123")

        self.client_record = Client.objects.create(
            name="Alpha Corp",
            company="Alpha Corp",
            email="alpha@example.com",
            timezone="UTC",
            owner_user=self.user,
            is_active=True,
        )

        self.unauthorized_client = Client.objects.create(
            name="Beta Corp",
            company="Beta Corp",
            email="beta@example.com",
            timezone="UTC",
            owner_user=self.other_user,
            is_active=True,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_01_tenant_isolation_unauthorized_rejected(self):
        """User cannot access analytics for a client they do not own (returns 404)."""
        url = f"/api/analytics/summary/?client_id={self.unauthorized_client.id}"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        url_trends = f"/api/analytics/trends/?client_id={self.unauthorized_client.id}&metric=REACTIONS"
        resp_trends = self.api_client.get(url_trends)
        self.assertEqual(resp_trends.status_code, status.HTTP_404_NOT_FOUND)

        url_top = f"/api/analytics/top-posts/?client_id={self.unauthorized_client.id}"
        resp_top = self.api_client.get(url_top)
        self.assertEqual(resp_top.status_code, status.HTTP_404_NOT_FOUND)

    def test_02_instagram_partial_mode_unavailable_metrics_not_zero(self):
        """Instagram partial mode returns is_available=False and value=None for unavailable metrics, never 0."""
        # Create Instagram credential in partial mode (missing instagram_manage_insights)
        PlatformCredential.objects.create(
            client=self.client_record,
            platform="instagram",
            instagram_account_id="ig_alpha_1",
            access_token="tok_ig",
            scope="instagram_basic,instagram_content_publish",
            is_active=True,
            rate_limit_state={},
        )

        # Create valid Instagram rollups for supported metrics
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="instagram",
            metric_scope="account",
            object_id="ig_alpha_1",
            normalized_metric="FOLLOWERS_TOTAL",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("1500.0000"),
            sample_count=1,
        )
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="instagram",
            metric_scope="post",
            object_id="ig_post_100",
            normalized_metric="REACTIONS",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("45.0000"),
            sample_count=1,
        )

        url = f"/api/analytics/summary/?client_id={self.client_record.id}&platform=instagram&period=day"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # Supported metrics are available with numeric values
        self.assertTrue(data["metrics"]["FOLLOWERS_TOTAL"]["is_available"])
        self.assertEqual(data["metrics"]["FOLLOWERS_TOTAL"]["value"], 1500.0)
        self.assertTrue(data["metrics"]["REACTIONS"]["is_available"])
        self.assertEqual(data["metrics"]["REACTIONS"]["value"], 45.0)

        # Advanced metrics MUST NOT be 0; must be unavailable with explicit explanation
        reach_metric = data["metrics"]["REACH"]
        self.assertFalse(reach_metric["is_available"])
        self.assertIsNone(reach_metric["value"])
        self.assertIn("Not available with current Instagram permissions", reach_metric["unavailable_reason"])
        self.assertIn("Advanced Instagram insights require additional Meta permissions", reach_metric["permission_guidance"])

        video_metric = data["metrics"]["VIDEO_VIEWS"]
        self.assertFalse(video_metric["is_available"])
        self.assertIsNone(video_metric["value"])
        self.assertIn("Not available with current Instagram permissions", video_metric["unavailable_reason"])

    def test_03_reach_aggregation_safety_weekly_monthly_unavailable(self):
        """Weekly and monthly REACH rollups must have is_available=False, never rendering 0 as real reach."""
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="fb_page_1",
            normalized_metric="REACH",
            period="week",
            period_start=date(2026, 10, 19),
            metric_value=Decimal("0.0000"),
            sample_count=7,
            metadata={"is_available": False, "reason": "audience_overlap_non_summable"},
        )

        url = f"/api/analytics/summary/?client_id={self.client_record.id}&platform=facebook&period=week"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        reach_metric = data["metrics"]["REACH"]
        self.assertFalse(reach_metric["is_available"])
        self.assertIsNone(reach_metric["value"])
        self.assertEqual(reach_metric["unavailable_reason"], "Unavailable for aggregated period")
        self.assertEqual(reach_metric["caveat"], "Unique daily audiences cannot be safely summed across days.")

    def test_04_top_posts_deduplication_by_unique_content_identity(self):
        """Top posts endpoint returns exactly ONE ranked entity per provider content object."""
        # Create UnifiedPost
        unified_post = UnifiedPost.objects.create(
            client=self.client_record,
            title="Bop Authored Launch Post",
            content="Launching Bop Social Publishing Engine",
            status="published",
        )

        # Simulate 3 snapshots for the same Bop post across different sync runs / metrics
        now = timezone.now()
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_canonical_1",
            unified_post_id=unified_post.id,
            normalized_metric="REACTIONS",
            metric_value=Decimal("88.0000"),
            bucket_timestamp=now - timedelta(hours=2),
            metadata={"post_type": "post"},
        )
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_canonical_1",
            unified_post_id=unified_post.id,
            normalized_metric="REACTIONS",
            metric_value=Decimal("92.0000"),  # updated value
            bucket_timestamp=now - timedelta(hours=1),
            metadata={"post_type": "post"},
        )
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_canonical_1",
            unified_post_id=unified_post.id,
            normalized_metric="COMMENTS",
            metric_value=Decimal("14.0000"),
            bucket_timestamp=now - timedelta(hours=1),
            metadata={"post_type": "post"},
        )

        # Simulate 1 organic post
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_organic_99",
            unified_post_id=None,
            normalized_metric="REACTIONS",
            metric_value=Decimal("120.0000"),
            bucket_timestamp=now - timedelta(hours=3),
            metadata={"post_type": "post"},
        )

        # Attach PostMetric caption & permalink
        PostMetric.objects.create(
            client=self.client_record,
            platform="facebook",
            post_id="fb_post_canonical_1",
            unified_post=unified_post,
            caption="Launching Bop Social Publishing Engine",
            post_url="https://facebook.com/posts/fb_post_canonical_1",
            post_type="post",
            likes=92,
            comments=14,
        )

        url = f"/api/analytics/top-posts/?client_id={self.client_record.id}&metric=REACTIONS"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # Count MUST be 2 distinct posts, NOT 4 snapshot records
        self.assertEqual(data["count"], 2)
        object_ids = [p["object_id"] for p in data["posts"]]
        self.assertEqual(len(object_ids), len(set(object_ids)))

        # Top 1: Organic post (120 likes)
        top_1 = data["posts"][0]
        self.assertEqual(top_1["object_id"], "fb_post_organic_99")
        self.assertFalse(top_1["is_bop_authored"])
        self.assertEqual(top_1["source_label"], "Organic / External")
        self.assertIsNone(top_1["unified_post_id"])
        self.assertEqual(top_1["ranking_value"], 120.0)

        # Top 2: Bop-authored post (92 likes)
        top_2 = data["posts"][1]
        self.assertEqual(top_2["object_id"], "fb_post_canonical_1")
        self.assertTrue(top_2["is_bop_authored"])
        self.assertEqual(top_2["source_label"], "Published by Bop Social")
        self.assertEqual(top_2["unified_post_id"], unified_post.id)
        self.assertEqual(top_2["ranking_value"], 92.0)
        self.assertEqual(top_2["permalink"], "https://facebook.com/posts/fb_post_canonical_1")
        self.assertIn("COMMENTS", top_2["metrics"])
        self.assertEqual(top_2["metrics"]["COMMENTS"], 14.0)

    def test_05_cross_platform_all_mode_comparability_caveats(self):
        """Cross-platform mode includes comparability warnings for non-comparable metrics."""
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="fb_page_1",
            normalized_metric="CLICKS_TOTAL",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("25.0000"),
            sample_count=1,
        )

        url = f"/api/analytics/summary/?client_id={self.client_record.id}&platform=all"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        # CLICKS_TOTAL has comparability warning when platform=all
        clicks = data["metrics"]["CLICKS_TOTAL"]
        self.assertIsNotNone(clicks["comparability_warning"])
        self.assertIn("Not directly", clicks["comparability_warning"])

    def test_06_data_health_and_capabilities_response(self):
        """Summary view includes data_health array and platform capabilities with correct status badges."""
        PlatformCredential.objects.create(
            client=self.client_record,
            platform="facebook",
            page_id="fb_page_1",
            access_token="tok_fb",
            scope="pages_manage_posts,read_insights",
            is_active=True,
            rate_limit_state={},
        )
        PlatformCredential.objects.create(
            client=self.client_record,
            platform="instagram",
            instagram_account_id="ig_1",
            access_token="tok_ig",
            scope="instagram_basic",
            is_active=True,
            rate_limit_state={},
        )

        url = f"/api/analytics/summary/?client_id={self.client_record.id}"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        self.assertIn("capabilities", data)
        self.assertEqual(data["capabilities"]["facebook"]["status"], "FULL")
        self.assertEqual(data["capabilities"]["instagram"]["status"], "PARTIAL")

        self.assertIn("data_health", data)
        health_platforms = [h["platform"] for h in data["data_health"]]
        self.assertIn("facebook", health_platforms)
        self.assertIn("instagram", health_platforms)

    def test_07_trends_endpoint_instagram_partial_blocks_unavailable_metric(self):
        """Trends endpoint returns is_available=False for unsupported Instagram metrics."""
        url = f"/api/analytics/trends/?client_id={self.client_record.id}&platform=instagram&metric=REACH"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()

        self.assertFalse(data["is_available"])
        self.assertEqual(data["datapoints"], [])
        self.assertIn("Not available with current Instagram permissions", data["unavailable_reason"])
