# BOP SOCIAL — Phase BS-4F Business Intelligence Foundation
**Status**: APPROVED / VERIFIED
**Baseline HEAD**: `827f5faa1716b866ef7b25dfe4f47bb06b3347f6`
**Branch**: `feature/bs-4f-business-intelligence`

---

## 1. Executive Summary & Purpose

Phase **BS-4F** introduces a **deterministic, explainable Business Intelligence (BI) layer** to Bop Social. It bridges the gap between normalized raw aggregations (e.g. *"Post X received 27 reactions"*) and defensible business conclusions (e.g. *"Post X performed 2.1x above the recent median for comparable image content"*), **without generative AI**.

All signals are machine-readable, idempotent, fully traced to source snapshots and rollups, and designed to serve as the ground truth foundation for future narrative AI, executive summaries, or scheduled PDF reports.

---

## 2. Core Architecture & Taxonomy

The canonical business intelligence architecture is structured around the `BusinessSignal` model and its deterministic evaluation services.

### 2.1 Signal Types (`signal_type`)

| Signal Type | Scope | Description |
|---|---|---|
| `CONTENT_OUTPERFORMING` | `post` | Post performed $\ge +20\%$ above cohort median. |
| `CONTENT_UNDERPERFORMING` | `post` | Post performed $\le -20\%$ below cohort median. |
| `FORMAT_OUTPERFORMING` | `format` | Format (e.g. Reel) median outperformed overall platform median by $\ge +20\%$. |
| `FORMAT_UNDERPERFORMING` | `format` | Format median underperformed overall platform median by $\le -20\%$. |
| `POSTING_TIME_OUTPERFORMING` | `time` | Posts in a local hour bucket performed $\ge +20\%$ above overall median. |
| `POSTING_TIME_UNDERPERFORMING` | `time` | Posts in a local hour bucket performed $\le -20\%$ below overall median. |
| `ENGAGEMENT_TREND_UP` | `account` | Period median engagement trended upwards vs prior comparison window. |
| `ENGAGEMENT_TREND_DOWN` | `account` | Period median engagement trended downwards vs prior comparison window. |
| `FOLLOWER_GROWTH_UP` | `account` | Net follower change accelerated compared to prior comparison window. |
| `FOLLOWER_GROWTH_DOWN` | `account` | Net follower change decelerated compared to prior comparison window. |
| `MOMENTUM_UP` | `account` | Recent 7-day median outperformed previous 7-day median by $\ge +20\%$. |
| `MOMENTUM_DOWN` | `account` | Recent 7-day median underperformed previous 7-day median by $\le -20\%$. |
| `POSITIVE_OUTLIER` | `post` | Statistical positive anomaly detected via Median Absolute Deviation (MAD). |
| `NEGATIVE_OUTLIER` | `post` | Statistical negative anomaly detected via Median Absolute Deviation (MAD). |
| `DATA_STALE` | `account` | Source data has not synced in $>24-48$ hours. |
| `INSUFFICIENT_SAMPLE` | `post` / `format` | Cohort observations $n < 3$; defensible conclusions suppressed. |
| `PROVIDER_PARTIAL` | `account` | Platform capability is in PARTIAL mode (e.g. Instagram). |
| `METRIC_UNAVAILABLE` | `account` | Requested metric unsupported by provider permissions. |

---

## 3. Baseline & Statistical Methodology

1. **Median First**: Social engagement data is heavily skewed by viral posts. Median is strictly preferred over arithmetic mean to prevent single outliers from distorting baselines.
2. **Median Absolute Deviation (MAD)**: Anomaly detection utilizes $MAD = \text{median}(|X_i - \text{median}(X)|)$ with a $2.5\times$ cutoff for robust outlier identification without heavy machine learning dependencies.
3. **No Fake Zeros**: When baseline values are zero or observations are missing, relative deltas return `null` (`None`) rather than division-by-zero or fake infinity.

---

## 4. Centralized Thresholds & Confidence Model

### 4.1 Performance Tiers

Centralized in `social_stats/analytics/intelligence/rules.py`:

```python
THRESHOLDS = {
    "STRONG_OUTPERFORMANCE": Decimal("0.5000"),    # >= +50%
    "OUTPERFORMANCE": Decimal("0.2000"),           # +20% to +49.99%
    "NORMAL_LOWER": Decimal("-0.2000"),            # -19.99% to +19.99%
    "UNDERPERFORMANCE": Decimal("-0.2000"),        # -20% to -49.99%
    "STRONG_UNDERPERFORMANCE": Decimal("-0.5000"), # <= -50%
}
```

### 4.2 Confidence Tiers

Confidence is never subjective. It is calculated deterministically:

| Sample Size ($n$) | Base Confidence | Stale / Partial Downgrade |
|---|---|---|
| $n < 3$ | `NONE` (`INSUFFICIENT_SAMPLE`) | `NONE` |
| $3 \le n < 5$ | `LOW` | `NONE` |
| $5 \le n < 10$ | `MEDIUM` | `LOW` |
| $n \ge 10$ | `HIGH` | `MEDIUM` |

---

## 5. Cohort Separation & Strict Semantic Guardrails

1. **Format Cohorts**: Unlike content is never blindly compared. Instagram Reels are compared against Instagram Reels; Facebook Photos against Facebook Photos.
2. **Reach Safety**: `REACH` remains strictly **NON_AGGREGATABLE** across unique multi-day audiences. Daily reaches are never summed into weekly or monthly reach baselines.
3. **Follower Semantics**:
   - `FOLLOWERS_TOTAL`: Handled strictly as a **gauge** (latest observation). It is never summed.
   - `FOLLOWERS_NET_CHANGE`: Handled as an additive **delta** across the period.
