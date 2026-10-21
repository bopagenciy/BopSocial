"""
Comprehensive Test Suite for BS-4D:
Unified Social Analytics Rollup, Cadence & Freshness Automation.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import zoneinfo

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricSnapshot,
    SocialMetricRollup,
    SyncLog,
    UnifiedPost,
    PlatformPublishLog,
)
from social_stats.analytics.registry import (
    AggregationBehavior,
    CANONICAL_METRICS,
    FreshnessState,
)
from social_stats.analytics.rollups import (
    aggregate_snapshots,
    calculate_period_start,
    build_rollups_for_client,
    get_client_timezone,
)
from social_stats.analytics.freshness import (
    evaluate_freshness,
    get_client_platform_freshness,
)
from social_stats.analytics.orchestrator import (
    acquire_sync_lock,
    release_sync_lock,
    is_sync_due,
    run_analytics_orchestrator,
)
from social_stats.analytics.backfill import (
    backfill_rollups,
)


class AnalyticsRollupEngineTests(TestCase):
    """Tests for rollup calculation, aggregation semantics, non-aggregatable safety, and idempotency."""

    def setUp(self):
        self.user = User.objects.create_user(username="test_analytics_user", password="password123")
        self.client_record = Client.objects.create(
            name="Test Client",
            company="Test Company",
            email="test_analytics@example.com",
            timezone="America/New_York",
            owner_user=self.user,
        )

    def test_01_aggregation_behavior_summable(self):
        """SUMMABLE metrics (e.g. REACTIONS, COMMENTS, SHARES) sum values across snapshots."""
        snap1 = SocialMetricSnapshot(metric_value=Decimal("15.0000"))
        snap2 = SocialMetricSnapshot(metric_value=Decimal("25.5000"))
        val, meta = aggregate_snapshots([snap1, snap2], "REACTIONS", "day")
        self.assertEqual(val, Decimal("40.5000"))
        self.assertEqual(meta["aggregation_behavior"], AggregationBehavior.SUMMABLE.value)

    def test_02_aggregation_behavior_latest_value(self):
        """LATEST_VALUE metrics (e.g. FOLLOWERS_TOTAL) take the latest observation, never summing."""
        t1 = timezone.now() - timedelta(hours=5)
        t2 = timezone.now() - timedelta(hours=1)
        snap1 = SocialMetricSnapshot(metric_value=Decimal("100.0000"), bucket_timestamp=t1, captured_at=t1)
        snap2 = SocialMetricSnapshot(metric_value=Decimal("120.0000"), bucket_timestamp=t2, captured_at=t2)
        val, meta = aggregate_snapshots([snap1, snap2], "FOLLOWERS_TOTAL", "day")
        self.assertEqual(val, Decimal("120.0000"))
        self.assertEqual(meta["aggregation_behavior"], AggregationBehavior.LATEST_VALUE.value)

    def test_03_aggregation_behavior_delta(self):
        """DELTA metrics (e.g. FOLLOWERS_NET_CHANGE) sum net changes across discrete buckets."""
        snap1 = SocialMetricSnapshot(metric_value=Decimal("5.0000"))
        snap2 = SocialMetricSnapshot(metric_value=Decimal("-2.0000"))
        val, meta = aggregate_snapshots([snap1, snap2], "FOLLOWERS_NET_CHANGE", "day")
        self.assertEqual(val, Decimal("3.0000"))
        self.assertEqual(meta["aggregation_behavior"], AggregationBehavior.DELTA.value)

    def test_04_aggregation_behavior_average(self):
        """AVERAGE metrics (e.g. VIDEO_AVG_WATCH_TIME) compute mean value, never sum."""
        snap1 = SocialMetricSnapshot(metric_value=Decimal("10.0000"))
        snap2 = SocialMetricSnapshot(metric_value=Decimal("20.0000"))
        val, meta = aggregate_snapshots([snap1, snap2], "VIDEO_AVG_WATCH_TIME", "day")
        self.assertEqual(val, Decimal("15.0000"))
        self.assertEqual(meta["aggregation_behavior"], AggregationBehavior.AVERAGE.value)

    def test_05_non_aggregatable_reach_safety(self):
        """REACH must never be summed across daily snapshots into weekly or monthly rollups."""
        snap1 = SocialMetricSnapshot(metric_value=Decimal("500.0000"), bucket_period="day", bucket_timestamp=timezone.now() - timedelta(days=2))
        snap2 = SocialMetricSnapshot(metric_value=Decimal("600.0000"), bucket_period="day", bucket_timestamp=timezone.now() - timedelta(days=1))

        # Daily rollup: allowed to preserve single-day value
        val_day, meta_day = aggregate_snapshots([snap1], "REACH", "day")
        self.assertEqual(val_day, Decimal("500.0000"))
        self.assertTrue(meta_day["is_available"])

        # Weekly rollup: strictly refuses to sum 500 + 600 = 1100
        val_week, meta_week = aggregate_snapshots([snap1, snap2], "REACH", "week")
        self.assertEqual(val_week, Decimal("0.0000"))
        self.assertFalse(meta_week["is_available"])
        self.assertIn("Audience overlap prevents mathematical summation", meta_week["unavailable_reason"])

    def test_06_rollup_idempotency_zero_duplicates(self):
        """Rebuilding rollups for the same client and snapshots updates in-place with 0 duplicates."""
        t_base = datetime(2026, 10, 20, 15, 0, 0, tzinfo=dt_timezone.utc)
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="REACTIONS",
            metric_value=Decimal("50.0000"),
            raw_metric_name="likes",
            bucket_period="day",
            bucket_timestamp=t_base,
        )

        # 1st run
        res1 = build_rollups_for_client(self.client_record.id, platform="facebook", periods=("day", "week"))
        self.assertEqual(res1["created"], 2)  # 1 day, 1 week
        self.assertEqual(res1["updated"], 0)
        self.assertEqual(SocialMetricRollup.objects.filter(client=self.client_record).count(), 2)

        # 2nd run
        res2 = build_rollups_for_client(self.client_record.id, platform="facebook", periods=("day", "week"))
        self.assertEqual(res2["created"], 0)
        self.assertEqual(res2["updated"], 2)
        # Total count must remain strictly 2
        self.assertEqual(SocialMetricRollup.objects.filter(client=self.client_record).count(), 2)

    def test_07_dimension_aware_rollups(self):
        """Metrics with distinct dimensions_hash (e.g. reaction types like vs love) produce distinct rollup records."""
        t_base = datetime(2026, 10, 20, 15, 0, 0, tzinfo=dt_timezone.utc)
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="REACTIONS",
            metric_value=Decimal("30.0000"),
            raw_metric_name="reactions",
            dimensions_hash="hash_like",
            extra_dimensions={"reaction_type": "like"},
            bucket_period="day",
            bucket_timestamp=t_base,
        )
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="REACTIONS",
            metric_value=Decimal("15.0000"),
            raw_metric_name="reactions",
            dimensions_hash="hash_love",
            extra_dimensions={"reaction_type": "love"},
            bucket_period="day",
            bucket_timestamp=t_base,
        )

        build_rollups_for_client(self.client_record.id, platform="facebook", periods=("day",))
        rollups = SocialMetricRollup.objects.filter(client=self.client_record, period="day")
        self.assertEqual(rollups.count(), 2)
        like_r = rollups.get(dimensions_hash="hash_like")
        love_r = rollups.get(dimensions_hash="hash_love")
        self.assertEqual(like_r.metric_value, Decimal("30.0000"))
        self.assertEqual(love_r.metric_value, Decimal("15.0000"))

    def test_08_client_timezone_period_start(self):
        """Period start aligns to client local calendar boundaries (America/New_York vs UTC)."""
        tz_ny = zoneinfo.ZoneInfo("America/New_York")
        # 2026-10-21 02:00:00 UTC is 2026-10-20 22:00:00 EDT (previous calendar date in NY)
        dt_utc = datetime(2026, 10, 21, 2, 0, 0, tzinfo=dt_timezone.utc)

        p_day_ny = calculate_period_start(dt_utc, "day", tz_ny)
        self.assertEqual(p_day_ny, date(2026, 10, 20))

        p_day_utc = calculate_period_start(dt_utc, "day", zoneinfo.ZoneInfo("UTC"))
        self.assertEqual(p_day_utc, date(2026, 10, 21))

        # Weekly boundary (Monday)
        p_week_ny = calculate_period_start(dt_utc, "week", tz_ny)
        # 2026-10-20 is Tuesday; preceding Monday is 2026-10-19
        self.assertEqual(p_week_ny, date(2026, 10, 19))

        # Monthly boundary (1st of month)
        p_month_ny = calculate_period_start(dt_utc, "month", tz_ny)
        self.assertEqual(p_month_ny, date(2026, 10, 1))


class AnalyticsFreshnessAndCadenceTests(TestCase):
    """Tests for freshness state detection, cadence rules, and duplicate dispatch prevention."""

    def setUp(self):
        self.client_record = Client.objects.create(
            name="Cadence Client",
            company="Cadence Co",
            email="cadence@example.com",
        )
        self.cred = PlatformCredential.objects.create(
            client=self.client_record,
            platform="facebook",
            page_id="fb_12345",
            access_token="test_token",
            is_active=True,
            rate_limit_state={},
        )

    def test_09_freshness_evaluation_account(self):
        """Account metrics: fresh < 24h, aging 24-48h, stale >= 48h, unavailable when never synced."""
        now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=dt_timezone.utc)

        # Never synced
        state, age, _ = evaluate_freshness(None, metric_scope="account", now=now)
        self.assertEqual(state, FreshnessState.UNAVAILABLE)

        # Fresh (2 hours old)
        t_fresh = now - timedelta(hours=2)
        state, age, next_sync = evaluate_freshness(t_fresh, metric_scope="account", now=now)
        self.assertEqual(state, FreshnessState.FRESH)
        self.assertEqual(age, 7200)

        # Aging (30 hours old)
        t_aging = now - timedelta(hours=30)
        state, age, _ = evaluate_freshness(t_aging, metric_scope="account", now=now)
        self.assertEqual(state, FreshnessState.AGING)

        # Stale (50 hours old)
        t_stale = now - timedelta(hours=50)
        state, age, _ = evaluate_freshness(t_stale, metric_scope="account", now=now)
        self.assertEqual(state, FreshnessState.STALE)

    def test_10_freshness_evaluation_recent_vs_maturing_vs_story(self):
        """Posts adapt cadence by age; stories expire after 24h."""
        now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=dt_timezone.utc)

        # Recent post published 10h ago; synced 3h ago -> FRESH (<4h cadence)
        pub_recent = now - timedelta(hours=10)
        synced_recent = now - timedelta(hours=3)
        state, _, _ = evaluate_freshness(synced_recent, metric_scope="post", post_published_at=pub_recent, now=now)
        self.assertEqual(state, FreshnessState.FRESH)

        # Recent post synced 6h ago -> AGING (4h to 12h)
        synced_aging = now - timedelta(hours=6)
        state, _, _ = evaluate_freshness(synced_aging, metric_scope="post", post_published_at=pub_recent, now=now)
        self.assertEqual(state, FreshnessState.AGING)

        # Active Story (<24h old): synced 2h ago -> FRESH (<3h cadence)
        story_pub = now - timedelta(hours=10)
        story_synced = now - timedelta(hours=2)
        state, _, _ = evaluate_freshness(story_synced, metric_scope="story", post_published_at=story_pub, now=now)
        self.assertEqual(state, FreshnessState.FRESH)

        # Expired Story (published 26h ago) -> UNAVAILABLE
        story_expired_pub = now - timedelta(hours=26)
        state, _, _ = evaluate_freshness(story_synced, metric_scope="story", post_published_at=story_expired_pub, now=now)
        self.assertEqual(state, FreshnessState.UNAVAILABLE)

    def test_11_sync_due_evaluation(self):
        """is_sync_due evaluates elapsed time against required cadence."""
        now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=dt_timezone.utc)

        # Case 1: Never synced -> due
        due, reason = is_sync_due(self.cred, cadence_hours=24, now=now)
        self.assertTrue(due)
        self.assertEqual(reason, "NEVER_SYNCED")

        # Case 2: Synced 5h ago -> not due
        SyncLog.objects.create(
            client=self.client_record,
            platform="facebook",
            status="success",
            finished_at=now - timedelta(hours=5),
        )
        due, reason = is_sync_due(self.cred, cadence_hours=24, now=now)
        self.assertFalse(due)
        self.assertIn("NOT_DUE", reason)

        # Case 3: Synced 25h ago (delete 5h log first) -> due
        SyncLog.objects.filter(client=self.client_record, platform="facebook").delete()
        SyncLog.objects.create(
            client=self.client_record,
            platform="facebook",
            status="success",
            finished_at=now - timedelta(hours=25),
        )
        due, reason = is_sync_due(self.cred, cadence_hours=24, now=now)
        self.assertTrue(due)
        self.assertIn("DUE_ELAPSED", reason)

    def test_12_rate_limit_throttling_cooldown(self):
        """Credentials in 90% COOLDOWN are blocked by orchestrator."""
        now = timezone.now()
        self.cred.rate_limit_state = {
            "app_usage_percent": 95,
            "cooldown_until": (now + timedelta(minutes=15)).isoformat(),
        }
        self.cred.save()

        due, reason = is_sync_due(self.cred, cadence_hours=24)
        self.assertFalse(due)
        self.assertIn("RATE_LIMIT_COOLDOWN", reason)

    def test_13_duplicate_schedule_concurrency_lock(self):
        """Concurrent scheduler runs cannot double-dispatch the same client/platform."""
        # 1st acquire succeeds
        lock1 = acquire_sync_lock(self.client_record.id, "facebook")
        self.assertTrue(lock1)

        # 2nd concurrent acquire is rejected
        lock2 = acquire_sync_lock(self.client_record.id, "facebook")
        self.assertFalse(lock2)

        # Release lock
        release_sync_lock(self.client_record.id, "facebook")

        # 3rd acquire succeeds after release
        lock3 = acquire_sync_lock(self.client_record.id, "facebook")
        self.assertTrue(lock3)
        release_sync_lock(self.client_record.id, "facebook")


class AnalyticsApiReadLayerTests(TestCase):
    """Tests for Analytics Summary, Trends, and Top-Posts API read layer."""

    def setUp(self):
        self.user = User.objects.create_user(username="api_user", password="password123")
        self.other_user = User.objects.create_user(username="other_user", password="password123")

        self.client_record = Client.objects.create(
            name="API Client",
            company="API Agency",
            email="api@example.com",
            owner_user=self.user,
        )
        self.other_client = Client.objects.create(
            name="Other Client",
            company="Other Agency",
            email="other@example.com",
            owner_user=self.other_user,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

        # Populate sample rollups
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="REACTIONS",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("45.0000"),
            sample_count=3,
        )
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="FOLLOWERS_TOTAL",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("150.0000"),
            sample_count=1,
        )

        # Sample Bop post & log
        self.unified_post = UnifiedPost.objects.create(
            client=self.client_record,
            created_by=self.user,
            content="API test post",
            target_platforms=["facebook"],
            status="published",
        )
        self.publish_log = PlatformPublishLog.objects.create(
            unified_post=self.unified_post,
            platform="facebook",
            platform_post_id="fb_post_1",
            status="success",
        )

        # Sample post snapshot (Bop-authored)
        t_post = datetime(2026, 10, 20, 18, 0, 0, tzinfo=dt_timezone.utc)
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_1",
            normalized_metric="REACTIONS",
            metric_value=Decimal("80.0000"),
            raw_metric_name="likes",
            unified_post=self.unified_post,
            publish_log=self.publish_log,
            bucket_period="day",
            bucket_timestamp=t_post,
        )
        # Sample post snapshot (External organic)
        SocialMetricSnapshot.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="post",
            object_id="fb_post_organic",
            normalized_metric="REACTIONS",
            metric_value=Decimal("95.0000"),
            raw_metric_name="likes",
            unified_post=None,
            publish_log=None,
            bucket_period="day",
            bucket_timestamp=t_post,
        )

    def test_14_api_summary_endpoint(self):
        """GET /api/analytics/summary/ returns normalized metric dictionary."""
        url = f"/api/analytics/summary/?client_id={self.client_record.id}&platform=facebook"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["client_id"], self.client_record.id)
        self.assertIn("REACTIONS", data["metrics"])
        self.assertEqual(data["metrics"]["REACTIONS"]["value"], 45.0)
        self.assertIn("FOLLOWERS_TOTAL", data["metrics"])
        self.assertEqual(data["metrics"]["FOLLOWERS_TOTAL"]["value"], 150.0)

    def test_15_api_trends_endpoint(self):
        """GET /api/analytics/trends/ returns chronological datapoints."""
        url = f"/api/analytics/trends/?client_id={self.client_record.id}&metric=REACTIONS&platform=facebook"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["metric"], "REACTIONS")
        self.assertEqual(len(data["datapoints"]), 1)
        self.assertEqual(data["datapoints"][0]["metric_value"], 45.0)

    def test_16_api_top_posts_distinguishes_bop_vs_external(self):
        """GET /api/analytics/top-posts/ correctly distinguishes Bop-authored vs organic posts."""
        url = f"/api/analytics/top-posts/?client_id={self.client_record.id}&metric=REACTIONS"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["count"], 2)
        # Top 1 is organic (95 likes)
        self.assertEqual(data["posts"][0]["object_id"], "fb_post_organic")
        self.assertFalse(data["posts"][0]["is_bop_authored"])
        self.assertIsNone(data["posts"][0]["unified_post_id"])

        # Top 2 is Bop-authored (80 likes)
        self.assertEqual(data["posts"][1]["object_id"], "fb_post_1")
        self.assertTrue(data["posts"][1]["is_bop_authored"])
        self.assertEqual(data["posts"][1]["unified_post_id"], self.unified_post.id)

    def test_17_tenant_isolation_unauthorized_access_blocked(self):
        """User cannot query analytics of a client they do not own."""
        url = f"/api/analytics/summary/?client_id={self.other_client.id}"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_18_orchestrator_run_loop(self):
        """Orchestrator run loop identifies due credentials and respects dry-run and locks."""
        # Create active credential
        PlatformCredential.objects.create(
            client=self.client_record,
            platform="facebook",
            page_id="page_orch",
            access_token="tok",
            is_active=True,
            rate_limit_state={},
        )
        res = run_analytics_orchestrator(dry_run=True, force=True)
        self.assertIn("dispatched", res)
        # Should contain at least our client
        dispatched_clients = [d["client_id"] for d in res["dispatched"]]
        self.assertIn(self.client_record.id, dispatched_clients)

    def test_19_backfill_rollups_dry_run(self):
        """Backfill rollups in dry-run mode previews count without generating rollups."""
        res = backfill_rollups(client_id=self.client_record.id, dry_run=True)
        self.assertIn(str(self.client_record.id), res)
        self.assertTrue(res[str(self.client_record.id)]["dry_run"])
        self.assertGreaterEqual(res[str(self.client_record.id)]["snapshots_found"], 1)

    def test_20_instagram_partial_cadence_mode_detection(self):
        """Orchestrator detects PARTIAL mode for Instagram credentials without manage_insights."""
        ig_cred = PlatformCredential.objects.create(
            client=self.client_record,
            platform="instagram",
            instagram_account_id="ig_123",
            access_token="tok",
            scope="instagram_basic,instagram_content_publish",
            is_active=True,
            rate_limit_state={},
        )
        res = run_analytics_orchestrator(dry_run=True, force=True)
        ig_entry = next((d for d in res["dispatched"] if d["client_id"] == self.client_record.id and d["platform"] == "instagram"), None)
        self.assertIsNotNone(ig_entry)
        self.assertEqual(ig_entry["capability_mode"], "PARTIAL")

    def test_21_cross_platform_comparability_warning(self):
        """Summary view includes comparability caveats when querying cross-platform non-comparable metrics."""
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="CLICKS_TOTAL",
            period="day",
            period_start=date(2026, 10, 20),
            metric_value=Decimal("10.0000"),
            sample_count=1,
        )
        url = f"/api/analytics/summary/?client_id={self.client_record.id}&platform=all&metric=CLICKS_TOTAL"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("CLICKS_TOTAL", data["metrics"])
        self.assertIsNotNone(data["metrics"]["CLICKS_TOTAL"]["comparability_warning"])

    def test_22_api_trends_date_filtering(self):
        """Trends endpoint filters by start_date and end_date correctly."""
        # Create earlier rollup
        SocialMetricRollup.objects.create(
            client=self.client_record,
            platform="facebook",
            metric_scope="account",
            object_id="page_100",
            normalized_metric="REACTIONS",
            period="day",
            period_start=date(2026, 10, 1),
            metric_value=Decimal("10.0000"),
            sample_count=1,
        )
        # Filter range after 2026-10-15
        url = f"/api/analytics/trends/?client_id={self.client_record.id}&metric=REACTIONS&platform=facebook&start_date=2026-10-15"
        resp = self.api_client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # Should only contain 2026-10-20 rollup, not 2026-10-01
        datapoint_dates = [dp["period_start"] for dp in data["datapoints"]]
        self.assertIn("2026-10-20", datapoint_dates)
        self.assertNotIn("2026-10-01", datapoint_dates)
