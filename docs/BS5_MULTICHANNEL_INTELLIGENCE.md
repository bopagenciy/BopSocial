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


---

## BS-5D — Multichannel Executive Intelligence & Cross-Platform Narrative Integration

### 1. Overview & Architectural Role
Phase BS-5D completes the analytical pipeline by allowing client-facing `ExecutiveReport` structures and Grounded AI Executive Narrative engines to safely consume cross-platform business signals (IDs 6–9) and benchmark evidence (`14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012`) without weakening deterministic safeguards established in BS-4H, BS-5A, BS-5B, and BS-5C.

**Core Principles:**
$$\text{Executive Reporting} \leftarrow \text{Authoritative Benchmark} + \text{Multichannel Signals} \quad \wedge \quad \text{Zero Hallucination} \quad \wedge \quad \text{Strict Non-Performance Rules}$$

---

### 2. Multichannel Executive Reporting Schema (`bs5d-multichannel-executive-v1`)

The executive report data payload incorporates a dedicated `multichannel_intelligence` section governed by schema `bs5d-multichannel-executive-v1`:

1. **Benchmark Binding**:
   - Strictly binds to verified `benchmark_hash` (`14bb7652...`).
   - Evaluates signal freshness against current benchmark window; stale signals from divergent periods are filtered.
2. **Coverage Summary**:
   - `total_metrics`: 15
   - `comparable_metrics`: 3 (`FOLLOWERS_TOTAL`, `REACTIONS`, `COMMENTS`)
   - `status`: `LIMITED` (highlighted when coverage ratio < 50%)
   - Explicit warning citing partial provider capability mode (`Instagram`).
3. **Platform Comparisons (Strict Non-Performance & Non-Summation Rules)**:
   - `FOLLOWERS_TOTAL`: Evaluated as audience volume gauge only (FB=20.0, IG=50.0). Winner is strictly `NO_WINNER` and `is_rankable = False`. Volume difference is never described as performance superiority.
   - `REACTIONS`: Direct outperformance (FB=0.0, IG=6.0, delta=-6.0). Because baseline platform is 0, `relative_delta = None` (zero baseline). Fabricating fake percentages (e.g. "+600%") is mathematically and semantically forbidden.
   - `COMMENTS`: Non-actionable tie (FB=0.0, IG=0.0, delta=0.0, winner=`TIE`).
4. **Non-Comparable Metrics & Disparity Callouts**:
   - `SAVES` and `VIDEO_VIEWS` are registered as structural semantic limitations (`METRIC_NOT_EQUIVALENT`), never relabeled as ties, zeros, or competitive losses.
5. **The No-Overall-Platform-Winner Invariant**:
   - `overall_winner` is strictly `None`.
   - Governance disclaimer explicitly declares that Bop Social evaluates individual metric dimensions only and refuses to manufacture synthetic cross-metric platform scores.

---

### 3. Deterministic Executive Takeaways Engine

Multichannel takeaways are ordered deterministically to ensure critical data caveats precede operational insights:

1. **`DATA_COVERAGE_WARNING`** (Severity: `WARNING`, Action: `REVIEW_PROVIDER_PERMISSIONS`, Ref: `MC-SIG-8`):
   - Informs stakeholders of partial capability mode and 12/15 unavailable metrics.
2. **`METRIC_ADVANTAGE`** (Severity: `POSITIVE`, Action: `REVIEW_PLATFORM_PERFORMANCE`, Ref: `MC-SIG-7`):
   - Highlights factual outperformance in directly comparable interactions (Instagram 6 reactions vs Facebook 0).
3. **`AUDIENCE_CONTEXT`** (Severity: `INFO`, Action: `None`, Ref: `MC-SIG-6`):
   - Clarifies audience volume difference (Instagram 50 vs Facebook 20) without performance superiority claims.
4. **`SEMANTIC_COMPARISON_LIMITATION`** (Severity: `INFO`, Action: `CONTINUE_COLLECTING_DATA`, Ref: `MC-SIG-9`):
   - Details measurement discrepancies for `SAVES` and `VIDEO_VIEWS`.

---

### 4. Grounded AI Narrative Context Integration (`bs4h-context-v2`)

1. **Context Schema Increment**:
   - Schema version incremented to `bs4h-context-v2`.
   - Embeds structured `multichannel_intelligence` envelope into grounded context.
2. **Stable Evidence References (`MC-SIG-*`)**:
   - Multichannel signals receive deterministic evidence registry keys: `MC-SIG-6`, `MC-SIG-7`, `MC-SIG-8`, `MC-SIG-9`.
   - Guarantees bidirectional resolution between narrative citations and machine-readable evidence payloads.
3. **Context Hash & Source Hash Determinism**:
   - `compute_context_hash` and `compute_source_hash` incorporate multichannel evidence and `benchmark_hash`.
   - Modifying any cross-platform observation or benchmark shifts hashes predictably.

---

### 5. Multichannel Narrative Validator Gates

`NarrativeValidator` enforces four strict deterministic locks:

1. **Overall-Winner Lock**:
   - Rejects phrases like *"plataforma ganadora"*, *"ganador general"*, *"overall winner"*, or *"best platform"*.
2. **Comparability Lock**:
   - Rejects competitive performance claims on structurally non-comparable metrics (`SAVES`, `VIDEO_VIEWS`).
3. **Zero-Baseline Lock**:
   - Rejects percentage variation claims on zero baseline interactions.
4. **Metric Lock**:
   - Rejects claims evaluating unavailable cross-platform metrics (`ENGAGEMENT_TOTAL`, `REACH`).
5. **Evidence Grounding**:
   - Ensures all `MC-SIG-*` evidence citations in recommendations resolve against the verified evidence registry.

---

### 6. Verification & Invariant Proof

