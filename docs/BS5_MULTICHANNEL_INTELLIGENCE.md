# BS-5 Multichannel Intelligence

## BS-5A — Metric Compatibility & Comparison Model

### 1. Overview & Architectural Principle
Cross-platform social media intelligence cannot assume that identical metric names share identical business or mathematical meanings across providers.

**The Golden Rule of Cross-Platform Analytics:**
$$\text{Same Metric Name} \neq \text{Same Business Meaning}$$

Comparison is permitted **only** when metric semantics are explicitly registered as compatible in the deterministic comparison registry. The compatibility layer — never an LLM — is authoritative. Calculations are performed strictly by pure deterministic functions over normalized analytics telemetry.

---

### 2. Goals & Non-Goals

#### Goals
- Establish an immutable, machine-readable metric compatibility registry (`MetricComparisonRule`) across social platforms (Facebook ↔ Instagram in v1).
- Provide deterministic pure comparison functions calculating absolute deltas, safe relative deltas, and direction-aware winner determinations.
- Distinguish strictly between observed source-backed zero values and missing/unavailable data.
- Guarantee reach non-summation invariants across calendar dates.
- Enforce metric-level capability gating under degraded provider modes (e.g. Instagram Basic mode).
- Provide typed, machine-readable evidence payloads with bilingual (ES/EN) human reason labels.
- Guarantee strict tenant isolation and zero database writes.

#### Non-Goals
- No cross-platform recommendation engine (deferred to future BS-5 phases).
- No multichannel `BusinessSignal` persistence or database schema migrations in BS-5A.
- No modifications to `ExecutiveReport` or `ExecutiveNarrative`.
- No live external API calls to providers (Meta, Ollama, OpenAI, etc.).
- No arbitrary mathematical approximations or generic engagement rates without explicit denominators.

---

### 3. Semantic Taxonomies

#### A. Comparison Compatibility (`ComparisonCompatibility`)
| State | Semantics |
| :--- | :--- |
| `DIRECT` | Identical business concept and homogeneous measurement semantics across platforms. |
| `NORMALIZED` | Comparable only after a documented normalization or mathematical transformation. |
| `CONDITIONAL` | Comparable only if runtime prerequisites are satisfied (e.g. period unique reach, provider capability). |
| `NON_COMPARABLE` | Fundamental semantic discrepancy prevents cross-platform ranking. Direct competition disallowed. |
| `UNAVAILABLE` | Required source data is missing, unqueried, or unsupported for one or both platforms. |

#### B. Comparison Direction (`ComparisonDirection`)
| Direction | Meaning | Winner Determination |
| :--- | :--- | :--- |
| `HIGHER_IS_BETTER` | Greater value indicates superior competitive performance. | Platform with highest normalized value. |
| `LOWER_IS_BETTER` | Lower value indicates superior performance (e.g. costs, churn). | Platform with lowest normalized value. |
| `NEUTRAL` | Informational or volume gauge; greater value does **not** imply performance superiority (e.g. `FOLLOWERS_TOTAL`). | Strictly `NO_WINNER`. |
| `NOT_APPLICABLE` | Metric cannot or must not be ranked competitively. | Strictly `NO_WINNER` or `UNAVAILABLE`. |

#### C. Normalization Taxonomy (`NormalizationType`)
| Type | Description |
| :--- | :--- |
| `NONE` | Raw values compared directly without transformation. |
| `PER_POST` | Scaled per published post in the period. |
| `PER_1000_FOLLOWERS` | Scaled per 1,000 active followers. |
| `PER_IMPRESSION` | Scaled per total screen impressions. |
| `PER_REACH` | Scaled per unique reached audience. |
| `RATE` | Normalized mathematical ratio or proportion. |
| `LATEST_VALUE` | Point-in-time gauge snapshot. |
| `DELTA` | Net shift over aligned calendar period. |
| `DAILY_AVERAGE` | Period total divided by active days. |

---

### 4. Semantic Rules & Safety Invariants

