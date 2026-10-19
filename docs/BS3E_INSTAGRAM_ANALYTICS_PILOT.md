# Phase BS-3E — Instagram Analytics & Insights Resilience Pilot: Formal Closure

**Bop Social — Instagram Professional Insights Capability Architecture, Graceful Degradation & Truthful Observability**

---

## 1. Executive Summary

Phase **BS-3E.3** and **BS-3E.3A** evaluated and hardened the Instagram analytics synchronization pipeline in **Bop Social** through the **Meta Graph API v21.0** for Instagram Professional accounts (**@bopsoluciones** / ID `17841464843082253`), linked to Facebook Page `Bo Projects` (`657647337668646`), under tenant `Client.id = 3` (`Bop Agencia`).

During the initial sync pilot (BS-3E.3), all 15 public Instagram media objects and their associated engagement metrics (`like_count`, `comments_count`) were retrieved successfully and saved into `PostMetric`. However, account-level daily insights (`reach`, `follower_count`, `profile_views`) and per-media insights (`saved`, `shares`, `reach`) returned `HTTP 400 OAuthException 10` ("Application does not have permission for this action") because the elevated permission `instagram_manage_insights` is not granted to the staging credential.

Under Phase **BS-3E.3A**, the Instagram analytics sync architecture was hardened to be **capability-aware**:
$$\text{PlatformCredential (scope)} \longrightarrow \text{Capability Check} \longrightarrow \begin{cases} \text{has } \texttt{instagram\_manage\_insights} & \longrightarrow \text{Full Daily Insights + Per-Media Insights} \\ \text{missing scope} & \longrightarrow \text{Basic Media Metrics + Graceful Degradation} \end{cases}$$

The implementation guarantees:
1. **Zero Unnecessary Provider Errors**: Avoids issuing failing HTTP calls to `/{ig_user_id}/insights` and `/{media_id}/insights` when the credential lacks capability.
2. **Accurate Record Accounting**: Sync status correctly transitions to `partial` with `records_synced = 15` (15 posts synced), with sanitized, truthful observability messages.
3. **No Fake Zeroes**: `DailyMetric` records are not fabricated when data cannot be queried.
4. **Transparent UX**: The frontend surfaces an informative, non-alarming notice explaining that basic media metrics are active while daily timeseries charts require advanced insights access.

---

## 2. Pilot Entity & Credential Architecture

All pilot actions were strictly isolated within the authorized tenant (`Client.id = 3`):

| Entity / Dimension | Value | Architectural Significance |
| :--- | :--- | :--- |
| **Workspace Tenant** | `Bop Agencia` | Authorized pilot workspace |
| **Local Relational PK (`Client.id`)** | `3` | Scoped multi-tenant boundary |
| **Associated Facebook Page** | `Bo Projects` (ID `657647337668646`) | Linked Facebook Page |
| **Instagram Professional Account** | `@bopsoluciones` | Target Instagram Professional profile |
| **Instagram Account ID** | `17841464843082253` | Meta Graph API user node ID |
| **PlatformCredential ID** | `2` | Active Instagram credential |
| **Persisted Scopes** | `read_insights`, `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `business_management`, `pages_read_engagement` | Current granted scopes |
| **Elevated Permission Status** | `instagram_manage_insights: NOT GRANTED` | Rejected by Meta as invalid for current unreviewed app mode |

---

## 3. Root Cause Analysis: Meta Graph API Permission Model

In Meta Graph API v21.0, Instagram Professional account data is segregated into distinct permission tiers:

```mermaid
flowchart TD
    subgraph Basic Tier ["Tier 1: Basic Access (instagram_basic)"]
        MediaList["GET /{ig_user_id}/media"]
        MediaCounts["GET /{media_id}?fields=like_count,comments_count"]
    end

    subgraph Advanced Tier ["Tier 2: Advanced Access (instagram_manage_insights)"]
        DailyInsights["GET /{ig_user_id}/insights (reach, follower_count, profile_views)"]
        MediaInsights["GET /{media_id}/insights (reach, saved, shares, plays)"]
    end

    BasicTierOK["Status: GRANTED (HTTP 200 OK)"]
    AdvTierFail["Status: UNGRANTED (HTTP 400 OAuthException 10)"]

    Basic Tier --> BasicTierOK
    Advanced Tier --> AdvTierFail