- **Backend Test Suite**: 1,003 tests passing (100% OK in 97.2s).
- **Targeted BS-5 Suites**: 76 tests passing (BS-5A: 19, BS-5B: 17, BS-5C: 21, BS-5D: 19).
- **Frontend Suites**: 32 test suites, 282 tests passing. Production build succeeded.
- **Canonical Pilot Runtime Verification**:
  - Live PostgreSQL database row counts remained 100% identical before and after Client #3 multichannel executive preview:
    - `SocialMetricSnapshot` = 312
    - `SocialMetricRollup` = 551
    - `BusinessSignal` = 9
    - `ExecutiveReport` = 1
    - `ExecutiveNarrative` = 1
    - `DailyMetric` = 33
    - `PostMetric` = 38
    - `SyncLog` = 8
    - `UnifiedPost` = 14
    - `PlatformPublishLog` = 15
    - `PostQueue` = 2
    - `QueuedItem` = 3
    - `PeriodicTask` = 17
  - Provider API calls: 0. LLM generation calls: 0. Database writes: 0.


---

## BS-5D.0A — Benchmark Identity & Coverage Semantics Audit

### 1. Architectural Scope & Audit Resolution
Phase **BS-5D.0A** resolves two semantic inconsistencies identified during operator review of BS-5D prior to authorizing BS-5D.1:
1. Reconciling the granularity identity between the canonical pilot benchmark (`14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012`) and persisted `BusinessSignal` records (IDs 6–9).
2. Preserving strict machine-level semantic distinction between `unavailable_metrics` (10) and `non_comparable_metrics` (2), eliminating presentation collapsing in the machine payload.

---

### 2. Issue 1: Benchmark Granularity & Hash Identity

#### A. Hash Identity Verification (`generate_benchmark_hash`)
Verification of `social_stats.analytics.multichannel.benchmarks.generate_benchmark_hash` confirmed that granularity is an active, deterministic participant in the SHA-256 identity calculation.

Canonical serialized identity payload fields:
```json
{
  "schema_version": "bs5b-benchmark-v1",
  "client_id": 3,
  "platform_a": "facebook",
  "platform_b": "instagram",
  "period_start": "2026-09-22",
  "period_end": "2026-10-22",
  "granularity": "day",
  "metrics": [ ... 15 canonical metric evaluation dicts ... ]
}
```

#### B. Granularity Sensitivity
- Evaluated with `granularity = "day"`:
  `benchmark_hash = "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"`
- Evaluated with `granularity = "period"`:
  `benchmark_hash = "ce70369e8cd91de13974584a09e95dce45e4322aab9bf9bb96dd78ef9bed365a"`
- Granularity sensitivity is guaranteed: altering granularity directly alters the benchmark hash digest. A period benchmark cannot masquerade as a day benchmark.

#### C. Persisted Signal Binding (IDs 6–9)
Database inspection of canonical `BusinessSignal` rows 6–9 confirmed:
- `metadata["granularity"]` = `"day"`
- `metadata["benchmark_hash"]` = `"14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"`
- `evidence["benchmark_hash"]` = `"14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012"`
- `cohort_hash` = `None`
- `period_start` = `2026-09-22`
- `period_end` = `2026-10-22`

#### D. Root Cause & Decision
- **Root Cause**: The underlying code, benchmark generation, and persisted signals (IDs 6–9) all deterministically used and stored `granularity = "day"`. The canonical hash `14bb7652...` was generated under `granularity = "day"`. The reference to `granularity = "period"` in earlier review text was a documentation discrepancy.
- **Decision (Case 1)**: Documentation and reporting defect. The canonical benchmark hash did not change. Persisted `BusinessSignal` rows 6–9 required zero mutations and remain 100% untouched.

---

### 3. Issue 2: Coverage Semantics & Machine Payload

#### A. Canonical Diagnostic Representation
The machine payload schema in `report_data["multichannel_intelligence"]["coverage_summary"]` and canonical alias `report_data["multichannel_intelligence"]["coverage"]` strictly preserves separate diagnostic counts:

```json
{
  "total_metrics": 15,
  "comparable_metrics": 3,
  "rankable_metrics": 2,
  "non_rankable_metrics": 1,
  "unavailable_metrics": 10,
  "non_comparable_metrics": 2,
  "invalid_metrics": 0,
  "limited_or_noncomparable_metrics": 12,
  "coverage_ratio": "3/15",
  "status": "LIMITED",
  "status_label": "COBERTURA LIMITADA",
  "warning": "Limitación de datos entre plataformas: 10 métricas no disponibles y 2 no comparables (12 métricas limitadas o no comparables de 15)."
}
```

#### B. Semantic Invariants Preserved
- `unavailable_metrics = 10`: Represents metrics unqueried or unpermitted on Instagram (`PROVIDER_PARTIAL` 9 + `COMPONENT_UNAVAILABLE` 1).
- `non_comparable_metrics = 2`: Represents structurally non-comparable metrics (`SAVES` and `VIDEO_VIEWS` under `METRIC_NOT_EQUIVALENT`).
- `limited_or_noncomparable_metrics = 12`: Optional derived combined count representing total limitation footprint (10 + 2 = 12).
- `SAVES` and `VIDEO_VIEWS` strictly retain `compatibility = NON_COMPARABLE`, `status = UNAVAILABLE`, and `winner = NO_WINNER`.

---

### 4. BS-5D Preview Invocation & Tenant Safety

- In `backend/social_stats/analytics/reporting/builder.py`, `build_multichannel_benchmark` invocation was corrected to pass `client=client` (resolving keyword mismatch).
- Tenant isolation guard added: clients without comparable metrics (`comparable_metrics == 0`) and without persisted signals evaluate `has_mc_data = False`, ensuring empty comparison tables and zero cross-tenant signal leakage.

---

### 5. Deterministic Verification & Invariants