#### A. Missing vs Zero
- **Observed Zero (`0.0000`)**: A valid observation explicitly reported by the provider (e.g. 0 comments). It is preserved as a valid numerical zero and participates in deltas and rankings.
- **Unavailable (`None`)**: Data is absent, unqueried, or unsupported by permissions. It **never** becomes a fake zero. Comparisons involving unavailable data immediately evaluate to status `UNAVAILABLE` and winner `UNAVAILABLE`.

#### B. Safe Relative Delta & Zero Baseline
Relative change is calculated as:
$$\Delta_{\text{rel}} = \frac{\text{val}_a - \text{val}_b}{|\text{val}_b|} \times 100\%$$
- If baseline $\text{val}_b = 0$, division by zero is strictly avoided:
  $$\Delta_{\text{rel}} = \text{None}, \quad \text{reason\_code} = \text{ZERO\_BASELINE}$$

#### C. Reach Invariants
- `REACH` represents unique accounts and is **strictly non-aggregatable** across daily periods.
- Cross-platform comparison of `REACH` is rejected if daily reach is arithmetically summed over a multi-day range (`NON_AGGREGATABLE_SUMMATION_REJECTED`).
- `AVERAGE_DAILY_REACH` is a distinct metric identity. It may only be compared against another `AVERAGE_DAILY_REACH`, never relabeled as total period reach.

#### D. Engagement Total Components
- Canonical `ENGAGEMENT_TOTAL` requires all three core components:
  $$\text{ENGAGEMENT\_TOTAL} = \text{REACTIONS} + \text{COMMENTS} + \text{SHARES}$$
- If any required component is missing or unavailable (e.g. Instagram in Partial Mode lacking `SHARES`), `ENGAGEMENT_TOTAL` comparison status evaluates to `UNAVAILABLE` with reason `COMPONENT_UNAVAILABLE`. Partial sums are strictly forbidden.

#### E. Metric-Level Capability Gating
- Capability gating is evaluated per metric, not by blanket rejection of the platform.
- When Instagram operates in degraded `PARTIAL` mode (missing `instagram_manage_insights`), unsupported metrics (`SHARES`, `SAVES`, `REACH`, `VIDEO_VIEWS`) return `PROVIDER_PARTIAL`.
- Supported metrics (`COMMENTS`, `REACTIONS`, `FOLLOWERS_TOTAL`) continue to evaluate successfully.

---

### 5. Facebook ↔ Instagram Compatibility Matrix

The authoritative registry governs all 15 canonical analytics metrics:

| Metric | Compatibility | Normalization | Direction | Rankable | Requirements / Semantic Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `REACH` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | True | Period-level unique reach only. Arithmetic summation across daily dates is strictly rejected. |
| `AVERAGE_DAILY_REACH` | `DIRECT` | `DAILY_AVERAGE` | `HIGHER_IS_BETTER` | True | Average daily unique reach. Compared only against same identity; never relabeled as total reach. |
| `IMPRESSIONS` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | True | Full on FB; IG Graph API v18+ deprecated media impressions. Conditional on source availability. |
| `FOLLOWERS_TOTAL` | `DIRECT` | `LATEST_VALUE` | `NEUTRAL` | False | Audience volume gauge. Neutral direction; winner is always `NO_WINNER` (volume $\neq$ performance). |
| `FOLLOWERS_NET_CHANGE` | `DIRECT` | `DELTA` | `HIGHER_IS_BETTER` | True | Net follower shift (gains minus losses) over aligned period. |
| `PROFILE_VIEWS` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | False | Discrepancy: FB measures logged-in Page views; IG measures profile visits. Informational only. |
| `CLICKS_TOTAL` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | False | Discrepancy: FB measures post/link/photo clicks; IG feed posts only support bio clicks. |
| `ENGAGEMENT_TOTAL` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | True | Requires complete components: REACTIONS + COMMENTS + SHARES. Partial composition disallowed. |
| `REACTIONS` | `DIRECT` | `NONE` | `HIGHER_IS_BETTER` | True | Direct count of user likes / positive reactions. |
| `COMMENTS` | `DIRECT` | `NONE` | `HIGHER_IS_BETTER` | True | Direct count of comments and replies. |
| `SHARES` | `CONDITIONAL` | `NONE` | `HIGHER_IS_BETTER` | True | Direct redistribution count. Conditional on Instagram professional insight permissions. |
| `SAVES` | `NON_COMPARABLE` | `NONE` | `NOT_APPLICABLE` | False | Standard on Instagram; organic Facebook posts do not expose a public saves metric. |
| `VIDEO_VIEWS` | `NON_COMPARABLE` | `NONE` | `NOT_APPLICABLE` | False | FB measures 3-second views; IG measures Reel plays/loops. Discrepant thresholds prevent raw ranking. |
| `VIDEO_WATCH_TIME` | `DIRECT` | `NONE` | `HIGHER_IS_BETTER` | True | Cumulative elapsed viewing duration normalized to seconds. |
| `VIDEO_AVG_WATCH_TIME` | `DIRECT` | `DAILY_AVERAGE` | `HIGHER_IS_BETTER` | True | Mean viewing duration per session in seconds. Must be averaged, never summed. |

