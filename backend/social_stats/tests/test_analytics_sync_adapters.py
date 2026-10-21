"""
Unit and integration tests for BS-4C: Provider Analytics Sync Adapters & Controlled Ingestion.
Mocks Graph API transport to validate Facebook/Instagram adapters, capability-aware gating,
rate limit tracking, idempotent settlement updates, and publishing engine isolation.
"""
import json
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    UnifiedPost,
    PlatformPublishLog,
    DailyMetric,
    PostMetric,
    SocialMetricSnapshot,
    SyncLog,
)
from social_stats.analytics import (
    FacebookAnalyticsAdapter,
    InstagramAnalyticsAdapter,
    ProviderPayload,
    SyncResult,
    sync_facebook_analytics,
    sync_instagram_analytics,
    parse_meta_rate_limit_headers,
    update_credential_rate_limit_state,
    evaluate_throttling,
    AnalyticsAuthExpiredError,
    AnalyticsRateLimitedError,
    AnalyticsPermissionError,
)
from social_stats.analytics_tasks import (
    sync_client_facebook_analytics_v2,
    sync_client_instagram_analytics_v2,
)


class FacebookAdapterAndSyncTests(TestCase):
    """Section AB, AF, AG, AI, AJ: Facebook Adapter & Ingestion tests with mocked HTTP transport."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client = Client.objects.create(name=f"FB Client {uid}", company="FB Corp", email=f"fb_{uid}@example.com")
        self.cred = PlatformCredential.objects.create(
            client=self.client,
            platform="facebook",
            page_id="100990099",
            page_name="Test FB Page",
            access_token="fake_fb_token",
            scope="pages_read_engagement,read_insights",
        )

    def test_facebook_account_and_post_sync_pipeline(self):
        """Mocks Graph API v21.0 responses and verifies SocialMetricSnapshot and legacy model ingestion."""
        adapter = FacebookAnalyticsAdapter()

        # Mock page node
        mock_page_resp = MagicMock()
        mock_page_resp.status_code = 200
        mock_page_resp.headers = {"X-App-Usage": '{"call_count": 25, "total_cputime": 10, "total_time": 15}'}
        mock_page_resp.json.return_value = {
            "id": "100990099",
            "name": "Test FB Page",
            "followers_count": 35000,
            "fan_count": 34000,
        }

        # Mock page insights
        mock_insights_resp = MagicMock()
        mock_insights_resp.status_code = 200
        mock_insights_resp.headers = {}
        mock_insights_resp.json.return_value = {
            "data": [
                {
                    "name": "page_post_engagements",
                    "period": "day",
                    "values": [{"value": 450, "end_time": "2026-10-21T07:00:00+0000"}],
                },
                {
                    "name": "page_impressions_unique",
                    "period": "day",
                    "values": [{"value": 12500, "end_time": "2026-10-21T07:00:00+0000"}],
                },
            ]
        }

        # Mock reactions breakdown
        mock_rx_resp = MagicMock()
        mock_rx_resp.status_code = 200
        mock_rx_resp.headers = {}
        mock_rx_resp.json.return_value = {"data": []}

        # Mock posts list
        mock_posts_resp = MagicMock()
        mock_posts_resp.status_code = 200
        mock_posts_resp.headers = {}
        mock_posts_resp.json.return_value = {
            "data": [
                {
                    "id": "100990099_post_111",
                    "message": "Hello World Facebook",
                    "created_time": "2026-10-21T12:00:00+00:00",
                    "permalink_url": "https://facebook.com/100990099/posts/111",
                }
            ]
        }

        # Mock post direct counters
        mock_post_detail = MagicMock()
        mock_post_detail.status_code = 200
        mock_post_detail.headers = {}
        mock_post_detail.json.return_value = {
            "shares": {"count": 14},
            "reactions": {"summary": {"total_count": 88}},
            "comments": {"summary": {"total_count": 22}},
        }

        # Mock post insights
        mock_post_ins = MagicMock()
        mock_post_ins.status_code = 200
        mock_post_ins.headers = {}
        mock_post_ins.json.return_value = {
            "data": [
                {"name": "post_impressions_unique", "values": [{"value": 1800}]},
                {"name": "post_clicks", "values": [{"value": 45}]},
            ]
        }

        def mock_get(url, *args, **kwargs):
            if "/insights" in url and "page_actions_post_reactions_total" in kwargs.get("params", {}).get("metric", ""):
                return mock_rx_resp
            elif "/insights" in url and "page_post_engagements" in kwargs.get("params", {}).get("metric", ""):
                return mock_insights_resp
            elif "/insights" in url and "post_impressions" in kwargs.get("params", {}).get("metric", ""):
                return mock_post_ins
            elif "/posts" in url:
                return mock_posts_resp
            elif "100990099_post_111" in url:
                return mock_post_detail
            elif "100990099" in url:
                return mock_page_resp
            resp = MagicMock()
            resp.status_code = 404
            resp.json.return_value = {}
            return resp

        adapter.session.get = MagicMock(side_effect=mock_get)

        # Run sync
        result = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)

        self.assertEqual(result.status, "success")
        self.assertGreater(result.records_ingested, 0)

        # Check snapshots created
        snapshots = SocialMetricSnapshot.objects.filter(client=self.client, platform="facebook")
        self.assertGreater(snapshots.count(), 0)

        # Check Page follower snapshot
        fol_snap = snapshots.filter(normalized_metric="FOLLOWERS_TOTAL").first()
        self.assertIsNotNone(fol_snap)
        self.assertEqual(fol_snap.metric_value, Decimal(35000))

        # Check Post reach snapshot
        post_reach_snap = snapshots.filter(normalized_metric="REACH", metric_scope="post").first()
        self.assertIsNotNone(post_reach_snap)
        self.assertEqual(post_reach_snap.metric_value, Decimal(1800))

        # Check Dual-write to DailyMetric and PostMetric
        daily = DailyMetric.objects.filter(client=self.client, platform="facebook", date="2026-10-21").first()
        self.assertIsNotNone(daily)
        self.assertEqual(daily.reach, 12500)
        self.assertEqual(daily.likes, 450)

        pm = PostMetric.objects.filter(client=self.client, platform="facebook", post_id="100990099_post_111").first()
        self.assertIsNotNone(pm)
        self.assertEqual(pm.likes, 88)
        self.assertEqual(pm.comments, 22)
        self.assertEqual(pm.shares, 14)

    def test_idempotent_resync_and_settlement_update(self):
        """Re-syncing updated metrics updates value in-place without duplicate snapshots."""
        adapter = FacebookAnalyticsAdapter()

        # Step 1: Initial payload (reach = 1000)
        mock_page_1 = MagicMock(status_code=200, headers={}, json=lambda: {"followers_count": 1000})
        mock_ins_1 = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [{"name": "page_impressions_unique", "values": [{"value": 1000, "end_time": "2026-10-21T07:00:00+0000"}]}]
        })
        adapter.session.get = MagicMock(side_effect=[mock_page_1, mock_ins_1, MagicMock(status_code=200, json=lambda: {"data": []}), MagicMock(status_code=200, json=lambda: {"data": []})])

        res1 = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)
        self.assertEqual(res1.status, "success")
        count_pass1 = SocialMetricSnapshot.objects.filter(client=self.client, platform="facebook").count()

        # Step 2: Settled payload 24h later (reach settled to 1450)
        mock_page_2 = MagicMock(status_code=200, headers={}, json=lambda: {"followers_count": 1000})
        mock_ins_2 = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [{"name": "page_impressions_unique", "values": [{"value": 1450, "end_time": "2026-10-21T07:00:00+0000"}]}]
        })
        adapter.session.get = MagicMock(side_effect=[mock_page_2, mock_ins_2, MagicMock(status_code=200, json=lambda: {"data": []}), MagicMock(status_code=200, json=lambda: {"data": []})])

        res2 = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)
        self.assertEqual(res2.status, "success")
        count_pass2 = SocialMetricSnapshot.objects.filter(client=self.client, platform="facebook").count()

        # Same bucket count; no duplicate rows
        self.assertEqual(count_pass1, count_pass2)

        settled_reach = SocialMetricSnapshot.objects.filter(
            client=self.client,
            platform="facebook",
            normalized_metric="REACH",
            metric_scope="account",
        ).first()
        self.assertEqual(settled_reach.metric_value, Decimal(1450))

    def test_external_post_sync_unlinked(self):
        """External posts not authored in Bop Social persist snapshots with unified_post=None."""
        adapter = FacebookAnalyticsAdapter()
        mock_page = MagicMock(status_code=200, headers={}, json=lambda: {"followers_count": 500})
        mock_ins = MagicMock(status_code=200, headers={}, json=lambda: {"data": []})
        mock_posts = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [{"id": "external_fb_post_777", "message": "Organic post", "created_time": "2026-10-21T10:00:00+00:00"}]
        })
        mock_detail = MagicMock(status_code=200, headers={}, json=lambda: {
            "shares": {"count": 3}, "reactions": {"summary": {"total_count": 15}}, "comments": {"summary": {"total_count": 2}}
        })

        adapter.session.get = MagicMock(side_effect=[mock_page, mock_ins, MagicMock(status_code=200, json=lambda: {"data": []}), mock_posts, mock_detail, MagicMock(status_code=200, json=lambda: {"data": []})])

        result = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)
        self.assertEqual(result.status, "success")

        snap = SocialMetricSnapshot.objects.filter(client=self.client, object_id="external_fb_post_777").first()
        self.assertIsNotNone(snap)
        self.assertIsNone(snap.unified_post)
        self.assertIsNone(snap.publish_log)

    def test_auth_expired_handling(self):
        """Expired token raises AnalyticsAuthExpiredError and completes with status=failed without retry loop."""
        adapter = FacebookAnalyticsAdapter()
        mock_expired = MagicMock(
            status_code=401,
            headers={},
            json=lambda: {"error": {"code": 190, "error_subcode": 463, "message": "Session has expired"}}
        )
        adapter.session.get = MagicMock(return_value=mock_expired)

        result = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_classification, "AUTH_EXPIRED")
        self.assertIn("expired", result.errors[0].lower())

        # SyncLog recorded properly
        slog = SyncLog.objects.filter(client=self.client, platform="facebook").first()
        self.assertEqual(slog.status, "failed")


class InstagramAdapterAndSyncTests(TestCase):
    """Section AC, AD, AK: Instagram Adapter & Capability-aware Ingestion tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client = Client.objects.create(name=f"IG Client {uid}", company="IG Corp", email=f"ig_{uid}@example.com")

    def test_instagram_full_mode_sync(self):
        """Credential with instagram_manage_insights syncs account insights and media metrics."""
        cred_full = PlatformCredential.objects.create(
            client=self.client,
            platform="instagram",
            instagram_account_id="ig_biz_111",
            access_token="fake_ig_full_token",
            scope="instagram_basic,instagram_manage_insights,pages_read_engagement",
        )

        adapter = InstagramAnalyticsAdapter()

        # Mock direct account node
        mock_acct = MagicMock(status_code=200, headers={}, json=lambda: {
            "followers_count": 28000, "follows_count": 450, "media_count": 120
        })

        # Mock daily insights (reach, follower_count)
        mock_day_ins = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {"name": "reach", "values": [{"value": 6400, "end_time": "2026-10-21T07:00:00+0000"}]},
                {"name": "follower_count", "values": [{"value": 28000, "end_time": "2026-10-21T07:00:00+0000"}]},
            ]
        })

        # Mock total insights (profile_views, website_clicks)
        mock_tot_ins = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {"name": "profile_views", "values": [{"value": 310, "end_time": "2026-10-21T07:00:00+0000"}]},
                {"name": "website_clicks", "values": [{"value": 85, "end_time": "2026-10-21T07:00:00+0000"}]},
            ]
        })

        # Mock media list (1 Reel)
        mock_media = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {
                    "id": "ig_reel_888",
                    "caption": "Exciting Reel",
                    "media_type": "REEL",
                    "timestamp": "2026-10-21T14:00:00+00:00",
                    "permalink": "https://instagram.com/reel/888",
                }
            ]
        })

        # Mock direct counters (like_count, comments_count)
        mock_direct = MagicMock(status_code=200, headers={}, json=lambda: {
            "like_count": 140, "comments_count": 28
        })

        # Mock reel insights (reach, plays, watch time)
        mock_reel_ins = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {"name": "reach", "values": [{"value": 3500}]},
                {"name": "plays", "values": [{"value": 7200}]},
                {"name": "saved", "values": [{"value": 62}]},
                {"name": "ig_reels_video_view_total_time", "values": [{"value": 8500}]},
            ]
        })

        def mock_get(url, *args, **kwargs):
            if "/insights" in url and "metric_type" in kwargs.get("params", {}):
                return mock_tot_ins
            elif "/insights" in url and "reach,follower_count" in kwargs.get("params", {}).get("metric", ""):
                return mock_day_ins
            elif "/insights" in url and "plays" in kwargs.get("params", {}).get("metric", ""):
                return mock_reel_ins
            elif "/media" in url:
                return mock_media
            elif "ig_reel_888" in url:
                return mock_direct
            elif "ig_biz_111" in url:
                return mock_acct
            return MagicMock(status_code=404, json=lambda: {})

        adapter.session.get = MagicMock(side_effect=mock_get)

        result = sync_instagram_analytics(client_id=self.client.id, cred=cred_full, adapter=adapter)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.capability_mode, "FULL")

        # Verify snapshots
        snaps = SocialMetricSnapshot.objects.filter(client=self.client, platform="instagram")
        self.assertGreater(snaps.count(), 0)

        # Verify Reel plays mapped to VIDEO_VIEWS
        reel_plays = snaps.filter(object_id="ig_reel_888", normalized_metric="VIDEO_VIEWS").first()
        self.assertIsNotNone(reel_plays)
        self.assertEqual(reel_plays.metric_value, Decimal(7200))
        self.assertEqual(reel_plays.raw_metric_name, "plays")

    def test_instagram_partial_mode_degradation(self):
        """Credential without instagram_manage_insights skips account insights, syncs media counters, returns partial."""
        cred_basic = PlatformCredential.objects.create(
            client=self.client,
            platform="instagram",
            instagram_account_id="ig_basic_222",
            access_token="fake_ig_basic_token",
            scope="instagram_basic,pages_show_list",  # No manage_insights!
        )

        adapter = InstagramAnalyticsAdapter()

        # Direct account node succeeds
        mock_acct = MagicMock(status_code=200, headers={}, json=lambda: {
            "followers_count": 12000, "follows_count": 150, "media_count": 45
        })

        # Media list
        mock_media = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {"id": "ig_photo_333", "caption": "Nice photo", "media_type": "IMAGE", "timestamp": "2026-10-21T11:00:00+00:00"}
            ]
        })

        # Direct counters (like_count, comments_count)
        mock_direct = MagicMock(status_code=200, headers={}, json=lambda: {
            "like_count": 55, "comments_count": 8
        })

        def mock_get(url, *args, **kwargs):
            if "/media" in url:
                return mock_media
            elif "ig_photo_333" in url:
                return mock_direct
            elif "ig_basic_222" in url:
                return mock_acct
            return MagicMock(status_code=404, json=lambda: {})

        adapter.session.get = MagicMock(side_effect=mock_get)

        result = sync_instagram_analytics(client_id=self.client.id, cred=cred_basic, adapter=adapter)

        # Status must be partial, capability mode PARTIAL
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.capability_mode, "PARTIAL")

        # Media direct counters ingested
        rx_snap = SocialMetricSnapshot.objects.filter(
            client=self.client, platform="instagram", object_id="ig_photo_333", normalized_metric="REACTIONS"
        ).first()
        self.assertIsNotNone(rx_snap)
        self.assertEqual(rx_snap.metric_value, Decimal(55))

        # Account daily insights must NOT exist (no fabricated zeroes)
        reach_daily = SocialMetricSnapshot.objects.filter(
            client=self.client, platform="instagram", metric_scope="account", normalized_metric="REACH"
        ).first()
        self.assertIsNone(reach_daily)

    def test_story_expiration_handling(self):
        """Active stories return insights; expired stories are handled without failing."""
        cred = PlatformCredential.objects.create(
            client=self.client,
            platform="instagram",
            instagram_account_id="ig_story_333",
            access_token="fake_token",
            scope="instagram_basic,instagram_manage_insights",
        )
        adapter = InstagramAnalyticsAdapter()

        # Stories list with 1 active and 1 expired
        mock_stories = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [
                {"id": "story_active_1", "media_type": "IMAGE", "timestamp": "2026-10-21T18:00:00+00:00"},
                {"id": "story_expired_2", "media_type": "IMAGE", "timestamp": "2026-10-20T10:00:00+00:00"},
            ]
        })

        mock_active_ins = MagicMock(status_code=200, headers={}, json=lambda: {
            "data": [{"name": "reach", "values": [{"value": 420}]}, {"name": "replies", "values": [{"value": 5}]}]
        })

        mock_expired_ins = MagicMock(status_code=404, headers={}, json=lambda: {
            "error": {"code": 100, "error_subcode": 33, "message": "Story has expired"}
        })

        def mock_get(url, *args, **kwargs):
            if "/stories" in url:
                return mock_stories
            elif "story_active_1/insights" in url:
                return mock_active_ins
            elif "story_expired_2/insights" in url:
                return mock_expired_ins
            return MagicMock(status_code=404, json=lambda: {})

        adapter.session.get = MagicMock(side_effect=mock_get)

        payload = adapter.fetch_story_metrics(cred)
        self.assertEqual(len(payload.raw_data.get("stories", [])), 2)
        active_entry = payload.raw_data["stories"][0]
        expired_entry = payload.raw_data["stories"][1]

        self.assertFalse(active_entry.get("expired", False))
        self.assertTrue(expired_entry.get("expired", False))
        self.assertEqual(len(payload.errors), 0)


