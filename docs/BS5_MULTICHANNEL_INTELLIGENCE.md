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