---

### 6. Comparison Result Model & Reason Codes

#### Dataclass Schema (`ComparisonResult`)
- `metric`: Canonical metric key.
- `platform_a`, `platform_b`: Platform pair identifiers.
- `status`: `AVAILABLE`, `UNAVAILABLE`, or `INVALID`.
- `compatibility`: `DIRECT`, `NORMALIZED`, `CONDITIONAL`, `NON_COMPARABLE`, `UNAVAILABLE`.
- `direction`: `HIGHER_IS_BETTER`, `LOWER_IS_BETTER`, `NEUTRAL`, `NOT_APPLICABLE`.
- `normalization`: `NormalizationType`.
- `rankable`: Boolean indicating if performance ranking is semantically permissible.
- `value_a`, `value_b`: Raw extracted/observed values.
- `normalized_value_a`, `normalized_value_b`: Values after normalization.
- `delta_absolute`: $\text{val}_a - \text{val}_b$.
- `delta_relative`: Percentage delta relative to baseline platform B, or `None`.
- `winner`: `PLATFORM_A`, `PLATFORM_B`, `TIE`, `NO_WINNER`, `UNAVAILABLE`.
- `period_start`, `period_end`: ISO date bounds of aligned period.
- `sample_a`, `sample_b`: Number of underlying observations.
- `reason_code`: Machine-readable reason code (`ComparisonReasonCode`).
- `reason_labels`: Bilingual dictionary `{"es": "...", "en": "..."}`.
- `evidence`: Machine-readable evidence payload without secrets or LLM hallucinations.
- `metadata`: Additional diagnostic context.

#### Reason Codes (`ComparisonReasonCode`)
- `DIRECTLY_COMPARABLE`: Metrics are directly comparable with identical measurement semantics.
- `NORMALIZATION_REQUIRED`: Comparison valid only after required dimensional normalization.
- `SOURCE_UNAVAILABLE`: Source data unavailable or no observations in selected period.
- `PROVIDER_PARTIAL`: Comparison unavailable due to partial provider coverage on platform.
- `METRIC_NOT_EQUIVALENT`: Fundamental semantic discrepancy between platforms; direct ranking disallowed.
- `PERIOD_MISMATCH`: Mismatch in comparison date range, granularity, or timezone boundaries.
- `DENOMINATOR_UNAVAILABLE`: Required denominator for normalization is unavailable.
- `ZERO_BASELINE`: Baseline is zero; relative delta omitted to prevent division by zero.
- `INSUFFICIENT_SAMPLE`: Insufficient sample size to issue a statistically valid comparison.
- `NON_RANKABLE_METRIC`: Volume or audience size metric; does not rank competitive performance.
- `UNSUPPORTED_METRIC`: Metric identifier unknown or unmapped in canonical registry.
- `UNSUPPORTED_PLATFORM`: Platform unsupported for multichannel comparisons in this version.
- `TENANT_MISMATCH`: Differing client entities or unauthorized cross-tenant access.
- `COMPONENT_UNAVAILABLE`: One or more required sub-components for derived metric are unavailable.
- `NON_AGGREGATABLE_SUMMATION_REJECTED`: Arithmetic sum rejected: unique reach metric is non-aggregatable across days.