class RateLimitAndPublishingIsolationTests(TestCase):
    """Sections AE, AL: Rate limit evaluation and publishing engine isolation."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.client = Client.objects.create(name=f"RL Client {uid}", company="RL Corp", email=f"rl_{uid}@example.com")
        self.cred = PlatformCredential.objects.create(
            client=self.client,
            platform="facebook",
            page_id="page_rl_999",
            access_token="fake_token",
        )

    def test_rate_limit_header_parsing_and_state_update(self):
        headers = {
            "X-App-Usage": '{"call_count": 82, "total_cputime": 40, "total_time": 60}',
            "X-Business-Use-Case-Usage": '{"12345": [{"call_count": 85, "total_cputime": 70, "total_time": 75}]}',
        }
        parsed = parse_meta_rate_limit_headers(headers)
        self.assertEqual(parsed["app_usage_percent"], 82)
        self.assertEqual(parsed["business_usage_percent"], 85)

        state = update_credential_rate_limit_state(self.cred, headers)
        self.cred.refresh_from_db()
        self.assertEqual(self.cred.rate_limit_state["app_usage_percent"], 82)
        self.assertEqual(self.cred.rate_limit_state["business_usage_percent"], 85)

        # Test throttling threshold evaluation
        decision, _ = evaluate_throttling(self.cred.rate_limit_state)
        self.assertEqual(decision, "DEFER_HISTORICAL")

        # Test >=90% threshold
        headers_95 = {"X-App-Usage": '{"call_count": 95, "total_cputime": 20, "total_time": 30}'}
        update_credential_rate_limit_state(self.cred, headers_95)
        self.cred.refresh_from_db()
        decision_95, wait = evaluate_throttling(self.cred.rate_limit_state)
        self.assertEqual(decision_95, "COOLDOWN")
        self.assertGreaterEqual(wait, 890)
        self.assertLessEqual(wait, 900)

    def test_publishing_engine_isolation_on_analytics_failure(self):
        """Analytics sync failures or rate limits must NEVER mutate UnifiedPost or PublishingLogs."""
        post = UnifiedPost.objects.create(
            client=self.client,
            title="Pilot Post",
            content="Protected post content",
            status="published",
        )
        pub_log = PlatformPublishLog.objects.create(
            unified_post=post,
            platform="facebook",
            status="success",
            platform_post_id="post_protected_123",
        )

        adapter = FacebookAnalyticsAdapter()
        # Mock provider fatal 500 error
        adapter.session.get = MagicMock(return_value=MagicMock(status_code=500, json=lambda: {"error": {"message": "Server Error"}}))

        result = sync_facebook_analytics(client_id=self.client.id, cred=self.cred, adapter=adapter)
        self.assertEqual(result.status, "failed")

        # Assert post and publish log remain completely untouched!
        post.refresh_from_db()
        pub_log.refresh_from_db()
        self.assertEqual(post.status, "published")
        self.assertEqual(pub_log.status, "success")
        self.assertEqual(pub_log.platform_post_id, "post_protected_123")