- **Django Check**: `python manage.py check` → System check identified no issues (0 silenced).
- **Targeted Test Suites**: 87 passing tests (BS-5A: 19, BS-5B: 17, BS-5C: 21, BS-5D: 19, BS-5D.0A: 11).
- **Full Backend Regression**: 1,014 passing tests (0 failures, 0 errors, ran in 99.3s).
- **Database Safety Invariants**:
  - `SocialMetricSnapshot` = 312
  - `SocialMetricRollup` = 551
  - `BusinessSignal` = 9
  - `ExecutiveReport` = 1
  - `ExecutiveNarrative` = 1
  - `DailyMetric` = 33
  - `PostMetric` = 38
  - `SyncLog` = 8
  - `UnifiedPost` = 14
  - `PlatformPublishLog` = 15
  - `PostQueue` = 2
  - `QueuedItem` = 3
  - `PeriodicTask` = 17
- Zero database writes. Zero external provider calls. Zero LLM calls.


---

## BS-5E ? Grounded Multichannel Narrative Safeties & Deterministic Preview

### 1. Overview & Architectural Role
Phase **BS-5E** extends Bop Social's Grounded AI Narrative system to safely consume multichannel executive intelligence (`ExecutiveReport #2`), single-platform signals (IDs 1?5), and multichannel signals (IDs 6?9) under canonical benchmark binding (`14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012`).

BS-5E operates strictly as an implementation, contract definition, safeguard enforcement, and deterministic preview phase:
- **Zero Live LLM Calls**: No calls to Ollama, OpenAI, Gemini, Anthropic, or Meta.
- **Zero Database Persistence**: `ExecutiveNarrative` count remains strictly 1; `ExecutiveReport` remains 2; `BusinessSignal` remains 9.
- **Fail-Closed Gate Architecture**: All claims, observations, and recommendations must be grounded strictly in allowlisted evidence.

---

### 2. Grounded Context Contract (`bs4h-context-v2`)
The narrative context is constructed via `build_grounded_narrative_context` adhering to approved schema version `bs4h-context-v2`:

```json
{
  "context_schema_version": "bs4h-context-v2",
  "report": {
    "id": 2,
    "title": "Informe Ejecutivo Multicanal",
    "period_start": "2026-09-22",
    "period_end": "2026-10-22",
    "language": "es",
    "report_type": "EXECUTIVE",
    "client_name": "Bop Agencia"
  },
  "kpis": { ... },
  "kpi_details": [ ... ],
  "platforms": { ... },
  "signals": [ ... ],
  "limitations": [ ... ],
  "supported_recommendations": [ ... ],
  "evidence_registry": { ... },
  "has_sufficient_data": false,
  "multichannel_intelligence": {
    "benchmark_hash": "14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012",
    "coverage_summary": {
      "status": "LIMITED",
      "coverage_ratio": "3/15",
      "total_metrics": 15,
      "comparable_metrics": 3,
      "unavailable_metrics": 10,
      "non_comparable_metrics": 2
    },
    "platform_comparisons": [ ... ],
    "limitations": [ ... ],
    "executive_takeaways": [ ... ]
  }
}
```

---

### 3. Evidence Registry & Stable Reference Resolution
The `evidence_registry` indexes all valid factual sources:
- **Multichannel Signals**: `MC-SIG-6`, `MC-SIG-7`, `MC-SIG-8`, `MC-SIG-9` resolve directly to corresponding persisted `BusinessSignal` rows.
- **Single-Platform Signals**: `SIG-1` through `SIG-5` maintain backwards compatibility.
- **Platform Limitations**: `LIMITATION-IG-PARTIAL`, `LIMITATION-CROSS-PLATFORM-PARTIAL`.
- **Fail-Closed Rule**: Any citation to an unregistered ID (e.g. `MC-SIG-999`) immediately raises a `ValueError` during confidence derivation and fails validation.

---

### 4. Claim Classification & Taxonomy Mapping
Deterministic claim categories allow validators to verify recommendation grounding:
- `AUDIENCE_CONTEXT` -> supported by `MC-SIG-6` (`FOLLOWERS_TOTAL`, action: `None`, informational only).
- `METRIC_COMPARISON` -> supported by `MC-SIG-7` (`REACTIONS`, action: `REVIEW_PLATFORM_PERFORMANCE`).
- `DATA_LIMITATION` -> supported by `MC-SIG-8` (`CROSS_PLATFORM_DATA_LIMITATION`, action: `REVIEW_PROVIDER_PERMISSIONS`).
- `SEMANTIC_LIMITATION` -> supported by `MC-SIG-9` (`CROSS_PLATFORM_METRIC_NON_COMPARABLE`, action: `CONTINUE_COLLECTING_DATA`).
- `RECOMMENDATION` -> supported by `MC-SIG-7`, `MC-SIG-8`, `SIG-1..5`.

---

### 5. Deterministic Validator Locks

`NarrativeValidator` enforces 10 strict verification gates:

1. **Overall Winner Lock**: Rejects phrases such as *"Instagram es la mejor plataforma en general"*, *"ganador general"*, *"canal m?s fuerte"*, *"peor plataforma"*, or *"should replace"*.
2. **Cross-Metric Aggregation Lock**: Forbids synthetic composite platform performance scores, weighted sums, or combined channel rankings.
3. **Zero-Baseline Percentage Lock**: When baseline platform is 0 (Facebook reactions = 0, Instagram reactions = 6), percentage language (`+600%`, `600 percent`, `seiscientos por ciento`) is strictly rejected.
4. **Metric Availability Lock**: Forbids performance, trend, or numeric claims on unavailable metrics (`REACH`, `IMPRESSIONS`, `ENGAGEMENT_TOTAL`, `PROFILE_VIEWS`, `CLICKS_TOTAL`, `SHARES`). Only availability/limitation statements are permitted.
5. **Non-Comparable Metric Lock**: Forbids ranking or superiority comparisons for `SAVES` and `VIDEO_VIEWS`. Only semantic divergence callouts are allowed.
6. **Audience Non-Performance Lock**: Follower counts (`FOLLOWERS_TOTAL`) represent point-in-time audience volume only. Any claim linking follower volume to strategic superiority, efficiency, quality, or competitive performance is rejected.
7. **Causality Guard**: Rejects unsupported causal assertions (*"porque"*, *"caused"*, *"drove"*, *"debido a que su contenido fue mejor"*, *"tu audiencia prefiere"*). Mathematical explanations of zero baselines are exempt.
8. **Budget Reallocation Prohibition**: Forbids recommendations suggesting budget shifts across channels (*"Move budget to Instagram"*, *"Reasignar presupuesto de Facebook a Instagram"*) based on limited 3/15 coverage.
9. **Limitation Preservation Lock**: When cross-platform comparisons are made under limited coverage (3/15), the limitations section must explicitly acknowledge the limited data coverage constraint.
10. **Language Contract Lock**: When report language is `es` (Spanish), any English sentences or function words are strictly rejected.

