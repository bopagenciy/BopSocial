# BOP SOCIAL — BS-4D: UNIFIED SOCIAL ANALYTICS ROLLUP, CADENCE & FRESHNESS AUTOMATION

## 1. Overview & Architecture
Phase **BS-4D** implements the analytics rollup engine, freshness tracking service, cadence orchestration, and read-layer API for Bop Social. It bridges the granular observation store (`SocialMetricSnapshot`) with high-performance, dashboard-ready materialized caches (`SocialMetricRollup`), while preserving strict isolation from the verified Publishing Engine v1 baseline.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SocialMetricSnapshot (Store of Truth)                  │
│       269 Facebook Snapshots         │         43 Instagram Snapshots        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Rollup Service                                 │
│  - Client timezone transformation (America/New_York vs UTC)                  │
│  - Aggregation semantics (SUMMABLE, LATEST_VALUE, DELTA, AVERAGE)          │
│  - Non-aggregatable REACH protection (strictly no multi-day reach sums)     │
│  - Dimension preservation (deterministic dimensions_hash)                   │
│  - Idempotent upsert into SocialMetricRollup (0 duplicate groups)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Analytics Cadence & Orchestrator                         │
│  - Sync due evaluation based on entity lifecycle                            │
│  - Concurrency lock (prevents duplicate Beat dispatches)                    │
│  - Rate-limit governance (80% DEFER, 90% COOLDOWN)                          │
│  - Capability awareness (Instagram PARTIAL vs FULL mode)                    │
│  - Dedicated 'analytics' Celery queue                                       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Analytics API Read Layer                            │
│  GET /api/analytics/summary/   - Metric cards, tenant-isolated, comparability│
│  GET /api/analytics/trends/    - Timeseries datapoints with freshness state  │
│  GET /api/analytics/top-posts/ - Ranked posts (Bop-authored vs organic)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Canonical Aggregation Semantics
Located at `backend/social_stats/analytics/rollups.py`.

Every canonical metric in `CANONICAL_METRICS` adheres strictly to its mathematical behavior:

| Behavior | Description | Example Metrics | Aggregation Implementation |
|---|---|---|---|
| **SUMMABLE** | Discrete events that accumulate across time and content | `REACTIONS`, `COMMENTS`, `SHARES`, `IMPRESSIONS`, `CLICKS_TOTAL`, `VIDEO_WATCH_TIME` | `sum(snapshot.metric_value)` |
| **LATEST_VALUE** | Point-in-time gauges reflecting account state | `FOLLOWERS_TOTAL` | Most recent observation by `(bucket_timestamp, captured_at)` |
| **DELTA** | Net changes within discrete buckets | `FOLLOWERS_NET_CHANGE` | `sum(snapshot.metric_value)` |
| **AVERAGE** | Durations and ratios | `VIDEO_AVG_WATCH_TIME` | `sum(snapshot.metric_value) / count` |
| **NON_AGGREGATABLE** | Unique user sets with unknown audience overlap | `REACH` | See Section 3 below |

---

## 3. Non-Aggregatable Metrics & REACH Protection
`REACH` measures unique accounts that saw content. Because the audience viewing content on consecutive days overlaps, daily reach observations **must never be mathematically added together** to calculate weekly or monthly reach.

### Safety Rules Implemented:
1. **Daily Rollups (`period='day'`)**:
   - The single-day reach observation is preserved directly: `metric_value = latest_snapshot.metric_value`, `metadata['is_available'] = True`.
2. **Multi-Day Rollups (`period in ('week', 'month')`)**:
   - If Meta provides a native multi-day reach observation matching that exact period (`bucket_period == period`), that observation is used.
   - If only daily snapshots exist, the rollup engine **strictly refuses to sum them**. It sets:
     - `metric_value = Decimal('0.0000')`
     - `metadata['is_available'] = False`
     - `metadata['unavailable_reason'] = "Cannot sum REACH across N daily observations into a multi-day period. Audience overlap prevents mathematical summation."`
   - Zero fabricated reach values are ever generated.

---

## 4. Timezone & Boundary Handling
- **Storage**: All raw snapshot bucket timestamps remain strictly UTC in PostgreSQL.
- **Rollup Alignment**:
  - Rollup periods align to the client's business timezone (`Client.timezone`, e.g. `America/New_York`).
  - Fallback: Defaults safely to `UTC` if timezone is invalid or unspecified.
- **Period Definitions**:
  - `day`: Calendar date in client local timezone (`local_dt.date()`).
  - `week`: Canonical ISO Monday (`local_date - timedelta(days=local_date.weekday())`).
  - `month`: 1st day of client local month (`local_date.replace(day=1)`).
- **Daylight Saving Time (DST)**:
  - Conversion via Python's standard `zoneinfo.ZoneInfo` guarantees accurate handling of Spring forward and Fall back transitions without off-by-one calendar shifts.

---

## 5. Rollup Idempotency & Dimensions
- **Identity Key**:
  `SocialMetricRollup` enforces a strict 8-field composite unique constraint:
  `('client', 'platform', 'metric_scope', 'object_id', 'normalized_metric', 'dimensions_hash', 'period', 'period_start')`.