---

### 7. Future Platform Extension Model
Adding future platforms (e.g. LinkedIn, TikTok, YouTube, Threads, X) follows a strict three-step protocol:
1. **Audit Provider Semantics**: Inspect API specifications, view duration thresholds (e.g. TikTok 1s vs YouTube 30s vs Meta 3s), and unique reach aggregation constraints.
2. **Define Rules in Matrix**: Create `MetricComparisonRule` instances for each platform pair and canonical metric, specifying compatibility, normalization, direction, and rankability.
3. **Register in Master Registry**: Call `register_rule(rule)`. Symmetric pair lookup handles reciprocal ordering automatically (`get_metric_comparison_rule`).

No schema migrations or database writes are required to register new comparison rules.


---

## BS-5B — Cross-Platform Benchmark & Comparison Engine

### 1. Overview & Architectural Role
Phase BS-5B builds directly upon the BS-5A compatibility layer by orchestrating multi-metric cross-platform benchmark evaluations for a client across an aligned calendar window.
It serves as the deterministic source-of-truth engine that future BS-5 phases (such as BS-5C Multichannel Business Signals) will consume.

**Fundamental Invariant:**
$$\text{BS-5B executes BS-5A pure comparison rules} \quad \wedge \quad \text{No N+1 queries} \quad \wedge \quad \text{No overall winner}$$

---

### 2. Benchmark Domain Model & Schema

#### A. Schema Version
Canonical schema version constant:
`BENCHMARK_SCHEMA_VERSION = "bs5b-benchmark-v1"`

#### B. Domain Dataclasses
- `CoverageSummary`: Tallies `total_metrics`, `comparable_metrics`, `rankable_metrics`, `non_rankable_metrics`, `unavailable_metrics`, `non_comparable_metrics`, and `invalid_metrics`.
- `WinnerSummary`: Tallies per-metric platform wins (`platform_a_wins`, `platform_b_wins`, `ties`, `no_winner`, `unavailable`).
- `MultichannelBenchmarkResult`: Complete benchmark envelope encapsulating client ID, platform pair, period, granularity, deterministic `benchmark_hash`, coverage summary, winner summary, canonical 15-metric results list, optional cohort evaluations, and machine evidence provenance.

---

### 3. Deterministic Identity Hash (`benchmark_hash`)

The benchmark identity hash is a deterministic SHA256 digest calculated strictly from canonical inputs without volatile runtime parameters:
- `schema_version`
- `client_id`
- `platform_a`, `platform_b` (normalized lowercase)
- `period_start`, `period_end` (ISO 8601 strings)
- `granularity`
- Canonical list of metric results sorted strictly by the 15-metric canonical order (`REACH` through `VIDEO_AVG_WATCH_TIME`). Each entry includes `metric`, `status`, `values`, `deltas`, `winner`, `reason_code`, and `sample counts`.

**Properties:**
1. **Idempotence**: Identical client, platforms, period, and telemetry yield the exact same hash.
2. **Provenance Tracking**: Modifying or backfilling any single underlying data observation alters the benchmark hash.
3. **Orientation Sensitivity**: Swapping platform orientation (`FB <-> IG` vs `IG <-> FB`) produces an orientation-specific identity while preserving semantic parity.

---

### 4. Source Resolution & Query Plan Optimization

