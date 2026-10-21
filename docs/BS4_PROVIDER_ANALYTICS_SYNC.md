# BOP SOCIAL — BS-4C: PROVIDER ANALYTICS SYNC ADAPTERS & CONTROLLED INGESTION

## 1. Overview & Architecture
Phase **BS-4C** delivers the ingestion engine that connects Meta Graph API v21.0 to the Bop Social Analytics Foundation established in BS-4B. The implementation provides resilient, rate-limited, and deterministic data collection across Facebook Pages and Instagram Professional accounts while maintaining strict isolation from the live Publishing Engine v1 baseline.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Meta Graph API v21.0                                │
│        Facebook Page & Post Nodes     │   Instagram Business & Media Nodes   │
└──────────────────────┬────────────────┴──────────────────────┬──────────────┘
                       │                                       │
                       ▼                                       ▼
        ┌──────────────────────────────┐        ┌──────────────────────────────┐
        │   FacebookAnalyticsAdapter   │        │   InstagramAnalyticsAdapter  │
        └──────────────┬───────────────┘        └──────────────┬───────────────┘
                       │                                       │
                       └───────────────────┬───────────────────┘
                                           │ ProviderPayload
                                           ▼
                       ┌───────────────────────────────────────┐
                       │   SocialMetricSnapshot Normalizer     │
                       │   (Deterministic dimensions_hash)     │
                       └───────────────────┬───────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
     ┌─────────────────────────────────────┐  ┌────────────────────────────────┐
     │ SocialMetricSnapshot (Foundation)   │  │ Dual-Write (Legacy Compatibility)│
     │ - In-place settlement updates       │  │ - DailyMetric                  │
     │ - Zero row duplication              │  │ - PostMetric                   │
     │ - Velocity & point-in-time tracking │  │ - SyncLog                      │
     └─────────────────────────────────────┘  └────────────────────────────────┘
