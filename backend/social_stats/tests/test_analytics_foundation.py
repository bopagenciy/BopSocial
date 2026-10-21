"""
Unit and integration tests for BS-4B: Canonical Analytics Metric Registry & Snapshot Foundation.
Covers registry validation, normalizers, snapshot idempotency, dimensions hashing,
tenant isolation, UnifiedPost linkage, external posts, derived metrics, and capability degradation.
"""
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from social_stats.models import (
    Client,
    PlatformCredential,
    PostMetric,
    UnifiedPost,
    PlatformPublishLog,
    SocialMetricSnapshot,
    SocialMetricRollup,
)
from social_stats.analytics import (
    AggregationBehavior,
    MetricValueType,
    MetricUnit,
    FreshnessState,
    CANONICAL_METRICS,
    get_metric_definition,
    is_valid_metric,
    get_canonical_keys,
    SupportLevel,
    get_provider_capability,
    normalize_facebook_metric,
    normalize_instagram_metric,
    normalize_metric,
    calculate_engagement_total,
    calculate_engagement_rate_reach,
    calculate_engagement_rate_followers,
    calculate_follower_growth_rate,
    compute_dimensions_hash,
    find_publish_log_and_unified_post,
    ingest_metric_snapshot,
    ingest_observations,
)


class MetricRegistryTests(TestCase):
    """Section AP: Canonical Metric Registry tests."""

    def test_canonical_metric_keys_unique_and_non_empty(self):
        keys = get_canonical_keys()
        self.assertGreaterEqual(len(keys), 14)
        self.assertEqual(len(keys), len(set(keys)))

    def test_all_metric_definitions_valid(self):
        for key, definition in CANONICAL_METRICS.items():
            self.assertEqual(key, definition.key)
            self.assertTrue(bool(definition.display_name))
            self.assertIn(definition.value_type, MetricValueType)
            self.assertIn(definition.unit, MetricUnit)
            self.assertIn(definition.aggregation_behavior, AggregationBehavior)
            self.assertTrue(bool(definition.semantic_description))
            self.assertTrue(bool(definition.cross_platform_comparability))

    def test_invalid_key_rejected(self):
        self.assertFalse(is_valid_metric("UNSUPPORTED_RANDOM_METRIC"))
        self.assertFalse(is_valid_metric(""))
        self.assertIsNone(get_metric_definition("NONEXISTENT"))

    def test_aggregation_behavior_classification(self):
        reach_def = get_metric_definition("REACH")
        followers_def = get_metric_definition("FOLLOWERS_TOTAL")
        reactions_def = get_metric_definition("REACTIONS")
        avg_watch_def = get_metric_definition("VIDEO_AVG_WATCH_TIME")
        net_change_def = get_metric_definition("FOLLOWERS_NET_CHANGE")

        self.assertEqual(reach_def.aggregation_behavior, AggregationBehavior.NON_AGGREGATABLE)
        self.assertEqual(followers_def.aggregation_behavior, AggregationBehavior.LATEST_VALUE)
        self.assertEqual(reactions_def.aggregation_behavior, AggregationBehavior.SUMMABLE)
        self.assertEqual(avg_watch_def.aggregation_behavior, AggregationBehavior.AVERAGE)
        self.assertEqual(net_change_def.aggregation_behavior, AggregationBehavior.DELTA)