---

### 6. Confidence Authority & Derivation Architecture
- **No Model-Authored Confidence**: The generative model never defines recommendation confidence. Schema for providers strictly omits confidence properties.
- **Deterministic Confidence Calculation**: `derive_recommendation_confidence` derives canonical confidence as the minimum confidence among all cited evidence references.
- **Multichannel Authority**: Signals `MC-SIG-6`, `MC-SIG-7`, `MC-SIG-8`, and `MC-SIG-9` carry deterministic `HIGH` confidence.

---

### 7. Context Hash Determinism & Staleness Rules
- **Context Hash**: SHA-256 digest calculated over the canonically sorted JSON context string:
  `a7fb12cb84fdf4e17a11c14f0fbc9a31690b640af53a59ee6d0d7fa6a03db87c`
- **Hash Sensitivity**: Any change to `benchmark_hash`, coverage numbers, or underlying signals alters the context hash.
- **Staleness Rule**: If `ExecutiveReport.source_hash` or `benchmark_hash` shifts, any existing narrative is flagged as stale.

---

### 8. Future BS-5E.1 Live-Call Policy & Idempotency Design
- **Single Authorized Call**: Exactly one model generation call is permitted per user authorization. Automatic retries are strictly prohibited.
- **Validation Failure Policy**: If validation fails after generation, the draft is marked `REJECTED` and no second generation call is attempted without operator intervention.
- **Idempotency Identity**: Future persistence binds to:
  `client_id` : `executive_report_id` : `source_hash` : `context_hash` : `prompt_version` : `provider_name`
  Guarantees 0 duplicate records on repeated requests.

---

### 9. Test Suite & Verification Results
- **BS-5E Dedicated Tests**: 25 tests passing (`test_grounded_multichannel_narrative.py`).
- **Targeted Multichannel Regression**: 190 tests passing (BS-4H: 78, BS-5A: 20, BS-5B: 20, BS-5C: 17, BS-5D: 24, BS-5D.0A: 6, BS-5E: 25).
- **Full Backend Regression**: 1,039 tests passing (0 failures, 0 errors, ran in 101.9s).
- **Database Safety Invariants**:
  - `SocialMetricSnapshot` = 312
  - `SocialMetricRollup` = 551
  - `BusinessSignal` = 9
  - `ExecutiveReport` = 2
  - `ExecutiveNarrative` = 1
  - `DailyMetric` = 33
  - `PostMetric` = 38
  - `SyncLog` = 8
  - `UnifiedPost` = 14
  - `PlatformPublishLog` = 15
  - `PostQueue` = 2
  - `QueuedItem` = 3
  - `PeriodicTask` = 17
- **Provider Call Invariants**: Ollama = 0, OpenAI = 0, Gemini = 0, Anthropic = 0, Meta = 0, Facebook = 0, Instagram = 0.


---

## BS-5E.0A — Live Execution Safety Contract Audit & Single-Attempt Policy Enforcement

### 1. Executive Summary & Objective
Following operator review of phase BS-5E, Phase BS-5E.0A audits and resolves two critical safety contract requirements prior to authorizing live LLM generation in BS-5E.1:
1. **Enforce Strict Single-Attempt Execution Policy**:
   - `MAX_PROVIDER_CALLS = 1` enforced at application runtime.
   - 0 automatic retries under any circumstance.
   - 0 validation-feedback retry loops.
   - 0 deterministic fallback substitutions persisted as live results (`fallback_enabled = False`).
   - If transport fails, response is ambiguous, JSON is malformed, or any validator gate fails -> immediate STOP, 0 database writes (`ExecutiveNarrative` persistence = 0), operator audit required.
2. **Canonical Signal Identity vs. Additive Narrative Classification**:
   - Persisted `BusinessSignal.signal_type` values for signals IDs 6–9 are strictly canonical:
     - ID 6: `AUDIENCE_SIZE_DIFFERENCE`
     - ID 7: `PLATFORM_METRIC_OUTPERFORMANCE`
     - ID 8: `CROSS_PLATFORM_DATA_LIMITATION`
     - ID 9: `CROSS_PLATFORM_METRIC_NON_COMPARABLE`
   - Presentation / narrative claim categories are cleanly separated into additive `claim_category` fields:
     - `MC-SIG-6`: `signal_type="AUDIENCE_SIZE_DIFFERENCE"`, `claim_category="AUDIENCE_CONTEXT"`
     - `MC-SIG-7`: `signal_type="PLATFORM_METRIC_OUTPERFORMANCE"`, `claim_category="PERFORMANCE_COMPARISON"`
     - `MC-SIG-8`: `signal_type="CROSS_PLATFORM_DATA_LIMITATION"`, `claim_category="DATA_AVAILABILITY"`
     - `MC-SIG-9`: `signal_type="CROSS_PLATFORM_METRIC_NON_COMPARABLE"`, `claim_category="SEMANTIC_LIMITATION"`
   - Full retention of `signal_id`, `signal_identity`, `metric`, `confidence`, and `benchmark_hash`.

---

### 2. Context Hash Recomputation
- **Previous Context Hash (BS-5E baseline)**:
  `a7fb12cb84fdf4e17a11c14f0fbc9a31690b640af53a59ee6d0d7fa6a03db87c`
