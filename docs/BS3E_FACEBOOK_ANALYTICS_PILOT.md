# BOP SOCIAL — BS-3E FACEBOOK ANALYTICS PILOT & HARDENING

## 1. Pilot Context & Initial Execution (Phase BS-3E.2)

- **Target Tenant:** Client ID `3` (Bop Agencia)
- **Target Platform:** Facebook
- **Connected Account:** `Bo Projects` (Facebook Page ID `657647337668646`)
- **Credential:** `PlatformCredential.id = 1`
- **Authorized Scopes:** `read_insights`, `pages_read_engagement`, `pages_manage_posts`, `pages_show_list`
- **Trigger Method:** `POST /api/clients/3/trigger_sync/` with payload `{"platforms": ["facebook"]}`
- **Execution Date:** 2026-10-19
- **Celery Task ID:** `5211e4b0-2a5b-4e90-b22b-eb70865f974c`

---

## 2. First Pilot Results & Root Cause Analysis

### Results
- `DailyMetric` records: `0`
- `PostMetric` records: `14` (Ingested successfully)
  - Post #1 (`657647337668646_1659782972329595`) — Facebook Text Pilot
  - Post #2 (`657647337668646_1661141888860370`) — Facebook Media Pilot
  - 12 additional historical posts dating from 2015 to 2026
- `SyncLog`: `1` record (`status = success`, `records_synced = 0`)
- **Initial Classification:** `PARTIAL`

### Root Cause
During the Page Insights daily metrics fetch, `sync_facebook` requested a comma-separated batch of 7 metrics:
`page_impressions_unique,page_post_engagements,page_views_total,page_daily_follows,page_daily_unfollows,page_video_views,page_total_actions`

In Meta Graph API v21.0, `page_impressions_unique` has been deprecated. Meta rejected the entire batch with:
```
HTTP 400 OAuthException (code 100): "(#100) The value must be a valid insights metric"
```

Because the legacy task used `insights.get('data', [])`, the error object caused the code to silently evaluate to an empty list, discarding the other 6 valid metrics. Meanwhile, `PostMetric` processing succeeded completely for all 14 posts, and the task concluded with `status = success` and `records_synced = 0`, masking the partial failure.

---

## 3. Resilience & Hardening Architecture (Phase BS-3E.2A)

### 3.1. Active Metrics Configuration
Removed the deprecated `page_impressions_unique` metric. The confirmed active Page Insights metric list is:
```python
FACEBOOK_PAGE_METRICS = [
    'page_post_engagements',    # engagements -> likes
    'page_views_total',         # page views -> profile_views
    'page_daily_follows',       # new followers -> followers
    'page_daily_unfollows',     # unfollows -> followers_lost
    'page_video_views',         # video views -> fb_video_views
    'page_total_actions',       # total actions on page -> clicks
]
```
`page_actions_post_reactions_total` is maintained in its dedicated request.

### 3.2. Single-Metric Fallback Fetcher (`_fetch_facebook_page_insights`)
To guarantee that a future metric deprecation by Meta cannot discard all valid metrics:
1. **Primary Attempt:** Sends a fast, single-call batch request with all configured metrics.
2. **Fallback:** If Meta responds with an error (e.g. invalid metric code 100), the helper falls back to querying each metric individually, collecting all successful 200 responses and recording sanitized warnings for any failing metrics.

### 3.3. SyncLog Status Semantics
Added `'partial'` to `SYNC_STATUS` choices in `social_stats.models`:
- **`success`:** All requested stages completed with data and without provider warnings.
- **`partial`:** At least one stage produced valid data (e.g., posts succeeded or partial daily metrics succeeded), but a provider error or warning occurred.
- **`failed`:** No useful ingestion completed, or a fatal exception occurred.

### 3.4. `records_synced` Semantics
Redefined `records_synced` from tracking only daily metric rows to tracking the sum of all successfully processed analytics records:
```python
total_records = daily_count + post_success_count
```

### 3.5. Post-Level Resilience
Individual post failures during insights or reactions queries no longer fail the loop silently without observation:
- Succeeded posts increment `post_success_count`.
- Failed posts increment `post_fail_count` and log sanitized warnings.
- Succeeded posts are saved; if any post failed, the sync status resolves to `partial`.

### 3.6. Frontend Support
Updated `AdminOverview.jsx` and localization dictionaries (`en/dashboard.json`, `es/dashboard.json`):
- Added amber warning badge styling for `partial` status (`#fef3c7` background, `#d97706` text).
- Replaced misleading green success rendering on partial syncs with explicit amber warning indicators.

---

## 4. Verification & Invariants

- **Resilience Test Suite:** 8 test cases in `social_stats/tests/test_facebook_analytics_resilience.py` (all PASS).
- **Regression Suite:** 72 total tests executed (resilience, dashboard endpoints, regressions, publishers) with 100% PASS.
- **Database Baseline Preserved:**
  - `UnifiedPost = 3`
  - `PlatformPublishLog = 3`
  - `MediaAsset = 2`
  - `DailyMetric = 0`
  - `PostMetric = 14` (Pilot records preserved)
  - `SyncLog = 1` (Pilot execution log preserved)
- **External Network Safety:** 0 Meta real calls performed during test executions.

---

## 5. Next Step: Controlled Rerun (Phase BS-3E.2B)
With resilience and status hardening in place, execute a second controlled Facebook analytics sync pilot for Client 3 to verify that `DailyMetric` populates with the 6 confirmed metrics alongside the 14 `PostMetric` records with `status = success` and `records_synced > 0`.