To eliminate N+1 query loops across the 15 evaluated metrics, `build_multichannel_benchmark` implements a bounded bulk-loading query plan:
1. **Query 1 (Credentials)**: Bulk-loads `PlatformCredential` records for `[platform_a, platform_b]`.
2. **Query 2 (Rollups)**: Bulk-loads all `SocialMetricRollup` observations in the window `[start_date, end_date]`.
3. **Query 3 (Snapshots fallback)**: Bulk-loads `SocialMetricSnapshot` observations within the window.
4. **Query 4 (Cohorts optional)**: Queries published content cohorts if `include_cohorts=True`.

Total query count for the entire 15-metric benchmark evaluation is strictly bounded to $\le 4$ queries.

---

### 5. Semantic Enforcements & Safety Invariants

#### A. Reach Handling
- Multi-day `REACH` summation is strictly rejected: if only daily reach observations exist across multiple dates, the metric evaluates to status `UNAVAILABLE` with reason `NON_AGGREGATABLE_SUMMATION_REJECTED`.
- `AVERAGE_DAILY_REACH` evaluates daily average reach and is never relabeled as total reach.

#### B. Engagement Total Handling
- Requires complete canonical components: `REACTIONS`, `COMMENTS`, and `SHARES`.
- If Instagram operates in `PARTIAL` mode without `SHARES`, `ENGAGEMENT_TOTAL` evaluates to `UNAVAILABLE` with reason `COMPONENT_UNAVAILABLE`. Partial sums are strictly forbidden.

#### C. Followers Total (Audience Gauge)
- Follower count is evaluated as a point-in-time gauge (`LATEST_VALUE`).
- Direction is strictly `NEUTRAL` and `rankable=False`; winner is strictly `NO_WINNER` (volume does not imply competitive superiority).

#### D. The No-Overall-Platform-Winner Rule
BS-5B strictly forbids declaring an "overall platform winner" (e.g. "Facebook won overall" or "Instagram outperformed Facebook"). Because social media metrics exhibit fundamentally disparate scales, units, and aggregation semantics, aggregating heterogeneous metrics into a synthetic score is statistically invalid. BS-5B emits per-metric winners only.

---

### 6. Content Cohort Benchmarking (Format Analysis)
- Formats evaluated: `IMAGE`, `VIDEO`, `CAROUSEL`.
- Minimum sample size requirement: $n \ge 3$ posts per platform per format.
- Cohorts below threshold return status `UNAVAILABLE`, reason `INSUFFICIENT_SAMPLE`, and winner `NO_WINNER`.

---

### 7. REST API Layer

#### Endpoint
`GET /api/analytics/multichannel/benchmark/`

#### Query Parameters
- `client_id` (required, int): Validated against authenticated user's organization.
- `platform_a` (default `facebook`): First platform key.
- `platform_b` (default `instagram`): Second platform key.
- `start_date` (required, `YYYY-MM-DD`): Beginning of evaluation window.
- `end_date` (required, `YYYY-MM-DD`): End of evaluation window.
- `granularity` (default `day`): Granularity boundary (`day`, `week`, `month`, `period`).
- `metrics` (optional): Comma-separated list of canonical metrics. Defaults to all 15.
- `include_cohorts` (optional, bool): Whether to execute format cohort benchmarking.

#### Security & Tenant Isolation
- Protected by `AnalyticsBaseView` (requires JWT authentication).
- Validates tenant access via `validate_client`. Cross-tenant requests return `404 Not Found`.
- 100% read-only: performs 0 database writes and 0 provider calls.

---

### 8. Real Pilot Verification (Client #3 Bop Agencia)

Executed read-only benchmark for Client #3 (`Bop Agencia`) across window `2026-09-22` to `2026-10-22`:
- **Benchmark Hash**: `14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012`
- **Coverage Summary**:
  - `total_metrics`: 15
  - `comparable_metrics`: 3 (`FOLLOWERS_TOTAL`, `REACTIONS`, `COMMENTS`)
  - `rankable_metrics`: 2 (`REACTIONS`, `COMMENTS`)
  - `non_rankable_metrics`: 1 (`FOLLOWERS_TOTAL`)
  - `unavailable_metrics`: 10 (metrics unqueried or unpermitted on IG)
  - `non_comparable_metrics`: 2 (`SAVES`, `VIDEO_VIEWS`)
  - `invalid_metrics`: 0