- **Final Approved Context Hash (BS-5E.0A with canonical signal identity & additive claim_category)**:
  `722dc6422a6bc7869f05d1d6c6cf0c352cbbcd060ec01f2b1c47a27d0f738628`
- **Context Hash Changed**: **YES** (Authorized: `ExecutiveNarrative #2` does not yet exist; ensures complete fidelity to persisted DB identity).
- **Context Schema Version**: `bs4h-context-v2` (retained).
- **Prompt Version**: `bs5d-prompt-v1` (retained).

---

### 3. Policy Comparison Matrix

| Dimension | Previous Default Behavior | Controlled Live Policy (`single_attempt_strict`) |
| :--- | :--- | :--- |
| **Max Provider Calls** | 1 (untracked) | **1 (Hard Enforced & Audited)** |
| **Transport Failure** | Unhandled / Generic Exception | **Immediate STOP; 0 Retries; 0 Persisted Rows** |
| **Ambiguous Transport** | Unhandled | **Immediate STOP; Operator Audit Mandated** |
| **Malformed JSON** | Provider Exception | **Immediate STOP; 0 Retries; 0 Persisted Rows** |
| **Validation Gate Failure** | Persisted row with `status='REJECTED'` | **Immediate STOP; 0 DB Persistence (`ControlledLiveExecutionError`)** |
| **Validation Retry Feedback** | Not active | **Strictly Forbidden** |
| **Deterministic Fallback** | Allowed in auxiliary routines | **Strictly Disabled (`fallback_enabled=False`)** |
| **Persistence Authorization** | Allowed on failure (`REJECTED`) | **Strictly Conditional on 100% Gates Passing (`VALIDATED`)** |
| **Attempt Accounting** | Untracked | **Persisted in narrative metadata (`provider_attempt_count: 1`)** |

---

### 4. Test Suite & Verification Results
- **BS-5E Dedicated Tests**: 61 tests passing (`test_grounded_multichannel_narrative.py`).
- **Targeted Multichannel Regression**: 226 tests passing (BS-4H: 78, BS-5A: 20, BS-5B: 20, BS-5C: 17, BS-5D: 24, BS-5D.0A: 6, BS-5E & BS-5E.0A: 61).
- **Database Safety Invariants**:
  - `SocialMetricSnapshot` = 312
  - `SocialMetricRollup` = 551
  - `BusinessSignal` = 9
  - `ExecutiveReport` = 2
  - `ExecutiveNarrative` = 1
  - `DailyMetric` = 33
  - `PostMetric` = 38
  - `SyncLog` = 8
  - `UnifiedPost` = 14
  - `PlatformPublishLog` = 15
  - `PostQueue` = 2
  - `QueuedItem` = 3
  - `PeriodicTask` = 17
- **Provider Call Invariants**: Ollama = 0, OpenAI = 0, Gemini = 0, Anthropic = 0, Meta = 0, Facebook = 0, Instagram = 0.


---

## BS-5E.1A — Live Narrative Prompt Hardening & Constrained Generation Contract

### 1. Executive Summary & BS-5E.1 Attempt 1 Audit
In Phase BS-5E.1, a single controlled live execution attempt was performed using the local small language model (`qwen3.5:9b` via Ollama) targeting `ExecutiveReport #2`. The single call executed under `MAX_PROVIDER_CALLS = 1`:
- Transport succeeded (HTTP 200).
- Provider returned valid JSON matching the schema syntax.
- The output failed deterministic semantic validation across **three** safety trip classes:
  1. **Metric Availability Framing**: Instagram unavailable metrics (such as `REACH`) were described as active performance observations rather than being strictly restricted to provider limitation statements.
  2. **Audience-Size Non-Performance Framing**: Follower counts (`FOLLOWERS_TOTAL`: 50 IG vs. 20 FB) were described using comparative performance superiority language (*"superó en rendimiento"*, *"mejor desempeño"*), violating the audience volume vs. performance lock.
  3. **Mandatory 3/15 Coverage Preservation**: Cross-platform reaction performance claims were asserted without preserving the mandatory explicit coverage disclosure (*"solo 3 de 15 métricas canónicas son actualmente comparables"*).
- The runtime safety architecture functioned exactly as intended:
  - **Persistence**: **0 rows** written (`ExecutiveNarrative` count remained strictly 1).
  - **Retries**: **0 automatic retries** triggered.
  - **Fallback**: **0 deterministic fallback substitutions** persisted.
  - The failed attempt remains permanently audited in historical execution logs as Attempt 1 (`FAILED_VALIDATION`).

Phase BS-5E.1A hardens the prompt and context architecture offline so that small local models have substantially less linguistic freedom around governed facts.

---

### 2. Architectural Principle: Constrained Language Compiler
Instead of relying on abstract negative prohibitions (*"avoid unsupported claims"*), the generation contract moves to **mandatory canonical phrasing patterns**:
$$	ext{Generative Model Role} = 	ext{Compiler of Approved Facts} \quad (	ext{NOT an Analytics Engine})$$

The LLM is provided with precomputed, evidence-grounded facts and instructed to summarize and organize them using verified linguistic templates.

---

### 3. Core Hardening Contracts

#### A. Approved Facts Architecture
Seven deterministic, allowlisted facts are injected into `context["approved_facts"]` for multichannel reports:
1. `FACT-MC-1`: Coverage limitation disclosure (*"La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables."*, refs: `["MC-SIG-8"]`).
2. `FACT-MC-2`: Audience volume context (*"Instagram registró una audiencia de 50 seguidores frente a 20 en Facebook. Esta diferencia describe tamaño de audiencia y no implica superioridad de rendimiento entre plataformas."*, refs: `["MC-SIG-6"]`).
3. `FACT-MC-3`: Reactions raw comparison without percentages (*"Instagram registró 6 reacciones frente a 0 en Facebook durante el periodo analizado. Debido a que la línea base observada en Facebook es cero, no se expresa una variación porcentual."*, refs: `["MC-SIG-7"]`).
4. `FACT-MC-4`: Unavailable metrics limitation statement (*"Diez métricas no están disponibles para una comparación completa con la configuración actual del proveedor, y dos métricas adicionales no son semánticamente comparables entre Facebook e Instagram."*, refs: `["MC-SIG-8"]`).
5. `FACT-MC-5`: Non-comparable metrics statement (*"SAVES y VIDEO_VIEWS no se comparan directamente entre Facebook e Instagram debido a diferencias en las definiciones y disponibilidad de proveedor."*, refs: `["MC-SIG-9"]`).
6. `FACT-MC-6`: Provider permissions recommendation (*"Revisar los permisos y capacidades de integración del proveedor para ampliar la cobertura de métricas comparables."*, refs: `["MC-SIG-8"]`).
7. `FACT-MC-7`: Platform performance review recommendation (*"Revisar el desempeño por plataforma con mayor profundidad a medida que se acumule una muestra más amplia de métricas comparables."*, refs: `["MC-SIG-7"]`).