- **Deterministic Rebuild**:
  - Running `build_rollups_for_client` repeatedly updates existing records in place.
  - Zero duplicate records are generated.
- **Multidimensional Dimensions**:
  - Distinct `dimensions_hash` values (e.g., reaction breakdowns `like` vs. `love`) are preserved as separate rollup records, ensuring reaction distributions do not collapse.

---

## 6. Freshness Service
Located at `backend/social_stats/analytics/freshness.py`.

Evaluates data staleness based on entity type and expected cadence:

| Scope | Condition | Cadence | FRESH | AGING | STALE | UNAVAILABLE |
|---|---|---|---|---|---|---|
| **Account** | Channel level | 24 hours | `< 24h` | `24h – 48h` | `>= 48h` | Never synced |
| **Post (Recent)** | Published `< 48h` ago | 4 hours | `< 4h` | `4h – 12h` | `>= 12h` | Never synced |
| **Post (Maturing)** | Published `3 – 14 days` ago | 24 hours | `< 24h` | `24h – 48h` | `>= 48h` | Never synced |
| **Post (Old)** | Published `> 14 days` ago | 7 days | `< 7d` | `7d – 14d` | `>= 14d` | Never synced |
| **Story** | Published `< 24h` ago | 3 hours | `< 3h` | `3h – 6h` | `>= 6h` | Published `> 24h` (expired) |

Exposes `last_synced_at`, `data_age_seconds`, and `next_scheduled_sync` via API.

---

## 7. Cadence Policy & Sync Orchestrator
Located at `backend/social_stats/analytics/orchestrator.py`.

### Orchestrator Workflow (`run_analytics_orchestrator`):
1. **Active Scan**: Finds active `PlatformCredential` instances for Facebook and Instagram.
2. **Rate Limit Gate**:
   - If `rate_limit_state` has peak usage `>= 90%` (`COOLDOWN`): skips sync until cooldown window expires.
   - If peak usage `>= 80%` (`DEFER_HISTORICAL`): defers non-critical deep history backfills.
3. **Capability Mode Detection**:
   - Automatically detects if Instagram credential has `instagram_manage_insights`.
   - If missing, sets `capability_mode = 'PARTIAL'` and restricts sync to direct counters.
4. **Due Evaluation**:
   - Checks elapsed time since latest completed `SyncLog` against cadence rules.
5. **Duplicate Dispatch Protection (Concurrency Lock)**:
   - Acquires atomic lock via `SyncLog.status == 'running'` within 15-minute window and atomic cache lock (`analytics_sync_lock:{client_id}:{platform}`).
   - Rejects concurrent Beat ticks from double-dispatching the same credential.
6. **Celery Queue Routing**:
   - Dispatches tasks to dedicated `analytics` queue (`sync_client_facebook_analytics_v2`, `sync_client_instagram_analytics_v2`).
   - Zero worker contention with critical `publishing` and `watchdog` queues.

---

## 8. Analytics API Read Layer
Located at `backend/social_stats/analytics/api.py`.

### 1. `GET /api/analytics/summary/`
- **Purpose**: High-level KPI cards for dashboard overviews.
- **Query Params**: `client_id` (required), `platform` (optional, default: all), `period` (`day`/`week`/`month`), `start_date`, `end_date`, `metric` (optional).
- **Features**:
  - Tenant isolation: verified client access.
  - Cross-platform comparability: detects non-comparable cross-platform metrics (e.g. `CLICKS_TOTAL`) and attaches explicit warning caveat.

### 2. `GET /api/analytics/trends/`
- **Purpose**: Chronological timeseries charts.
- **Query Params**: `client_id`, `metric` (required), `platform`, `period`, `start_date`, `end_date`.
- **Response**: Array of `{period_start, metric_value, sample_count, is_available}`.

### 3. `GET /api/analytics/top-posts/`
- **Purpose**: Ranked list of top performing content.
- **Query Params**: `client_id`, `platform`, `metric` (default: `REACTIONS`), `limit` (default: 10), `start_date`, `end_date`.
- **Bop Linkage**: Clearly distinguishes Bop-authored posts (`is_bop_authored: true`, `unified_post_id`, `publish_log_id`) from organic posts (`is_bop_authored: false`, `unified_post_id: null`).

---

## 9. Backfill Service & Production Activation Runbook

### Rollup Backfill (`backend/social_stats/analytics/backfill.py`):
```python
# Dry run preview (safe):
from social_stats.analytics.backfill import backfill_rollups
backfill_rollups(client_id=3, dry_run=True)

# Authorized execution:
backfill_rollups(client_id=3, periods=('day', 'week', 'month'), dry_run=False)
```

### Production Celery Beat Activation Runbook (Future Phase):
1. **Pre-check**: Ensure workers are consuming from the `analytics` queue (`celery -A dashboard worker -Q celery,publishing,watchdog,analytics`).
2. **Periodic Task Registration**:
   Add to `django_celery_beat.models.PeriodicTask`:
   - `analytics-orchestrator-hourly`: `social_stats.analytics_tasks.run_analytics_orchestrator_task` (runs every 60 minutes).
3. **Monitor**: Check `PlatformCredential.rate_limit_state` and ensure peak usage remains `< 80%`.