- **Winner Summary**:
  - `platform_a_wins` (Facebook): 0
  - `platform_b_wins` (Instagram): 1 (`REACTIONS`: IG 6 vs FB 0)
  - `ties`: 1 (`COMMENTS`: FB 0 vs IG 0, reason `ZERO_BASELINE`)
  - `no_winner`: 3 (`FOLLOWERS_TOTAL`, `SAVES`, `VIDEO_VIEWS`)
  - `unavailable`: 10
- **Capability State**: Accurately respected Instagram Basic `PARTIAL` mode permissions.
- **Database Safety**: Initial vs post-execution table row counts remained 100% identical.


---

## BS-5C — Multichannel Business Signal Engine

### 1. Overview & Architectural Role
Phase BS-5C establishes a deterministic business signal generation engine that consumes the authoritative `MultichannelBenchmarkResult` from BS-5B and derives grounded, actionable, cross-platform business intelligence signals.

**Core Architectural Rule:**
$$\text{BS-5C consumes MultichannelBenchmarkResult} \quad \wedge \quad \text{Zero Metric Recalculation} \quad \wedge \quad \text{Zero Overall Platform Winner}$$

BS-5C does NOT recalculate underlying rollups, snapshots, winner determinations, or deltas. All signals bind strictly to an immutable `benchmark_hash` and canonical schema version `bs5b-benchmark-v1`.

---

### 2. Signal Taxonomy & Categories

BS-5C defines a canonical set of multichannel signal types extending the deterministic `BusinessSignal` model:

| Signal Type | Category | Default Severity | Confidence | Actionable | Description |
|---|---|---|---|---|---|
| `PLATFORM_METRIC_OUTPERFORMANCE` | `PERFORMANCE` | `POSITIVE` | `HIGH` / `MEDIUM` | True | Direct rankable metric where one platform demonstrates material superiority over another. |
| `CROSS_PLATFORM_TIE` | `PERFORMANCE` | `INFO` | `HIGH` | False | Non-zero tie where both platforms record identical positive interaction volumes. |
| `AUDIENCE_SIZE_DIFFERENCE` | `AUDIENCE` | `INFO` | `HIGH` | False | Point-in-time audience gauge difference (`FOLLOWERS_TOTAL`). Never declares an outperformance winner. |
| `CROSS_PLATFORM_DATA_LIMITATION` | `CAPABILITY` | `WARNING` / `INFO` | `HIGH` | True (if fixable) | Consolidated signal surfacing provider permission or telemetry limitations with coverage ratio. |
| `CROSS_PLATFORM_METRIC_NON_COMPARABLE` | `DATA_QUALITY` | `INFO` | `HIGH` | False | Consolidated informational signal identifying metrics with disparate platform semantics (`SAVES`, `VIDEO_VIEWS`). |
| `FORMAT_PLATFORM_ADVANTAGE` | `FORMAT` | `POSITIVE` | `HIGH` / `MEDIUM` | True | Content cohort format superiority verified with adequate sample size ($n \ge 3$ on both sides). |
| `INSUFFICIENT_CROSS_PLATFORM_SAMPLE` | `FORMAT` | `INFO` | `NONE` | True | Content cohort format comparison gated by inadequate sample ($n < 3$ on either platform). |

---

### 3. Materiality Thresholds & Zero-Baseline Handling

1. **Volume Materiality Threshold**:
   - For discrete volume metrics (`REACTIONS`, `COMMENTS`, `CLICKS_TOTAL`), absolute delta $\ge 1$ is required to generate an outperformance signal when the baseline platform is 0.
   - When baseline value $> 0$, relative delta $\ge 20\%$ or absolute delta $\ge 5$ is required.