4. **Timezone Awareness**:
   - Posting-time intelligence strictly utilizes `client.timezone` (e.g. `America/New_York`, `America/Bogota`).
   - Time buckets: `morning` (06:00–11:59), `afternoon` (12:00–17:59), `evening` (18:00–21:59), `late_night` (22:00–05:59).
   - Time windows require $n \ge 3$ within the bucket and $\ge 5$ total posts before recommendations are surfaced.
5. **Instagram PARTIAL Mode Guard & Metric Integrity**:
   - Client #3 Instagram operates with basic media counters.
   - Authoritative supported metrics: `FOLLOWERS_TOTAL`, `REACTIONS`, `COMMENTS`.
   - Unavailable unless future snapshots explicitly exist: `SHARES`, `SAVES`, `REACH`, `VIDEO_VIEWS`, `ENGAGEMENT_TOTAL`.
   - **Canonical ENGAGEMENT_TOTAL Policy**: Canonical `ENGAGEMENT_TOTAL` strictly requires all three core components: `REACTIONS`, `COMMENTS`, and `SHARES`.
   - **Unavailable vs. Zero Distinction**:
     - An explicit observation of `SHARES = 0` is valid numerical data.
     - A missing or unsupported `SHARES` metric is `UNAVAILABLE`.
     - The system never treats missing `SHARES` as zero and never silently derives partial engagement totals.
     - Consequently, for Instagram PARTIAL mode, `ENGAGEMENT_TOTAL` is strictly `UNAVAILABLE`.
   - Signals for `REACH`, `SAVES`, `SHARES`, `VIDEO_VIEWS`, and `ENGAGEMENT_TOTAL` are suppressed on Instagram PARTIAL mode, emitting a `PROVIDER_PARTIAL` operational health signal or `METRIC_UNAVAILABLE` with explicit component reasons.
6. **Bop-Authored vs External Organic**:
   - Posts are tagged with `is_bop_authored` and `source_label` ("Published by Bop Social" vs "Organic / External").

---

## 6. Deterministic Explanation Templates (No Generative AI)

Textual summaries are produced using parameterized deterministic templates:

- **Post Outperformance**:
  > *"This post generated 45 Reactions, which is +114.3% above the recent median (21.0) of 14 comparable image posts on Facebook over the last 30 days."*
- **Winning Format**:
  > *"Reels content achieved a median of 42.0 Reactions, outperforming the overall platform median (29.5) by +42.4% across 8 posts."*
- **Posting Time**:
  > *"Posts published during the evening window (America/New_York) achieved a median of 38.0 Reactions, performing +28.8% above the baseline median (29.5) based on 6 observations."*
- **Insufficient Sample**:
  > *"Insufficient comparable historical data for reel content on Instagram (sample size n=1, minimum required is 3). Baselines will activate once more content is published."*

---

## 7. Traceability & Idempotency

Every signal contains an explicit `signal_identity` hash:
$$\text{SHA256}(\text{client\_id} : \text{platform} : \text{signal\_type} : \text{metric} : \text{scope} : \text{object\_id} : \text{period\_start} : \text{period\_end} : \text{cohort\_hash})$$

Repeated generation updates records in-place without duplicating database rows.
Every persisted signal stores comprehensive structured `evidence`:
- Observed value
- Baseline value & method (`median`, `prior_window`)
- Exact relative delta
- Sample size ($n$)
- Cohort definition
- Source snapshot/rollup IDs
- Freshness state

---

## 8. API Specifications

1. `GET /api/analytics/insights/`
   - Parameters: `client_id`, `platform`, `date_from`, `date_to`, `signal_type`, `severity`, `confidence`, `is_actionable`.
   - Tenant-isolated. Returns ranked list of signals.
2. `GET /api/analytics/executive-summary/`
   - Parameters: `client_id`, `platform`, `date_from`, `date_to`.
   - Returns structured executive KPI drivers: `best_performing_content`, `weakest_performing_content`, `engagement_direction`, `follower_direction`, `winning_formats`, `posting_time_insights`, `platform_health`, and `data_quality`.
3. `GET /api/analytics/insights/history/`
   - Parameters: `client_id`, `platform`, `signal_type`, `severity`.
   - Historical review of persisted `BusinessSignal` records.

---

## 9. Future AI Boundary

Future phases (BS-5+) that introduce LLM-based narrative generation or automated PDF reports must consume the machine-readable fields of `BusinessSignal` (`observed_value`, `baseline_value`, `relative_delta`, `confidence_level`, `evidence`) as immutable truth inputs. The LLM must not invent metrics, re-estimate baselines, or alter confidence tiers.

---

## 10. Operational Rollback Procedure (BS-INFRA-1 Compliant)

Container file-copy hacks (`docker cp`) are strictly prohibited under the BS-INFRA-1 local runtime isolation model. Code updates and rollbacks must follow the canonical Git + Bop Social runtime procedure:

```powershell
# 1. Rollback database migrations if schema changes are to be reverted
docker compose exec backend python manage.py migrate social_stats <target_migration>

# 2. Checkout target known-good commit or branch
git checkout <known-good-ref>

# 3. Canonical stack startup and rebuild via Bop-owned runner
.\scripts\start-bopsocial.ps1
```

If a clean container rebuild is required without touching persistent database volumes:
```powershell
.\scripts\stop-bopsocial.ps1 -Down
.\scripts\start-bopsocial.ps1
```
This guarantees image immutability (`bopsocial-backend:local`, `bopsocial-frontend:local`) and prevents runtime drift.