```

- **`instagram_basic`**: Allows querying the account's media objects, permalinks, timestamps, media URLs, and public interaction counters (`like_count`, `comments_count`).
- **`instagram_manage_insights`**: Required for querying private performance metrics (`reach`, `impressions`, `profile_views`, `follower_count`, `saved`, `shares`, `video_views`). Without this permission, any call to `/{id}/insights` returns `HTTP 400 OAuthException code 10`.

Attempting to request `instagram_manage_insights` without App Review or appropriate Business Verification leads Meta's OAuth dialog to reject the authorization request entirely. The system must therefore operate resiliently in a two-tier capability model.

---

## 4. Hardened Implementation Architecture

### 4.1 Backend Capability Detection (`social_stats.tasks`)
- Implemented `_has_instagram_insights_capability(cred)`: inspects whitespace/comma-delimited `cred.scope` for `instagram_manage_insights`.
- When capability is absent:
  - Bypasses calls to `/{ig_account_id}/insights`.
  - Records warning: `"Instagram advanced insights unavailable for current credential (instagram_manage_insights not granted); basic media metrics synced."`.
  - Retains queries to `/{ig_account_id}/media` and `/{media_id}?fields=like_count,comments_count`.
  - Bypasses per-post `/{media_id}/insights`.
  - Accurately counts saved media items in `records_synced = daily_count + post_success_count`.
  - Sets `SyncLog.status = 'partial'`.
  - Leaves `DailyMetric` untouched (no empty/zero rows).

### 4.2 Serializer & API Capability Surface (`social_stats.serializers`, `social_stats.views`)
- **`PlatformCredentialSerializer`**: Added read-only field `analytics_level`: returns `'advanced'` if `instagram_manage_insights` is present, else `'basic'`.
- **`ClientViewSet.summary`**: Exposes a structured `capabilities` dictionary:
  ```json
  {
    "instagram": {
      "analytics_level": "basic",
      "supports_timeseries": false,
      "supports_media_metrics": true,
      "reason": "instagram_manage_insights scope not granted; timeseries insights unavailable"
    },
    "facebook": {
      "analytics_level": "advanced",
      "supports_timeseries": true,
      "supports_media_metrics": true,
      "reason": null
    }
  }
  ```

### 4.3 Frontend Resilience (`ClientDashboard.jsx`, `AnalyticsPage.jsx`)
- Replaced ambiguous "No data yet / click sync" messages when viewing Instagram with basic analytics.
- Displays clear, non-alarming capability cards explaining that post-level analytics are active while timeseries graphs require elevated insights permissions.

---

## 5. Verification & Test Suite Evidence

A dedicated unit test suite was implemented in `backend/social_stats/tests/test_instagram_analytics_resilience.py` covering 10 distinct cases:
1. `test_case_1_capability_helper_without_insights_scope`: Confirms capability evaluates `False` without scope.
2. `test_case_2_capability_helper_with_insights_scope`: Confirms capability evaluates `True` with scope.
3. `test_case_3_sync_without_insights_scope_degrades_gracefully`: Verifies zero calls to insights endpoints, 0 DailyMetric, 1 PostMetric with likes/comments, SyncLog `partial` with truthful message.
4. `test_case_4_sync_with_insights_scope_full_success`: Verifies complete sync when scope is present (DailyMetric + PostMetric + SyncLog `success`).
5. `test_case_5_post_detail_failure_still_records_post`: Verifies post is retained even if per-post detail query errors.
6. `test_case_6_media_fetch_error_marks_failed_if_no_records`: Verifies fatal media fetch errors result in `failed` status when 0 records are synced.
7. `test_case_7_missing_credential_raises`: Confirms proper exception and `failed` logging on missing credential.
8. `test_case_8_access_token_redacted_on_exception`: Proves `[REDACTED]` replaces any access tokens in error messages.
9. `test_case_9_serializer_analytics_level`: Confirms serialization of `'basic'` vs `'advanced'`.
10. `test_case_10_client_summary_capabilities`: Validates the structure and content of `capabilities` in `/api/clients/{id}/summary/`.

All 10 tests and 59 regression suite tests execute with **100% PASS**:
- `social_stats.tests.test_instagram_analytics_resilience` — 10 tests PASS (0.48s)
- `social_stats.tests.test_facebook_analytics_resilience` — 8 tests PASS
- `social_stats.tests.test_dashboard_endpoints` — 27 tests PASS
- `social_stats.tests.test_regressions` — 12 tests PASS
- `social_stats.tests.test_publishers_instagram` — 12 tests PASS

---

## 6. Database Baseline Invariants Preserved

All existing database baseline invariants from prior phases remain strictly intact:
- `UnifiedPost`: `3`
- `PlatformPublishLog`: `3`
- `MediaAsset`: `2`
- `DailyMetric`: `30` (Facebook: 30, Instagram: 0)
- `PostMetric`: `29` (Facebook: 14, Instagram: 15)
- `SyncLog`: `3` (SyncLog 1 & 2: Facebook, SyncLog 3: Instagram)