```

### Core Design Principles
1. **Publishing Pipeline Isolation**: Analytics ingestion runs on a separate Celery queue (`analytics`), with read-only provider scopes, making zero writes to `UnifiedPost`, `PlatformPublishLog`, or `PostQueue`.
2. **Deterministic Settlement**: Re-syncing an existing time window updates observations in-place with `settlement_status='FINAL'`, guaranteeing zero duplicate snapshot records.
3. **Graceful Degradation**: Accounts lacking deep insight scopes (such as `instagram_manage_insights`) automatically degrade from `FULL` to `PARTIAL` mode, safely persisting public direct metrics without failing.
4. **Active Rate-Limit Defense**: Real-time parsing of `X-App-Usage` and `X-Business-Use-Case-Usage` headers triggers predictive deferral (at 80%) and automatic cooldown (at 90%).
5. **Dual-Write Backward Compatibility**: Ingested telemetry populates both the new canonical metric store (`SocialMetricSnapshot`) and legacy reporting tables (`DailyMetric`, `PostMetric`, `SyncLog`).

---

## 2. Facebook Analytics Adapter Specification
The `FacebookAnalyticsAdapter` (`backend/social_stats/analytics/adapters/facebook.py`) queries Meta Graph API v21.0 for Facebook Page and Post telemetry.

### Page Node & Direct Counters
- **Followers / Fans**: Direct query to `GET /{page_id}?fields=followers_count,fan_count`.
  - Normalizes `followers_count` as canonical `FOLLOWERS_TOTAL` with aggregation `LATEST_VALUE`.
  - Falls back to `fan_count` if `followers_count` is absent.

### Page Insights
- **Endpoint**: `GET /{page_id}/insights?metric={metrics}&period=day&since={since}&until={until}`
- **Batch Query Metrics**:
  - `page_impressions_unique` -> canonical `REACH` (`NON_AGGREGATABLE`).
  - `page_impressions` -> canonical `IMPRESSIONS` (`SUMMABLE`).
  - `page_views_total` -> canonical `PROFILE_VIEWS` (`SUMMABLE`).
  - `page_post_engagements` -> canonical `ENGAGEMENT_TOTAL` (`SUMMABLE`).
  - `page_video_views` -> canonical `VIDEO_VIEWS` (`SUMMABLE`, caveat: 3-second or longer views).
- **Graceful Fallback**: If the batched insights call fails (e.g. unsupported metric or permission issue), the adapter iterates through individual metrics, capturing available metrics while isolating failures.

### Page Reactions Breakdown
- Queries `page_actions_post_reactions_total` by period.
- Normalizes individual reaction types (`like`, `love`, `wow`, `haha`, `sorry`, `anger`) with canonical metric `REACTIONS` and distinct dimension hashes:
  - `dimensions={"reaction_type": "like"}`
  - `dimensions={"reaction_type": "love"}`, etc.

### Post-Level Insights & Metrics
- **Direct Post Counters**: `GET /{page_post_id}?fields=id,created_time,message,shares,comments.summary(true),likes.summary(true)`
  - `shares.count` -> canonical `SHARES`.
  - `comments.summary.total_count` -> canonical `COMMENTS`.
  - `likes.summary.total_count` -> canonical `REACTIONS` (`reaction_type="like"`).
- **Post Insights**: `GET /{page_post_id}/insights?metric=post_impressions_unique,post_impressions,post_reactions_by_type_total,post_video_views`
  - `post_impressions_unique` -> canonical `REACH`.
  - `post_impressions` -> canonical `IMPRESSIONS`.
  - `post_reactions_by_type_total` -> reaction breakdown.
  - `post_video_views` -> canonical `VIDEO_VIEWS`.
- **Linkage**: Matches `page_post_id` against `PlatformPublishLog.platform_post_id` to link with `UnifiedPost`. Unmatched posts are ingested as external organic content (`unified_post=None`).

---

## 3. Instagram Analytics Adapter Specification
The `InstagramAnalyticsAdapter` (`backend/social_stats/analytics/adapters/instagram.py`) manages Instagram Professional Accounts (Business / Creator).

### Account Node & Direct Counters
- **Endpoint**: `GET /{ig_user_id}?fields=followers_count,media_count`
- Captures `followers_count` -> canonical `FOLLOWERS_TOTAL`.

### Account Standard Insights (`day` period)
- **Endpoint**: `GET /{ig_user_id}/insights?metric=reach,profile_views,website_clicks&period=day&since={since}&until={until}`
- Metrics:
  - `reach` -> canonical `REACH`.
  - `profile_views` -> canonical `PROFILE_VIEWS`.
  - `website_clicks` -> canonical `CLICKS_TOTAL` (`click_type="website"`).

### Account Total-Value Insights
- **Endpoint**: `GET /{ig_user_id}/insights?metric=views,reach,total_interactions,accounts_engaged&metric_type=total_value&period=day`
- Metrics:
  - `views` -> canonical `IMPRESSIONS`.
  - `reach` -> canonical `REACH`.
  - `total_interactions` -> canonical `ENGAGEMENT_TOTAL`.
  - `accounts_engaged` -> canonical `ENGAGEMENT_TOTAL` (`dimension="engaged_accounts"`).

### Media-Level Insights
- Supported Media Types: `IMAGE`, `VIDEO`, `CAROUSEL_ALBUM`, `REEL`, `STORY`.
- Direct Counters:
  - `comments_count` -> canonical `COMMENTS`.
  - `like_count` -> canonical `REACTIONS`.
- Media Insights Metrics by Type:
  - **IMAGE / CAROUSEL_ALBUM**: `reach`, `saved`, `total_interactions`.
  - **VIDEO / REEL**: `reach`, `saved`, `total_interactions`, `plays` (normalized to `VIDEO_VIEWS`, `raw_metric_name="plays"`).
  - **STORY**: `reach`, `shares`, `replies` (normalized to `COMMENTS`).

### Story Expiration & Lifetime Semantics
- Instagram Stories expire from the API after 24 hours.
- When querying an expired or deleted story:
  - Adapter catches `AnalyticsObjectUnavailableError` / code 100 subcode 33.
  - Returns `[]` without raising an exception.
  - Existing settled snapshots in `SocialMetricSnapshot` remain untouched (`settlement_status='FINAL'`).
  - No synthetic zeroes are generated.

### Permission Modes (`FULL` vs `PARTIAL`)
- **FULL Mode** (`instagram_manage_insights` present in `PlatformCredential.capabilities`):
  - Fetches account insights, total_value metrics, and media insights.
- **PARTIAL Mode** (lacks `instagram_manage_insights`):
  - Skips insights endpoints.
  - Collects direct counters: `followers_count`, media `like_count`, and `comments_count`.
  - Logs warning without terminating sync in failure.

---

## 4. Rate-Limit Governance & Backoff
Located at `backend/social_stats/analytics/rate_limits.py`.

### Header Parsing
Meta rate-limit headers are extracted from every HTTP response:
- `X-App-Usage`: e.g. `{"call_count": 82, "total_cputime": 45, "total_time": 60}`
- `X-Business-Use-Case-Usage`: e.g. `{"100110011001": [{"type": "pages", "call_count": 85, "estimated_time_to_regain_access": 10}]}`

### Persistence & State Evaluation
The peak percentage across all dimensions is tracked on `PlatformCredential.rate_limit_state`:
```json
{
  "last_checked_at": "2026-10-21T21:15:00Z",
  "app_usage": {"call_count": 85, "total_cputime": 40, "total_time": 50},
  "business_usage": {},
  "peak_pct": 85,
  "throttled_until": null,
  "last_status": "DEFER_HISTORICAL"
}
```

### Governance Rules
| Peak Usage | Status | Action |
|---|---|---|
| `< 80%` | `OK` | Normal execution of all sync requests. |
| `>= 80%` and `< 90%` | `DEFER_HISTORICAL` | Execute account-level sync; skip deep post backfills. |
| `>= 90%` | `COOLDOWN` | Immediate rejection; set `throttled_until = now + 15 min`. |

### Celery Exponential Backoff
When Meta returns HTTP 429, error code 4 (Application request limit reached), error code 17 (User request limit reached), or code 32 (Page request limit reached):
- The Celery task catches `AnalyticsRateLimitedError`.
- Executes `self.retry(countdown=min(300 * (2 ** self.request.retries), 3600), exc=exc)`.
- Never drops data silently.

---

## 5. Error Classification & Failure Handling
Located at `backend/social_stats/analytics/exceptions.py`.

### Exception Hierarchy
```
AnalyticsError (Base)
├── AnalyticsPermanentError
│   ├── AnalyticsAuthExpiredError (Meta code 190, session expired / revoked)
│   ├── AnalyticsPermissionError (Meta code 200, missing required permission)
│   ├── AnalyticsObjectUnavailableError (Meta code 100 subcode 33, deleted/expired)
│   └── AnalyticsMetricUnsupportedError (Meta code 100 subcode 2108, unsupported metric)
└── AnalyticsTemporaryError
    ├── AnalyticsRateLimitedError (Meta code 4, 17, 32, HTTP 429)
    └── AnalyticsTemporaryProviderError (Meta code 1, 2, HTTP 500/503)