class NormalizationTests(TestCase):
    """Sections AQ & AR: Normalizer tests for Facebook and Instagram."""

    def test_facebook_page_and_post_normalization(self):
        # 1. Reach & Impressions
        reach_obs = normalize_facebook_metric("page_impressions_unique", 15400)
        self.assertEqual(len(reach_obs), 1)
        self.assertEqual(reach_obs[0].normalized_metric, "REACH")
        self.assertEqual(reach_obs[0].metric_value, Decimal(15400))
        self.assertEqual(reach_obs[0].metric_scope, "account")

        post_imp_obs = normalize_facebook_metric("post_impressions", 3200, metric_scope="post")
        self.assertEqual(post_imp_obs[0].normalized_metric, "IMPRESSIONS")
        self.assertEqual(post_imp_obs[0].metric_value, Decimal(3200))

        # 2. Followers & Follows
        fol_obs = normalize_facebook_metric("followers_count", 45000)
        self.assertEqual(fol_obs[0].normalized_metric, "FOLLOWERS_TOTAL")
        self.assertEqual(fol_obs[0].metric_value, Decimal(45000))

        loss_obs = normalize_facebook_metric("page_daily_unfollows", 12)
        self.assertEqual(loss_obs[0].normalized_metric, "FOLLOWERS_NET_CHANGE")
        self.assertEqual(loss_obs[0].metric_value, Decimal(-12))
        self.assertEqual(loss_obs[0].extra_dimensions, {"direction": "loss"})

        # 3. Reactions scalar and breakdown
        scalar_rx = normalize_facebook_metric("reactions", 120, metric_scope="post")
        self.assertEqual(len(scalar_rx), 1)
        self.assertEqual(scalar_rx[0].metric_value, Decimal(120))

        dict_rx = normalize_facebook_metric("reactions", {"like": 90, "love": 25, "wow": 5}, metric_scope="post")
        self.assertEqual(len(dict_rx), 4)  # 1 total + 3 types
        self.assertEqual(dict_rx[0].metric_value, Decimal(120))
        self.assertEqual(dict_rx[1].extra_dimensions, {"reaction_type": "like"})
        self.assertEqual(dict_rx[1].metric_value, Decimal(90))

    def test_instagram_account_and_media_normalization(self):
        # 1. Reach
        reach_obs = normalize_instagram_metric("reach", 8500, metric_scope="post")
        self.assertEqual(reach_obs[0].normalized_metric, "REACH")
        self.assertEqual(reach_obs[0].metric_value, Decimal(8500))

        # 2. Reel plays vs Video views
        reel_obs = normalize_instagram_metric("plays", 12400, metric_scope="reel")
        self.assertEqual(reel_obs[0].normalized_metric, "VIDEO_VIEWS")
        self.assertEqual(reel_obs[0].raw_metric_name, "plays")
        self.assertIn("comparability_caveat", reel_obs[0].metadata)

        # 3. Saves and shares
        saves_obs = normalize_instagram_metric("saved", 45, metric_scope="post")
        self.assertEqual(saves_obs[0].normalized_metric, "SAVES")
        self.assertEqual(saves_obs[0].metric_value, Decimal(45))

        # 4. Watch time
        watch_obs = normalize_instagram_metric("ig_reels_video_view_total_time", 4820, metric_scope="reel")
        self.assertEqual(watch_obs[0].normalized_metric, "VIDEO_WATCH_TIME")
        self.assertEqual(watch_obs[0].metric_value, Decimal(4820))

        # 5. Follows and unfollows dict
        net_obs = normalize_instagram_metric("follows_and_unfollows", {"follows": 50, "unfollows": 15})
        self.assertEqual(net_obs[0].normalized_metric, "FOLLOWERS_NET_CHANGE")
        self.assertEqual(net_obs[0].metric_value, Decimal(35))


class DerivedMetricTests(TestCase):
    """Section AX: Derived metrics calculation and safe division."""

    def test_calculate_engagement_total(self):
        total = calculate_engagement_total(reactions=50, comments=20, shares=10, saves=5, clicks=15)
        self.assertEqual(total, Decimal(100))

        # Zero inputs
        self.assertEqual(calculate_engagement_total(), Decimal(0))

        # Handles negative values safely by clamping to 0
        clamped = calculate_engagement_total(reactions=-5, comments=10)
        self.assertEqual(clamped, Decimal(10))

    def test_calculate_engagement_rate_reach_safe_division(self):
        # Standard calculation: (50 / 1000) * 100 = 5.0%
        rate = calculate_engagement_rate_reach(50, 1000)
        self.assertEqual(rate, Decimal("5.0000"))

        # Zero denominator returns None (safe division)
        self.assertIsNone(calculate_engagement_rate_reach(50, 0))

        # Missing denominator returns None
        self.assertIsNone(calculate_engagement_rate_reach(50, None))
        self.assertIsNone(calculate_engagement_rate_reach(None, 1000))

    def test_calculate_engagement_rate_followers_safe_division(self):
        rate = calculate_engagement_rate_followers(25, 500)
        self.assertEqual(rate, Decimal("5.0000"))
        self.assertIsNone(calculate_engagement_rate_followers(25, 0))
        self.assertIsNone(calculate_engagement_rate_followers(25, -100))

    def test_calculate_follower_growth_rate(self):
        # (1200 - 1000) / 1000 * 100 = 20.0%
        growth = calculate_follower_growth_rate(1000, 1200)
        self.assertEqual(growth, Decimal("20.0000"))

        # Negative growth
        decline = calculate_follower_growth_rate(1000, 950)
        self.assertEqual(decline, Decimal("-5.0000"))

        # Zero starting followers returns None
        self.assertIsNone(calculate_follower_growth_rate(0, 100))
        self.assertIsNone(calculate_follower_growth_rate(None, 100))