#### B. Audience Semantic Contract
`MC-SIG-6` explicitly specifies semantic boundaries in context:
- `signal_type`: `AUDIENCE_SIZE_DIFFERENCE`
- `claim_category`: `AUDIENCE_CONTEXT`
- `allowed_interpretation`: `AUDIENCE_SIZE_ONLY`
- `forbidden_interpretations`: `["PERFORMANCE_SUPERIORITY", "EFFICIENCY_SUPERIORITY", "OVERALL_WINNER", "CONTENT_QUALITY"]`
Forbidden terms describing followers include: *superior*, *mejor desempeño*, *mejor rendimiento*, *más efectivo*, *más fuerte*, *ganador*, *dominante*.

#### C. Zero-Baseline Reaction Contract
When the baseline platform is 0 (Facebook reactions = 0, Instagram reactions = 6), percentage variations (`+600%`, `600%`, `6x better`, `seis veces mejor`) are strictly forbidden. Only raw absolute counts are permitted.

#### D. Unavailable Metric Framing
Unavailable metrics (`REACH`, `IMPRESSIONS`, `SHARES`, `SAVES`, `VIDEO_VIEWS` under partial permissions) may appear strictly within capability or limitation framing. Any performance or trend verb attached to an unavailable metric triggers immediate validator rejection.

#### E. Mandatory Coverage Disclosure
Any narrative containing cross-platform comparisons MUST preserve the canonical coverage sentence:
*"La comparación entre plataformas es limitada: solo 3 de 15 métricas canónicas son actualmente comparables."*
Enforced via:
1. Mandatory presence in `limitations`.
2. Optional structured field `cross_platform_coverage_disclosure` (`comparable_metrics: 3`, `total_metrics: 15`, `status: "LIMITED"`).

#### F. Recommendation Scope Restriction
Only approved, grounded multichannel recommendations are permitted:
- `REVIEW_PROVIDER_PERMISSIONS` (refs: `["MC-SIG-8"]`)
- `REVIEW_PLATFORM_PERFORMANCE` (refs: `["MC-SIG-7"]`)
- `CONTINUE_COLLECTING_DATA` (refs: `["MC-SIG-9"]` or `["SIG-1"]`)
Any budget reallocation recommendation (*"move budget"*, *"reasignar presupuesto"*) is strictly forbidden.

---

### 4. Versioning & Context Hash

| Component | Previous Version (BS-5E / BS-5E.0A) | New Version (BS-5E.1A) |
| :--- | :--- | :--- |
| **Prompt Version** | `bs5d-prompt-v1` | `bs5e-prompt-v2` |
| **Output Schema Version** | `bs4h-output-v1` | `bs5e-output-v2` |
| **Context Schema Version** | `bs4h-context-v2` | `bs4h-context-v2` (retained) |
| **Approved Facts Count** | 0 (unstructured) | **7 canonical facts** |
| **Negative Examples** | 0 | **5 explicit FORBIDDEN patterns** |
| **Context Hash** | `722dc6422a6bc7869f05d1d6c6cf0c352cbbcd060ec01f2b1c47a27d0f738628` | `e4d615700de831ce81c968480226686010b2b38a2b61073ca8bda8588b982905` |

---

### 5. Future Live Execution Identity Freeze

```text
Client ID: 3
ExecutiveReport: #2
Report Source Hash: cb79885ade504aeac72f1bf2854b155be31c33b0c9ce3f0c168c7fc0a38ad148
Benchmark Hash: 14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012
Context Hash: e4d615700de831ce81c968480226686010b2b38a2b61073ca8bda8588b982905
Prompt Version: bs5e-prompt-v2
Output Schema Version: bs5e-output-v2
Context Schema Version: bs4h-context-v2
Language: es
Provider: ollama
Model: qwen3.5:9b
Policy: single_attempt_strict (MAX_PROVIDER_CALLS = 1, fallback_enabled = False)
Authorization Status: PENDING OPERATOR REVIEW (DO NOT EXECUTE)
```

---

### 6. Test Suite & Verification Results
- **First Live Failure Replay**: Tested and **REJECTED** (triggers all 3 original failure classes; validators NOT weakened).
- **BS-5E.1A Dedicated Tests**: 8 new tests, 69 total tests passing (`test_grounded_multichannel_narrative.py`).
- **Targeted Multichannel Regression**: 223 tests passing (0 failures, 0 errors, ran in 22.2s).
- **Full Backend Regression**: 1,083 tests passing (0 failures, 0 errors, ran in 108.2s).
- **Database Safety Invariants**:
  - `SocialMetricSnapshot` = 312
  - `SocialMetricRollup` = 551
  - `BusinessSignal` = 9
  - `ExecutiveReport` = 2
  - `ExecutiveNarrative` = 1
  - `DailyMetric` = 33
  - `PostMetric` = 38
  - `SyncLog` = 8
  - `UnifiedPost` = 14
  - `PlatformPublishLog` = 15
  - `PostQueue` = 2
  - `QueuedItem` = 3
  - `PeriodicTask` = 17