2. **Zero-Baseline Integrity**:
   - When the baseline platform records 0 interactions (e.g. FB=0 vs IG=6), the mathematical relative percentage is undefined.
   - BS-5C strictly sets `relative_delta = None` and forbids inventing synthetic percentage claims (e.g. "Instagram performed 600% better"). Signals cite factual observed values and absolute deltas only.

---

### 4. Audience Volume & Noise Suppression Rules

1. **Followers Total (Audience Gauge)**:
   - `FOLLOWERS_TOTAL` is evaluated as an audience volume gauge (`rankable = False`, `direction = NEUTRAL`).
   - Generates `AUDIENCE_SIZE_DIFFERENCE`. It NEVER emits an outperformance winner or competitive superiority claim.
2. **Zero-Zero Tie Suppression**:
   - When both platforms record 0 interactions on a metric (e.g. `COMMENTS` FB=0 vs IG=0), the comparison yields zero actionable business intelligence.
   - BS-5C automatically suppresses zero-zero ties from candidate signals to prevent signal spam. Suppressed observations are recorded in diagnostic metadata with reason `LOW_INFORMATION_ZERO_TIE`.

---

### 5. Consolidation Architecture

Rather than generating 10 duplicate signals for unavailable metrics or individual signals for non-comparable metrics, BS-5C consolidates them intelligently:

1. **Consolidated Data Limitation Signal (`CROSS_PLATFORM_DATA_LIMITATION`)**:
   - Gathers all metrics with status `UNAVAILABLE`.
   - Groups affected metrics by root cause: `PROVIDER_PARTIAL`, `COMPONENT_UNAVAILABLE`, `SOURCE_UNAVAILABLE`.
   - Computes deterministic coverage ratio (e.g. $3 / 15$).
   - Flags `is_actionable = True` if the limitation stems from fixable provider permissions (e.g. Instagram Basic missing insights permissions).
2. **Consolidated Non-Comparable Signal (`CROSS_PLATFORM_METRIC_NON_COMPARABLE`)**:
   - Gathers all metrics with compatibility `NON_COMPARABLE` (`SAVES`, `VIDEO_VIEWS`).
   - Surfaces semantic disparity as a single informational note without performance claims.

---

### 6. Format Cohort Advantage & Sample Gating

1. **Minimum Sample Size Requirement**:
   - Validating format cohorts requires $n \ge 3$ published posts on BOTH platforms within the period.
2. **Gating Enforcement**:
   - If $n < 3$ on either platform: emits `INSUFFICIENT_CROSS_PLATFORM_SAMPLE` with `confidence_level = "NONE"` and recommended action `CONTINUE_COLLECTING_DATA`. No winner is declared.
   - If $n \ge 3$ on both platforms and a material difference exists: emits `FORMAT_PLATFORM_ADVANTAGE` with `is_actionable = True`.

---

### 7. Deterministic Confidence & Actionability Framework

Confidence and actionability are derived purely from source evidence without heuristics or LLMs:

- **Confidence Tiers**:
  - `HIGH`: Direct metrics with full source telemetry, verified limitations, or sample sizes $n \ge 10$.
  - `MEDIUM`: Conditional metrics with runtime prerequisites satisfied or sample sizes $3 \le n < 10$.
  - `LOW`: Limited observation sample or narrow evidence window.
  - `NONE`: Inadequate cohort sample ($n < 3$) or structurally non-comparable claims.
- **Actionability Rules**:
  - Outperformance signals: `True` (review and allocate budget / focus).
  - Audience size difference: `False` (informational gauge).
  - Provider data limitation: `True` if permissions can be upgraded, else `False`.
  - Non-comparable metrics: `False`.
  - Insufficient sample: `True` in the operational sense of continuing data collection.

---

### 8. Stable SHA256 Signal Identity & Deduplication

Signals compute a deterministic 64-character SHA256 digest:

$$\text{signal\_identity} = \text{SHA256}(\text{client\_id} : \text{signal\_type} : \text{benchmark\_hash} : \text{metric} : \text{platform\_a} : \text{platform\_b} : \text{cohort\_key})$$

