# Bop Social — Phase BS-4E
## Analytics Dashboard & Executive Insights UI Architecture

### 1. Information Architecture

The Bop Social Analytics Dashboard is organized into a single unified workspace (`AnalyticsWorkspace`) structured across five executive sections:

1. **Overview**: Executive KPI summary cards presenting candidate metrics (`FOLLOWERS_TOTAL`, `FOLLOWERS_NET_CHANGE`, `ENGAGEMENT_TOTAL`, `REACTIONS`, `COMMENTS`, `SHARES`, `PROFILE_VIEWS`, `VIDEO_VIEWS`, `REACH`). Metrics explicitly indicate capability availability.
2. **Trends**: Chronological timeseries visualization via Recharts with interactive metric selector, gauge tracking for followers (non-cumulative), and audience overlap protection for Reach.
3. **Content Performance**: Strict deduplication by unique content object identity (`platform, object_id`), source attribution (`Published by Bop Social` vs `Organic / External`), media format identification, caption excerpts, and post-level metrics.
4. **Platform Breakdown**: Side-by-side comparative inspection of Facebook Page (`Full Analytics`) versus Instagram Professional (`Partial Analytics`), outlining supported versus degraded capabilities.
5. **Data Health & Freshness**: Telemetry health panel displaying platform synchronization recency, data age, and Meta permission guidance for missing advanced insights.

---

### 2. Metric Availability & Semantic Integrity

The frontend consumes normalized read APIs backed by `SocialMetricRollup` and `SocialMetricSnapshot`. Raw provider responses are never directly parsed or displayed.

#### A. Standard Candidate KPIs
- `FOLLOWERS_TOTAL`: Gauge observation (latest value at snapshot time; never summed).
- `FOLLOWERS_NET_CHANGE`: Net follower change across period.
- `ENGAGEMENT_TOTAL`: Sum of all interactions.
- `REACTIONS`: Sum of likes/reactions.
- `COMMENTS`: Sum of comment counts.
- `SHARES`: Sum of shares (Facebook only under current scopes).
- `PROFILE_VIEWS`: Observed profile visits.
- `VIDEO_VIEWS`: Video views / Reel plays.
- `REACH`: Single-day unique audience.

#### B. Unsupported & Missing Metrics Handling
- Unsupported metrics **never appear as `0`**.
- An explicit `Unavailable` UI badge is rendered with informative helper text detailing the technical cause (e.g. `Not available with current Instagram permissions` or `No observations in selected window`).

---

### 3. Instagram Partial Mode UX

For connections lacking `instagram_manage_insights` (such as Client #3):
- **Available Metrics**: `FOLLOWERS_TOTAL`, `REACTIONS`, `COMMENTS`.
- **Unavailable Advanced Metrics**: `REACH`, `IMPRESSIONS`, `SAVES`, `PROFILE_VIEWS`, `VIDEO_VIEWS`, `SHARES`.
- **UX Treatment**:
  - Displays persistent banner: `Instagram Partial Mode: Basic media counters are active. Advanced metrics require instagram_manage_insights permissions.`
  - Badged with `Partial Analytics` (amber indicator).
  - Advanced metrics render with `Unavailable` state and permission guidance notes.
  - Zero raw tokens, secret keys, or OAuth URLs are exposed to the user.

---

### 4. REACH Aggregation Safety

Reach represents unique individuals exposed to content within a specific measurement window.

- **Daily Bucket**: Valid single-day observations are displayed.
- **Weekly & Monthly Aggregated Periods**:
  - Because unique daily audiences overlap, summing reach across days yields artificially inflated, statistically invalid figures.
  - Weekly and monthly Reach rollups are stored with `is_available = False` and `reason = "audience_overlap_non_summable"`.
  - The UI explicitly renders `Unavailable for aggregated period` with tooltip:
    > "Unique daily audiences cannot be safely summed across days. Switch bucket to 'Day' to view daily reach."

---

### 5. Content Performance & Top-Post Deduplication

#### A. Semantic Correction & Identity
In Phase BS-4D.1, candidate counts reflected multi-metric and multi-period rollup rows (87 Bop rollups + 192 organic rollups = 279 total rows).
In Phase BS-4E, the read layer strictly deduplicates observations by unique content identity `(platform, object_id)`:
- Exactly **one ranked entity** per unique provider content object.
- Client #3 contains exactly **38 unique posts** (12 Bop-authored + 26 Organic feed posts).

#### B. Content Labeling
- **Bop-Authored Posts**: Labeled `Published by Bop Social` (indigo accent) with prospective linkage to `UnifiedPost.id` and `PlatformPublishLog`.
- **External Provider Posts**: Labeled `Organic / External` (slate accent), preventing any misleading implication that Bop Social generated external content.

#### C. Post Metadata & Preview
- Caption preview extracted from `PostMetric.caption` or `UnifiedPost.content`.
- Media format classified as `image`, `video`, `carousel`, `reel`, `story`, or `post`.
- External permalink icon opens post on platform in new tab where available.
- Signed, private, or expiring CDN URLs are strictly withheld.

---

### 6. API Read Layer Contracts

#### `GET /api/analytics/summary/`
- **Query Params**: `client_id` (required), `platform` (`all`, `facebook`, `instagram`), `period` (`day`, `week`, `month`), `start_date`, `end_date`, `metric`.
- **Response**:
  - `client_id`: integer
  - `platform`: string
  - `period`: string
  - `date_range`: `{ start, end }`
  - `capabilities`: map of platform capability objects (`status`: `FULL` | `PARTIAL`, `notes`, `permission_guidance`)
  - `metrics`: dictionary of metric objects (`is_available`, `value`, `unavailable_reason`, `comparability_warning`, `aggregation_behavior`)
  - `freshness`: platform freshness status
  - `data_health`: array of health summaries per platform

#### `GET /api/analytics/trends/`
- **Query Params**: `client_id` (required), `metric` (required), `platform`, `period`, `start_date`, `end_date`.
- **Response**:
  - `client_id`: integer
  - `metric`: string
  - `is_available`: boolean
  - `unavailable_reason`: optional string
  - `datapoints`: array of `{ period_start, metric_value, sample_count, is_available }`

#### `GET /api/analytics/top-posts/`
- **Query Params**: `client_id` (required), `platform`, `metric` (default `REACTIONS`), `limit` (1-50, default 10), `start_date`, `end_date`.
- **Response**:
  - `client_id`: integer
  - `count`: integer (count of unique ranked content objects)
  - `posts`: array of `{ object_id, platform, ranking_metric, ranking_value, is_bop_authored, source_label, unified_post_id, caption, permalink, media_type, published_at, metrics }`

---

### 7. Empty & Error States

- **Empty State**: When no rollup or snapshot data exists in the window, charts render a clean, themed placeholder card with guidance rather than crashing or rendering blank boxes.
- **Error State**: API failures render controlled error banners (`Failed to load analytics summary`). Stack traces, provider error payloads, and internal database details are never surfaced to the UI.
- **Loading State**: Pulse skeletons with layout dimensions matching final components to prevent layout shift.