- **Provider Call Invariants**: Ollama = 0, OpenAI = 0, Gemini = 0, Anthropic = 0, Meta = 0, Facebook = 0, Instagram = 0.


---

## BS-5E.1B & BS-5E.1C — Controlled Live Execution Audit & Semantic Precision Hardening

### 1. BS-5E.1B Live Execution Outcome (Attempt 2)

On October 26, 2026, an operator-authorized controlled live execution of `ExecutiveReport #2` was performed using:
- **Provider**: `ollama`
- **Model**: `qwen3.5:9b`
- **Prompt Version**: `bs5e-prompt-v2`
- **Output Schema Version**: `bs5e-output-v2`
- **Context Hash**: `e4d615700de831ce81c968480226686010b2b38a2b61073ca8bda8588b982905`
- **Policy**: `single_attempt_strict` (`MAX_PROVIDER_CALLS = 1`, `fallback_enabled = False`)

#### Telemetry & Transport Results
- **Provider Attempt Count**: 1 (0 -> 1)
- **Transport Status**: `SUCCESS` (HTTP 200, latency: 9.17s)
- **Input Tokens**: 2,050
- **Output Tokens**: 514
- **Total Tokens**: 2,564
- **Response Size**: 2,062 characters (2,067 bytes)
- **Response SHA-256**: `bc5c0ff15a87ce4909ee84fec1216de7ba37f2b9476327e11f2df48d2f84c4d4`
- **JSON Parse**: `PASS`
- **Derived Confidence Enrichment**: `PASS`

#### Gate Results & Fail-Closed Enforcement
The live response triggered three deterministic validator rejections:
1. `causality_safe`: Tripped by `"ya que"` in `"ya que se trata de una métrica de escala absoluta"`.
2. `Audience non-performance lock`: Tripped by the presence of the word `"superioridad"` within a disclaimer clause (`"no necesariamente superioridad de rendimiento"`).
3. `Limitation preservation lock`: Tripped because the coverage statement `"solo 3 de las 15 métricas"` included the article `"las"`, which did not match literal regex `"3/15"` or `"3 de 15"`.

Pursuant to the hard runtime policy:
- **Persistence Executed**: **NO** (0 rows written, `ExecutiveNarrative` count remains strictly 1).
- **Retries**: **0**.
- **Fallback**: **0**.
- **Database Baseline**: Verified 100% unchanged.

---

### 2. Critical Issue 0 Audit — Authoritative HEAD Verification

An identity discrepancy between the reported BS-5E.1A HEAD (`df3f9bc0f60c70e7eef4627d4999f848beceb7b5`) and the BS-5E.1B runtime HEAD (`df3f9bc03882e428825cfcc3ac871c84eed327fb`) was audited against git reflog and commit tree:
- **Authoritative Commit SHA**: `df3f9bc03882e428825cfcc3ac871c84eed327fb` (`git rev-parse HEAD`).
- **Commit Details**: `df3f9bc fix(bopsocial): harden multichannel narrative generation contract`.
- **Reflog Analysis**: `HEAD@{0}` is `df3f9bc`. There were 0 intermediate commits between BS-5E.1A and BS-5E.1B.
- **Root Cause**: The assistant in BS-5E.1A generated an unverified 40-character SHA string from the 7-character prefix `df3f9bc` instead of executing `git rev-parse HEAD`.
- **Conclusion**: BS-5E.1B executed 100% against the authoritative, intended BS-5E.1A hardened code.

---

### 3. BS-5E.1C Semantic Precision & Claim-Scope Hardening

Audit of the Attempt 2 generation revealed two distinct failure types:
1. **Validator False Positives**:
   - Disclaimers containing negated superiority words (`"...no necesariamente superioridad de rendimiento"`).
   - Definitional connectives (`"...ya que se trata de una métrica de escala absoluta"`).
   - Natural Spanish coverage phrasing (`"...solo 3 de las 15 métricas canónicas..."`).
2. **True Model Generalizations (Risk)**:
   - Generalizing 6 raw reactions into `"ventaja competitiva en métricas de rendimiento clave"`.
   - Generalizing reactions into `"Instagram lidera en interacciones"`.

#### Precision Remediations Implemented:
1. **Coverage Semantic Parser (Gate G)**:
   - Deterministic numeric semantic parser accepting Spanish variants:
     `3/15`, `3 de 15`, `3 de las 15`, `3 de un total de 15`, `solo tres de quince`, `solo tres de las quince`, `solo 3 de las 15 métricas`, `3 of 15`, `three of fifteen`.
   - Rejects vague assertions lacking explicit 3/15 numeric disclosure.
2. **Negation-Aware Audience Lock (Gate E)**:
   - Identifies explicit disclaimer structures (`no implica superioridad`, `no necesariamente superioridad`, `no se utiliza para evaluar desempeño`, `no debe interpretarse como mejor rendimiento`).
   - Strips disclaimer clauses from sentence context, then verifies that no affirmative superiority assertions remain.
3. **Causality Precision (Guard 6)**:
   - Permits approved mathematical zero-baseline explanations and metric-scale definitional clarifications.
   - Strictly prohibits ungrounded causal performance attributions (`caused`, `causó`, `provocó`, `debido a la calidad`, `debido al contenido`, `tu audiencia prefiere`, `esto demuestra`).
4. **Competitive-Language & Claim-Scope Lock (Gate I)**:
   - Forbids broad competitive terminology under limited coverage pilot:
     `ventaja competitiva`, `lidera en interacciones`, `lidera en engagement`, `liderazgo general`, `dominancia`, `mejor canal`, `plataforma superior`, `métricas de rendimiento clave`.
   - Enforces that reactions evidence (`MC-SIG-7`) remains strictly scoped to raw reactions.

---

### 4. Regression & Replay Matrix Results