**Properties:**
1. Zero timestamps or volatile counters in key derivation.
2. Guaranteed idempotency: repeated execution against the same benchmark creates 0 duplicate rows (`update_or_create`).
3. Benchmark Binding: if the underlying telemetry or benchmark period changes, `benchmark_hash` shifts, generating fresh distinct signal identities and marking former signals stale.

---

### 9. The No-Overall-Platform-Winner Invariant

BS-5C strictly forbids declaring an overall platform winner or aggregating disparate metric victories into a composite platform score:
- Signal candidates with types matching `OVERALL_PLATFORM_WINNER`, `CROSS_PLATFORM_OVERALL_WINNER`, or containing `OVERALL` fail closed at Gate 2 of the deterministic validator.
- Comparisons evaluate specific metric dimensions only.

---

### 10. Bilingual Natural-Language Templates

Signal explanations are generated via deterministic parameterized templates without generative AI or external LLM APIs:
- **Spanish (`es`)**:
  - *"Instagram registró 6 reacciones frente a 0 en Facebook durante el período."*
  - *"Instagram cuenta con 50 seguidores frente a 20 en Facebook (métrica de volumen de audiencia, no de rendimiento)."*
  - *"Limitación de datos entre plataformas: 10 de 15 métricas no están disponibles debido a capacidades parciales del proveedor (Instagram)."*
- **English (`en`)**:
  - *"Instagram recorded 6 reactions compared with 0 on Facebook during the period."*
  - *"Instagram has 50 followers compared with 20 on Facebook (audience volume metric, not performance)."*
  - *"Cross-platform data limitation: 10 of 15 metrics unavailable due to partial provider capabilities (Instagram)."*

---

### 11. REST API Layer

#### Endpoints
1. `GET` / `POST /api/analytics/multichannel/signals/preview/`
   - Read-only preview endpoint.
   - Consumes or builds benchmark, validates evidence, generates signal candidates.
   - Guaranteed 100% read-only: performs 0 database writes and 0 provider calls.
2. `POST /api/analytics/multichannel/signals/`
   - Protected persistence endpoint.
   - Fails closed with `403 Forbidden` unless operator authorization `allow_persistence=true` is explicitly provided.
   - Real pilot persistence is strictly disabled in this phase.

#### Tenant Security
- Enforces strict tenant isolation via `validate_client`. Cross-tenant requests return `404 Not Found`.

---

### 12. Real Pilot Verification (Client #3 Bop Agencia)

Executed read-only signal preview against verified pilot benchmark `14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012`:

- **Target Tenant**: Client #3 (`Bop Agencia`)
- **Pair & Window**: Facebook vs Instagram (`2026-09-22` to `2026-10-22`, granularity `period`)
- **Candidate Signal Count**: 4
  1. `FOLLOWERS_TOTAL`: `AUDIENCE_SIZE_DIFFERENCE` (FB=20, IG=50, non-rankable, `is_actionable=False`, confidence `HIGH`)
  2. `REACTIONS`: `PLATFORM_METRIC_OUTPERFORMANCE` (winner=Instagram, IG=6 vs FB=0, `zero_baseline=True`, `is_actionable=True`, confidence `HIGH`, action `REVIEW_PLATFORM_PERFORMANCE`)
  3. Consolidated Limitations: `CROSS_PLATFORM_DATA_LIMITATION` (10 unavailable metrics, coverage ratio `3/15`, provider `Instagram`, `is_actionable=True`, action `REVIEW_PROVIDER_PERMISSIONS`)
  4. Consolidated Non-Comparable: `CROSS_PLATFORM_METRIC_NON_COMPARABLE` (`SAVES`, `VIDEO_VIEWS`, `is_actionable=False`, confidence `HIGH`)
- **Suppressed Candidates**: 1
  - `COMMENTS`: Suppressed under low-information rule (FB=0 vs IG=0 tie).
- **Database Safety**:
  - `BusinessSignal` rows before preview: 5
  - `BusinessSignal` rows after preview: 5 (0 rows persisted)