class IngestionAndIdempotencyTests(TestCase):
    """Sections AS, AT, AU, AV, AW: Snapshot idempotency, dimensions, tenant isolation, and linkage."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client_a = Client.objects.create(name=f"Client Alpha {uid}", company="Alpha Corp", email=f"alpha_{uid}@example.com")
        self.client_b = Client.objects.create(name=f"Client Beta {uid}", company="Beta Corp", email=f"beta_{uid}@example.com")
        self.bucket_time = datetime(2026, 10, 21, 0, 0, 0, tzinfo=dt_timezone.utc)

    def test_snapshot_idempotency_and_settlement_update(self):
        """Inserting same deterministic observation twice updates value in-place without duplicating rows."""
        snap1, created1 = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            object_id="page_123",
            normalized_metric="REACH",
            metric_value=5000,
            raw_metric_name="page_impressions_unique",
            bucket_period="day",
            bucket_timestamp=self.bucket_time,
        )
        self.assertTrue(created1)
        self.assertEqual(snap1.metric_value, Decimal(5000))

        # Re-ingest with settled higher value
        snap2, created2 = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            object_id="page_123",
            normalized_metric="REACH",
            metric_value=5400,
            raw_metric_name="page_impressions_unique",
            bucket_period="day",
            bucket_timestamp=self.bucket_time,
        )
        self.assertFalse(created2)
        self.assertEqual(snap1.id, snap2.id)
        self.assertEqual(snap2.metric_value, Decimal(5400))
        self.assertEqual(SocialMetricSnapshot.objects.filter(client=self.client_a).count(), 1)

    def test_dimensions_hashing_distinguishes_variants(self):
        """Same metric and bucket with different dimensions produce separate distinct snapshots."""
        snap_love, _ = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="post",
            object_id="post_999",
            normalized_metric="REACTIONS",
            metric_value=30,
            raw_metric_name="reactions.love",
            extra_dimensions={"reaction_type": "love"},
            bucket_timestamp=self.bucket_time,
        )
        snap_like, _ = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="post",
            object_id="post_999",
            normalized_metric="REACTIONS",
            metric_value=70,
            raw_metric_name="reactions.like",
            extra_dimensions={"reaction_type": "like"},
            bucket_timestamp=self.bucket_time,
        )
        self.assertNotEqual(snap_love.id, snap_like.id)
        self.assertNotEqual(snap_love.dimensions_hash, snap_like.dimensions_hash)
        self.assertEqual(SocialMetricSnapshot.objects.filter(client=self.client_a).count(), 2)

    def test_multi_tenant_isolation(self):
        """Same object_id in two clients creates isolated records."""
        snap_a, _ = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="account",
            object_id="shared_page_id",
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=1000,
            raw_metric_name="followers_count",
            bucket_timestamp=self.bucket_time,
        )
        snap_b, _ = ingest_metric_snapshot(
            client=self.client_b,
            platform="facebook",
            metric_scope="account",
            object_id="shared_page_id",
            normalized_metric="FOLLOWERS_TOTAL",
            metric_value=2000,
            raw_metric_name="followers_count",
            bucket_timestamp=self.bucket_time,
        )
        self.assertNotEqual(snap_a.id, snap_b.id)
        self.assertEqual(snap_a.client, self.client_a)
        self.assertEqual(snap_b.client, self.client_b)

        # Cross-client validation constraint
        post_b = UnifiedPost.objects.create(client=self.client_b, content="Post B")
        snap_invalid = SocialMetricSnapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="post",
            object_id="ext_post_1",
            normalized_metric="REACH",
            metric_value=100,
            bucket_timestamp=self.bucket_time,
            unified_post=post_b,  # Client mismatch!
        )
        with self.assertRaises(ValidationError):
            snap_invalid.clean()

    def test_publish_log_and_unified_post_linkage(self):
        """Matching client, platform, and platform_post_id links UnifiedPost and PublishLog."""
        post = UnifiedPost.objects.create(client=self.client_a, content="Authoring test")
        log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform="instagram",
            status="success",
            platform_post_id="ig_media_555",
        )

        snap, _ = ingest_metric_snapshot(
            client=self.client_a,
            platform="instagram",
            metric_scope="post",
            object_id="ig_media_555",
            normalized_metric="REACH",
            metric_value=1200,
            raw_metric_name="reach",
            bucket_timestamp=self.bucket_time,
        )
        self.assertEqual(snap.publish_log, log)
        self.assertEqual(snap.unified_post, post)

    def test_external_organic_post_remains_unlinked(self):
        """Provider content not created in Bop Social has null unified_post and publish_log."""
        snap, _ = ingest_metric_snapshot(
            client=self.client_a,
            platform="facebook",
            metric_scope="post",
            object_id="external_organic_post_888",
            normalized_metric="REACH",
            metric_value=3400,
            raw_metric_name="post_impressions_unique",
            bucket_timestamp=self.bucket_time,
        )
        self.assertIsNone(snap.publish_log)
        self.assertIsNone(snap.unified_post)
        self.assertEqual(snap.object_id, "external_organic_post_888")


class CapabilityRegistryTests(TestCase):
    """Section AY: Provider capability registry and degradation tests."""

    def test_facebook_capability(self):
        cap = get_provider_capability("facebook")
        self.assertEqual(cap.overall_support, SupportLevel.SUPPORTED)
        self.assertTrue(cap.supports_account_timeseries)
        self.assertTrue(cap.supports_post_metrics)

    def test_instagram_basic_mode_degradation(self):
        uid = uuid.uuid4().hex[:8]
        client1 = Client.objects.create(name=f"Cap Client 1 {uid}", company="Cap Corp 1", email=f"cap1_{uid}@example.com")
        client2 = Client.objects.create(name=f"Cap Client 2 {uid}", company="Cap Corp 2", email=f"cap2_{uid}@example.com")

        # Credential without instagram_manage_insights
        cred_basic = PlatformCredential.objects.create(
            client=client1,
            platform="instagram",
            scope="instagram_basic,pages_show_list",
            access_token="fake_token",
        )
        cap_degraded = get_provider_capability("instagram", credential=cred_basic)
        self.assertEqual(cap_degraded.overall_support, SupportLevel.PARTIAL)
        self.assertFalse(cap_degraded.supports_account_timeseries)
        self.assertTrue(cap_degraded.supports_post_metrics)  # Media counters still supported

        # Credential with instagram_manage_insights
        cred_full = PlatformCredential.objects.create(
            client=client2,
            platform="instagram",
            scope="instagram_basic,instagram_manage_insights,pages_show_list",
            access_token="fake_token_full",
        )
        cap_full = get_provider_capability("instagram", credential=cred_full)
        self.assertEqual(cap_full.overall_support, SupportLevel.SUPPORTED)
        self.assertTrue(cap_full.supports_account_timeseries)

    def test_unsupported_providers(self):
        cap_tt = get_provider_capability("tiktok")
        self.assertEqual(cap_tt.overall_support, SupportLevel.UNSUPPORTED)
        self.assertFalse(cap_tt.supports_account_metrics)

        cap_x = get_provider_capability("x")
        self.assertEqual(cap_x.overall_support, SupportLevel.UNSUPPORTED)


class LegacyAnalyticsAndRateLimitSafetyTests(TestCase):
    """Sections AZ & BA: Rate limit state safety and legacy analytics non-regression."""

    def test_platform_credential_rate_limit_state(self):
        uid = uuid.uuid4().hex[:8]
        client = Client.objects.create(name=f"Rate Client {uid}", company="Rate Corp", email=f"rate_{uid}@example.com")
        cred = PlatformCredential.objects.create(
            client=client,
            platform="facebook",
            rate_limit_state={
                "app_usage_percent": 45,
                "business_usage_percent": 30,
                "cooldown_until": None,
            }
        )
        self.assertEqual(cred.rate_limit_state["app_usage_percent"], 45)
        # Ensure rate limit state does not store secrets
        self.assertNotIn("access_token", cred.rate_limit_state)

    def test_legacy_post_metric_with_unified_post_linkage(self):
        uid = uuid.uuid4().hex[:8]
        client = Client.objects.create(name=f"Legacy Client {uid}", company="Legacy Corp", email=f"legacy_{uid}@example.com")
        post = UnifiedPost.objects.create(client=client, content="Legacy post test")
        pm = PostMetric.objects.create(
            client=client,
            platform="facebook",
            post_id="fb_post_999",
            unified_post=post,
            impressions=150,
        )
        self.assertEqual(pm.unified_post, post)
        self.assertEqual(pm.impressions, 150)