| Test Target | Expected Result | Actual Result |
| :--- | :--- | :--- |
| **Attempt 1 Fixture Replay** | FAIL (3 locks) | **FAIL** (Preserved) |
| **Attempt 2 False Positives (Isolated)** | PASS (Coverage, Disclaimer, Definition) | **PASS** |
| **Attempt 2 Full Replay** | **FAIL** (on Broad Claims: `ventaja competitiva`, `lidera en interacciones`) | **FAIL** (`Claim-scope lock failed`) |
| **Section K Test Matrix (18 Scenarios)** | All 6 PASS cases PASS, all 12 FAIL cases FAIL | **PASS** (18 / 18 Verified) |
| **Golden Spanish Output V2** | PASS with 0 errors | **PASS** (0 errors) |
| **Targeted Multichannel Tests** | 225 passing | **225 PASSING** (in 22.9s) |
| **Full Backend Regression** | >= 1,083 passing | **1,085 PASSING** (in 109.6s, 0 failures, 0 errors) |

---

### 5. Final Identity Freeze for Future Live Execution

```text
Client ID: 3 (Bop Agencia)
ExecutiveReport ID: 2
Report Source Hash: cb79885ade504aeac72f1bf2854b155be31c33b0c9ce3f0c168c7fc0a38ad148
Benchmark Hash: 14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012
Context Hash: e4d615700de831ce81c968480226686010b2b38a2b61073ca8bda8588b982905 (UNCHANGED)
Prompt Version: bs5e-prompt-v3
Output Schema Version: bs5e-output-v2
Context Schema Version: bs4h-context-v2
Language: es
Provider: ollama
Model: qwen3.5:9b
Policy: single_attempt_strict (MAX_PROVIDER_CALLS = 1, fallback_enabled = False)
Authorization Status: PENDING OPERATOR REVIEW (DO NOT EXECUTE)
```

---

## BS-5E.1F — Ollama System Prompt Delivery Remediation

### 1. Root Cause Analysis (Discovered in BS-5E.1E)

In phases BS-5E.1B (Attempt 2) and BS-5E.1D (Attempt 3), live Ollama executions produced identical model telemetry (`input_tokens: 2,050`, `output_tokens: 514`, SHA256 `bc5c0ff15a87ce4909ee84fec1216de7ba37f2b9476327e11f2df48d2f84c4d4`) and repeated the same forbidden competitive phrases (`"ventaja competitiva..."`, `"lidera en interacciones"`).

Architectural inspection of Ollama model metadata via `/api/show` revealed the definitive root cause:
- **Model Modelfile Template**: The installed `qwen3.5:9b` (as well as `qwen3.5-32k` and `qwen3.5-64k`) contains:
  ```text
  TEMPLATE {{ .Prompt }}
  ```
  **There is no `{{ .System }}` variable in the template.**
- **Ollama Payload Behavior**: When `OllamaNarrativeProvider.generate()` submitted `payload = {"system": system_prompt, "prompt": user_prompt}`, Ollama's Go template renderer interpolated only `{{ .Prompt }}`. The separate `system` payload key was **completely discarded** by the Ollama server runtime.
- **Resulting Defect**: The LLM evaluated only `user_prompt` (which was 100% identical in Attempt 2 and Attempt 3). At `temperature: 0.0`, identical inputs deterministically generated the identical output to the character. The system prompt instructions and Section J/K negative examples were never visible to the model.

---

### 2. Provider Delivery Fix (`compose_ollama_prompt`)

To guarantee deterministic delivery of system instructions, safety locks, and negative examples across all Ollama models regardless of Modelfile template variations:
1. **Plaintext Composition**: Implemented `compose_ollama_prompt(system_prompt, user_prompt)`:
   ```text
   ===== SYSTEM INSTRUCTIONS =====
   <system_prompt>

   ===== USER / GROUNDED CONTEXT =====
   <user_prompt>
   ```
2. **Elimination of Duplicate System Risk**: The outgoing request now sets `payload["prompt"] = composed_prompt` and omits `payload["system"]`. This prevents accidental double-delivery on models whose templates do support `{{ .System }}`.
3. **Context Window Configuration**: Set `options.num_ctx = 32768` (well within the model's native 262,144 context length), providing ~18k tokens of generation headroom for the ~14.6k token composed prompt.
4. **Preserved Semantics**:
   - `PROMPT_VERSION = "bs5e-prompt-v3"` (strictly preserved; no prompt v4).
   - `OUTPUT_SCHEMA_VERSION = "bs5e-output-v2"`.
   - `temperature = 0.0`.
   - 0 modifications to validators or approved facts.

---

### 3. Verification & Test Metrics

- **Unit Tests**: `OllamaSystemPromptDeliveryTests` added (7 dedicated tests covering ordering, sentinels, empty handling, v2 vs v3 hash variance, v3 rule visibility, approved facts visibility, and mocked request payload).
- **Targeted Multichannel Suite**: **78 passing** (including 7 delivery tests).
- **Full Backend Regression Suite**: **1,092 passing** (100% pass rate, 0 failures, 0 errors).
- **Database Baseline**: All 13 canonical tables strictly invariant.

---

### 4. Final Identity Freeze for Future Controlled Live Execution

```text
Client ID: 3 (Bop Agencia)
ExecutiveReport ID: 2
Report Source Hash: cb79885ade504aeac72f1bf2854b155be31c33b0c9ce3f0c168c7fc0a38ad148
Benchmark Hash: 14bb7652b4247a6b98f2265796f1b320987684634a2d3ec27608faf671083012
Context Hash: e4d615700de831ce81c968480226686010b2b38a2b61073ca8bda8588b982905
Prompt Version: bs5e-prompt-v3
Output Schema Version: bs5e-output-v2
Context Schema Version: bs4h-context-v2
Provider: ollama
Model: qwen3.5:9b
Model-Visible Prompt SHA256: ebca7a24c0eea1b1940bfeb08668c15c238489ebc246945deb288708709657f6
Configured num_ctx: 32768
Configured temperature: 0.0
Policy: single_attempt_strict (MAX_PROVIDER_CALLS = 1, fallback_enabled = False)
Authorization Status: PENDING OPERATOR REVIEW (DO NOT EXECUTE)
```
