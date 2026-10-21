# BOP SOCIAL — BS-4B: ANALYTICS FOUNDATION & CANONICAL METRIC REGISTRY

## 1. Overview & Purpose
Phase BS-4B introduces the durable analytics data foundation for Bop Social without altering the verified Publishing Engine v1 baseline. It establishes:
1. A central **Canonical Metric Registry** decoupling business metrics from provider-specific naming conventions.
2. A durable time-bucket observation model (**`SocialMetricSnapshot`**) supporting settlement updates and point-in-time velocity queries.
3. A materialized rollup cache (**`SocialMetricRollup`**) for high-performance client dashboards.
4. Provider normalization adapters with explicit semantic caveats (e.g., Reel plays vs. 3-second video views).
5. Deterministic dimension hashing for multidimensional telemetry (e.g., reaction type breakdowns).
6. Prospective linkage to Bop Social authored posts (`UnifiedPost` and `PlatformPublishLog`) alongside native support for external organic posts.
7. A provider capability registry accounting for permission degradation (e.g., Instagram Basic mode without `instagram_manage_insights`).

---

## 2. Canonical Metric Registry
Located at `backend/social_stats/analytics/registry.py`.

### Canonical Metric Keys
- `REACH`: Unique accounts/users reached in period.
- `IMPRESSIONS`: Total screen appearances (including duplicate views).
- `FOLLOWERS_TOTAL`: Active follower/fan count at reporting time.
- `FOLLOWERS_NET_CHANGE`: Net follower delta (follows gained minus unfollows lost).
- `PROFILE_VIEWS`: Profile visits or Facebook Page views.
- `CLICKS_TOTAL`: Action button taps, website clicks, direction clicks, link clicks.
- `ENGAGEMENT_TOTAL`: Cumulative interactions across content.
- `REACTIONS`: Total positive reactions (likes or reaction types).
- `COMMENTS`: Top-level and reply comment counters.
- `SHARES`: Forward, share, and repost counters.
- `SAVES`: Post bookmark counters (Instagram).
- `VIDEO_VIEWS`: Video playbacks or view events (preserving provider raw metric).
- `VIDEO_WATCH_TIME`: Cumulative view duration in seconds.
- `VIDEO_AVG_WATCH_TIME`: Mean view duration per session in seconds.

### Aggregation Semantics
Every metric is strictly classified by its mathematical behavior:
- `SUMMABLE`: Can be summed across time buckets and posts (e.g. `REACTIONS`, `COMMENTS`, `SHARES`, `SAVES`, `CLICKS_TOTAL`, `VIDEO_WATCH_TIME`).
- `LATEST_VALUE`: Point-in-time gauge; must not be summed across dates (e.g. `FOLLOWERS_TOTAL`).
- `DELTA`: Net shift within a discrete bucket; can be summed to calculate total period delta (e.g. `FOLLOWERS_NET_CHANGE`).
- `AVERAGE`: Ratio or duration that must be averaged, never summed (e.g. `VIDEO_AVG_WATCH_TIME`).
- `NON_AGGREGATABLE`: Unique audience sets that cannot be summed due to user overlap (e.g. `REACH`).

---

## 3. Provider Semantic Caveats & Comparability
- **Reach**: Comparable as unique user counts across Facebook and Instagram. Must never be summed across calendar days.
- **Impressions**: Supported on Facebook. Deprecated on single media on Instagram Graph API v18+; reach and interactions are preferred.
- **Video Views vs. Reel Plays**:
  - Facebook `page_video_views` / `post_video_views` counts views of 3 seconds or longer.
  - Instagram Reels `plays` measures total video playbacks and loops.
  - In `SocialMetricSnapshot`, `normalized_metric='VIDEO_VIEWS'` preserves the exact provider name in `raw_metric_name='plays'` with explicit metadata caveats.

---

## 4. Models & Persistence Architecture