```

### Handling Rules
1. **Auth Expired (`190`)**: Set `credential.is_active = False`, log security audit event, terminate sync immediately. No retries.
2. **Permission Missing (`200`)**: Log capability degradation; downgrade from `FULL` to `PARTIAL`.
3. **Object Expired / Deleted**: Catch locally, skip object, continue syncing remaining media.
4. **Unsupported Metric**: Log warning, remove metric from query set, continue syncing valid metrics.
5. **Temporary / Rate Limit**: Retry with exponential backoff.

---

## 6. Dual-Write & Backward Compatibility
The sync service (`backend/social_stats/analytics/sync_service.py`) populates both analytics systems:

### Dual-Write Architecture
1. **Primary Destination (`SocialMetricSnapshot`)**:
   - Stores granular observations with dimension hashing.
   - Updates existing snapshots in-place using `snapshot.update_settlement(new_value, settlement_status='FINAL')`.
   - Guaranteed zero row explosion.
2. **Legacy Destination (`DailyMetric`, `PostMetric`, `SyncLog`)**:
   - `DailyMetric`: Aggregates daily `reach`, `impressions`, `profile_views`, `engagement`, and follower counts.
   - `PostMetric`: Updates per-post `likes`, `comments`, `shares`, `impressions`, and `reach`.
   - `SyncLog`: Records sync execution duration, status (`SUCCESS`, `PARTIAL`, `FAILED`), and error messages.

---

## 7. Celery Task Interface
Located at `backend/social_stats/analytics_tasks.py`.

### Task Signatures
```python
@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_client_facebook_analytics_v2(self, client_id: int, days_back: int = 7, sync_posts: bool = True) -> dict:
    ...

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_client_instagram_analytics_v2(self, client_id: int, days_back: int = 7, sync_posts: bool = True) -> dict:
    ...
```

### Queue Separation
- Tasks are routed to the `analytics` Celery queue.
- Dedicated worker pools prevent ingestion tasks from competing with time-critical publication tasks (`publishing` queue) or queue monitor watchdogs (`watchdog` queue).

---

## 8. Scheduling Cadence & Operations Guide

### Recommended Periodic Cadence (Celery Beat)
| Cadence | Task Scope | Parameters | Purpose |
|---|---|---|---|
| **Hourly** | Light Sync | `days_back=2, sync_posts=True` | Rapid detection of post engagement and recent reach. |
| **Daily (03:00 UTC)** | Daily Settlement | `days_back=14, sync_posts=True` | Settle recent 14 days of metrics to `FINAL` status. |
| **Weekly (Sunday 04:00 UTC)** | Monthly Audit | `days_back=30, sync_posts=False` | Deep reconciliation of follower totals and monthly reach. |

### Operator Invocations
```python
# Manual trigger via Django shell or admin action:
from social_stats.analytics_tasks import sync_client_facebook_analytics_v2, sync_client_instagram_analytics_v2

# Facebook:
sync_client_facebook_analytics_v2.delay(client_id=1, days_back=7)

# Instagram:
sync_client_instagram_analytics_v2.delay(client_id=1, days_back=7)
```

### Health & Alerting Thresholds
- **Rate Limit Alert**: Trigger warning notification when `peak_pct >= 80%`.
- **Auth Failure Alert**: Trigger high-priority alert when `AnalyticsAuthExpiredError` occurs, notifying the client to re-authenticate OAuth.
- **Sync Failure Rate**: Alert if consecutive sync failures exceed 3 runs for a single credential.