### `SocialMetricSnapshot`
Source-of-truth observation storage.
```python
class SocialMetricSnapshot(models.Model):
    client             = ForeignKey(Client, on_delete=CASCADE, related_name='metric_snapshots', db_index=True)
    platform           = CharField(max_length=30, choices=PLATFORM_CHOICES, db_index=True)
    account_id         = CharField(max_length=120, blank=True, db_index=True)
    metric_scope       = CharField(max_length=20, choices=METRIC_SCOPE_CHOICES, db_index=True)
    object_id          = CharField(max_length=255, db_index=True)

    unified_post       = ForeignKey(UnifiedPost, on_delete=SET_NULL, null=True, blank=True)
    publish_log        = ForeignKey(PlatformPublishLog, on_delete=SET_NULL, null=True, blank=True)

    raw_metric_name    = CharField(max_length=100)
    normalized_metric  = CharField(max_length=60, db_index=True)
    metric_value       = DecimalField(max_digits=20, decimal_places=4, default=0)

    extra_dimensions   = JSONField(default=dict, blank=True)
    dimensions_hash    = CharField(max_length=64, default='', db_index=True)

    bucket_period      = CharField(max_length=20, default='day')
    bucket_timestamp   = DateTimeField(db_index=True)

    provider_timestamp = DateTimeField(null=True, blank=True)
    captured_at        = DateTimeField(auto_now_add=True, db_index=True)
    updated_at         = DateTimeField(auto_now=True)

    freshness_state    = CharField(max_length=20, default='FRESH')
    is_derived          = BooleanField(default=False)
    metadata           = JSONField(default=dict, blank=True)
```
- **Compound Idempotency Constraint**:
  `unique_together = ('client', 'platform', 'metric_scope', 'object_id', 'normalized_metric', 'dimensions_hash', 'bucket_period', 'bucket_timestamp')`
- **Settlement Handling**:
  When re-ingested with settled values (e.g., 24-48 hours later), `update_or_create` updates `metric_value` and `updated_at` in-place without generating duplicates.

### `SocialMetricRollup`
Materialized daily/weekly/monthly rollup cache for sub-millisecond dashboard queries.
- `unique_together = ('client', 'platform', 'metric_scope', 'object_id', 'normalized_metric', 'dimensions_hash', 'period', 'period_start')`.
- Fully rebuildable from `SocialMetricSnapshot` records.

### `PostMetric` Prospective Linkage
Added nullable `unified_post` foreign key:
```python
unified_post = models.ForeignKey('social_stats.UnifiedPost', on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_post_metrics')
```
Populated prospectively during ingestion without mutating legacy records.

### `PlatformCredential` Rate Limit State
Added safe JSONField:
```python
rate_limit_state = models.JSONField(default=dict, blank=True)
```
Stores non-secret quota metrics (`app_usage_percent`, `business_usage_percent`, `cooldown_until`). Secrets or tokens are strictly prohibited.

---

## 5. Dimensions & Deterministic Hashing
Multidimensional observations (e.g. Facebook reaction type breakdown) compute a canonical SHA-256 hash:
```python
def compute_dimensions_hash(dimensions: Optional[Dict]) -> str:
    if not dimensions:
        return ""
    serialized = json.dumps(dimensions, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
```
Two legitimate dimension variants (e.g., `reaction_type=love` vs `reaction_type=like`) produce distinct hashes, preventing collision while guaranteeing idempotency for identical dimensions.

---

## 6. Freshness State Machine
Every snapshot exposes standardized freshness states:
- `FRESH`: Ingested within standard polling cadence.
- `AGING`: Beyond single-cadence window but within $2\times$ threshold.
- `STALE`: Exceeds $2\times$ cadence threshold (e.g. rate limit pause).
- `UNAVAILABLE`: Ingestion failure, expired token, or unsupported provider metric.

---

## 7. Linkage & External Organic Post Support
- Scoped matching: `PlatformPublishLog.objects.filter(unified_post__client=client, platform=platform, platform_post_id=object_id)`.
- If matched: `publish_log` and `unified_post` are attached.
- If not matched (external organic content): `publish_log=None` and `unified_post=None`. The snapshot remains fully valid for brand-wide channel intelligence.

---

## 8. Provider Capability Registry
Located at `backend/social_stats/analytics/capabilities.py`.
- **Facebook**: Full Page counters, Page insights, Post counters, Post insights.
- **Instagram**:
  - Full Mode (with `instagram_manage_insights`): Account timeseries + media insights.
  - Basic Mode (without `instagram_manage_insights`): Degrades gracefully to partial support. Direct media counters (`like_count`, `comments_count`) remain active; account timeseries is disabled.
- **YouTube / LinkedIn / Google Business Profile**: Explicitly declared as `PARTIAL`.
- **TikTok / X**: Explicitly declared as `UNSUPPORTED`.

---

## 9. Migration & Release Baseline Safety
- Migration `0077_social_analytics_foundation.py` is strictly additive.
- Legacy models (`DailyMetric`, `PostMetric`, `PostEngagement`, `SyncLog`, `ROIReport`, `AIInsight`) remain intact and functional.
- Zero mutations to existing Publishing Engine state:
  - `UnifiedPost #12, #13, #14`: published
  - `PlatformPublishLog #12..#15`: success
  - `PostQueue #1, #2`: PAUSED
  - `QueuedItem #2`: waiting / unconsumed
  - Full 256 publishing regression suite + 20 BS-4B tests = 276 tests passing green.
