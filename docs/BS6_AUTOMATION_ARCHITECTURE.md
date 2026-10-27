# BS-6A Production Intelligence Automation Architecture

## 1. Overview & Purpose

Phase **BS-6A** establishes the production automation and deterministic scheduling foundation for BOP Social's multichannel intelligence pipeline.

Following Phase BS-5 (which proved manual, controlled operator execution of multi-platform rollups, cross-platform business signals, executive reporting, and grounded AI executive narratives), BS-6A constructs the orchestration and safety architecture required for scheduled, multi-tenant intelligence generation without prematurely activating autonomous recurring generation.

The intelligence pipeline follows a deterministic chain of progression:
```
Provider Sync ──► Metric Snapshots ──► Metric Rollups ──► Business Signals ──► Executive Report ──► Grounded Executive Narrative
```

Every stage in BS-6A is independently gated, strictly audited, tenant-isolated, idempotent, fail-closed, and safe against concurrent duplicate execution.

---

## 2. Core Architectural Invariants

1. **Explicit Tenant Unit**: Automation never executes globally without tenant enumeration. An automation unit is strictly defined as:
   $$\text{Automation Unit} = \text{Tenant (Client)} + \text{Reporting Period} + \text{Pipeline Version}$$
2. **Deterministic Execution Identity**: Every run derives its deduplication key via a SHA-256 digest of `client_id`, `period_start`, `period_end`, and `pipeline_version`.
3. **Database Unique Constraints**: Database-level unique constraints on active execution identities prevent duplicate inflight executions across distributed workers, complementing advisory locks.
4. **PostgreSQL Advisory Single-Flight Locking**: Fast, lightweight distributed mutual exclusion is maintained using PostgreSQL session advisory locks derived deterministically from the execution identity.
5. **Fail-Closed Eligibility**: Any unfulfilled safety invariant (e.g., inactive client, missing active credentials, stale telemetry, disabled config) halts execution cleanly without external provider calls or DB corruption.
6. **Existing Artifact Reuse**: If valid `ExecutiveReport` or `ExecutiveNarrative` records already exist for the requested period, the engine reuses them rather than regenerating or overwriting canonical data.
7. **Strict Provider Budget Enforcement**: Provider call budgets are strictly enforced (`budget = 1` by default, `0` in dry-run mode). Live LLM or social API calls are disallowed if the budget is exhausted.
8. **Pure Dry-Run Preview Mode**: Dry-run mode (`dry_run=True`) performs zero database mutations (no config edits, no run records, no report/narrative generation) and zero provider network calls, producing a comprehensive execution plan and diagnostic explanation.
9. **Observability Without Secret Leaking**: All audit events use structured JSON with automatic redaction of bearer tokens, client secrets, passwords, and private API keys.
10. **Disabled-by-Default Scheduler**: Recurring Celery Beat periodic tasks are registered as unscheduled/disabled until full production approval.

---

## 3. Data Models

### 3.1 `IntelligenceAutomationConfig`

Tenant-level configuration governing pipeline scheduling, freshness thresholds, and safety limits.

| Field | Type | Default | Description |
|---|---|---|---|
| `client` | `OneToOneField(Client)` | Required | Foreign key to tenant client |
| `enabled` | `BooleanField` | `False` | Master switch for tenant automation |
| `timezone` | `CharField(64)` | `'America/New_York'` | Tenant timezone name |
| `reporting_frequency` | `CharField(20)` | `'MONTHLY'` | Schedule cadence (`MONTHLY`, `WEEKLY`, `CUSTOM`) |
| `reporting_day` | `PositiveSmallIntegerField` | `1` | Day of month (1-28) or weekday (0=Mon, 6=Sun) |
| `reporting_hour` | `PositiveSmallIntegerField` | `2` | Execution hour in tenant local time (0-23) |
| `lookback_days` | `PositiveIntegerField` | `30` | Data lookback duration |
| `minimum_data_freshness_hours` | `PositiveIntegerField` | `48` | Maximum telemetry staleness before blocking |
| `generate_report` | `BooleanField` | `True` | Whether to generate executive report |
| `generate_narrative` | `BooleanField` | `False` | Whether to generate AI grounded narrative |
| `require_operator_approval` | `BooleanField` | `True` | Enforce human-in-the-loop review |
| `provider_call_budget` | `PositiveIntegerField` | `1` | Max permitted external LLM calls per period |
| `max_retry_count` | `PositiveIntegerField` | `0` | Max automated retry attempts |

### 3.2 `IntelligenceAutomationRun`

Durable orchestration record tracking stage progression, execution identity, audit metadata, and artifact references.

| Field | Type | Description |
|---|---|---|
| `client` | `ForeignKey(Client)` | Associated tenant client |
| `agency_id` | `CharField(64)` | Agency identifier (supports UUIDs and string IDs) |
| `period_start` | `DateField` | Reporting period start boundary |
| `period_end` | `DateField` | Reporting period end boundary |
| `pipeline_version` | `CharField(32)` | Pipeline schema/algorithm version (default: `'bs6a-v1'`) |
| `execution_identity` | `CharField(64)` | SHA-256 hash of `(client_id, period_start, period_end, pipeline_version)` |
| `trigger_type` | `CharField(20)` | `MANUAL`, `SCHEDULED`, `RETRY`, or `ADMIN` |
| `status` | `CharField(20)` | `PENDING`, `ELIGIBILITY_CHECK`, `RUNNING`, `BLOCKED`, `FAILED`, `COMPLETED`, `CANCELLED` |
| `current_stage` | `CharField(32)` | Currently executing or evaluated pipeline stage |
| `started_at` | `DateTimeField` | Execution commencement timestamp |
| `finished_at` | `DateTimeField` | Execution conclusion timestamp |
| `requested_by` | `CharField(128)` | Username, task name, or system trigger |
| `dry_run` | `BooleanField` | Whether execution was executed as a dry-run |
| `provider_call_count` | `PositiveIntegerField` | Recorded number of external provider calls |
| `retry_count` | `PositiveIntegerField` | Current retry counter |
| `fallback_count` | `PositiveIntegerField` | Current fallback invocation counter |
| `error_code` | `CharField(64)` | Structured error or block code |
| `error_message_safe` | `TextField` | Sanitized, non-sensitive error explanation |
| `report_id` | `PositiveIntegerField` | ID of generated or reused `ExecutiveReport` |
| `narrative_id` | `PositiveIntegerField` | ID of generated or reused `ExecutiveNarrative` |

#### Unique Constraint
```python
UniqueConstraint(
    fields=["execution_identity"],
    condition=Q(status__in=["PENDING", "ELIGIBILITY_CHECK", "RUNNING"]),
    name="unique_active_intelligence_automation_identity",
)
```
This ensures that duplicate inflight runs for the same client, period, and pipeline version are rejected at the database level.

---

## 4. Pipeline Stages

The pipeline defines eight sequential, inspectable stages:

```mermaid
flowchart LR
    A["ELIGIBILITY"] --> B["SYNC_CHECK"]
    B --> C["SNAPSHOT_CHECK"]
    C --> D["ROLLUP_CHECK"]
    D --> E["SIGNAL_CHECK"]
    E --> F["REPORT_CHECK"]
    F --> G["NARRATIVE_CHECK"]
    G --> H["COMPLETE"]
```

1. **`ELIGIBILITY`**: Evaluates tenant active status, configuration presence, approval flags, credential presence, and existing lock states.
2. **`SYNC_CHECK`**: Validates whether recent provider sync logs exist within the configured staleness window (`minimum_data_freshness_hours`).
3. **`SNAPSHOT_CHECK`**: Verifies coverage of `SocialMetricSnapshot` records across active platforms for the period.
4. **`ROLLUP_CHECK`**: Verifies daily/weekly/monthly `SocialMetricRollup` records exist for cross-platform calculations.
5. **`SIGNAL_CHECK`**: Verifies deterministic `BusinessSignal` records exist or are evaluable for the period.
6. **`REPORT_CHECK`**: Reuses existing `ExecutiveReport` or prepares deterministic synthesis.
7. **`NARRATIVE_CHECK`**: Reuses existing `VALIDATED` `ExecutiveNarrative` or checks LLM provider budget and approvals.
8. **`COMPLETE`**: Finalizes execution, updates duration, and releases locks.

---

## 5. Deterministic Period Calculator (`period.py`)

Reporting periods are calculated pure-functionally using timezone-aware calendar rules:
- **Tenant Timezone Aware**: Never relies on server UTC boundaries. Converts execution timestamps to tenant local time (e.g., `America/New_York`) prior to calculating start and end dates.
- **Calendar Month Mode (`MONTHLY`)**: Aligns with previous closed calendar months (e.g., execution on Oct 27 yields Sept 1 – Sept 30; execution on Nov 1 yields Oct 1 – Oct 31).
- **Rolling Window Mode**: Computes exact `[now - lookback_days, now]` intervals.
- **Weekly Mode (`WEEKLY`)**: Aligns with closed Monday–Sunday calendar weeks.
- **Daylight Saving Time (DST)**: Utilizes Python's `zoneinfo` module to correctly handle DST cutovers without boundary skew.

---

## 6. Measurable Freshness Engine (`freshness.py`)

Data freshness evaluates whether upstream platform syncs and snapshots are current enough for intelligence synthesis:

- **Metrics Evaluated**:
  - `active_credentials_count`: Number of active, unexpired platform OAuth credentials.
  - `last_sync_timestamp`: Most recent successful `SyncLog` across platforms.
  - `snapshots_in_period`: Total `SocialMetricSnapshot` rows within period boundaries.
  - `rollups_in_period`: Total `SocialMetricRollup` rows within period boundaries.
  - `age_hours`: Elapsed hours since the last successful sync.
- **Status Codes**:
  - `FRESH`: Data age is within `minimum_data_freshness_hours`.
  - `ACCEPTABLE`: Usable snapshots exist within lookback period.
  - `STALE`: Telemetry exceeds staleness threshold.
  - `NO_SYNC_LOGS`: No sync history recorded.
  - `NO_CREDENTIALS`: No active platform credentials found.

---

## 7. Pure Eligibility Engine & Safety Contract (`eligibility.py`)

A pure evaluation function `evaluate_intelligence_automation_eligibility(...)` inspects tenant state and produces an `EligibilityResult`.

### 7.1 Data Eligibility vs. Execution Authorization Semantics
To prevent ambiguous interpretations where `eligible=True` might be misconstrued as unrestricted execution permission, the engine explicitly distinguishes between:
1. **`data_eligible`**: Indicates whether upstream telemetry, platform credentials, metric snapshots, and period definitions are complete and sufficient for intelligence calculations.
2. **`execution_authorized`**: Indicates whether the execution has explicit operational authorization under its trigger context.
   - For `SCHEDULED` triggers: requires tenant configuration `enabled=True` AND approval satisfied (`require_operator_approval=False` or explicit pre-authorization).
   - For `MANUAL` / `ADMIN` triggers: requires active tenant and zero structural blockers.
3. **`status` / `eligible`**: Boolean composite indicator (`len(blocking_reasons) == 0`).
4. **`blocking_reasons`**: Deterministic list of unfulfilled gate codes.

### 7.2 Fail-Closed Checks
1. `CLIENT_INACTIVE`: Client model has `is_active=False`.
2. `CONFIG_MISSING`: No `IntelligenceAutomationConfig` exists for client (blocks `SCHEDULED`).
3. `AUTOMATION_DISABLED`: Config has `enabled=False` (blocks `SCHEDULED`).
4. `APPROVAL_REQUIRED`: Scheduled trigger attempted while `require_operator_approval=True`.
5. `NO_CREDENTIALS`: Tenant has 0 active platform credentials.
6. `DATA_STALE`: Telemetry age exceeds `minimum_data_freshness_hours` on scheduled runs.
7. `INSUFFICIENT_DATA`: Zero snapshots found for the requested period.
8. `BUDGET_EXCEEDED`: Narrative requested but provider call budget is 0.

### 7.3 Artifact Reuse Logic
- Checks if `ExecutiveReport` already exists for `(client_id, period_start, period_end)`.
- Checks if `ExecutiveNarrative` already exists for `report_id` with `status="VALIDATED"`.
- If existing artifacts are found, the planned stages skip generation and flag `REUSE`.

---

## 8. Activation Safety Contract & Force Policy

### 8.1 What `--force` Bypasses (Soft Operational Overrides Only)
The `--force` option in the management command is strictly an **operator override** for soft operational warnings during manual execution:
- Allows manual triggering when `IntelligenceAutomationConfig.enabled = False`.
- Allows manual dry-run evaluation when scheduled configuration is not yet active.

### 8.2 Inviolable Structural Safety Gates (Non-Bypassable by `--force`)
The following invariants CANNOT be bypassed under any circumstances:
- **Tenant Existence & Active Check**: Inactive tenants cannot be run.
- **Platform Credential Validity**: Active platform credentials are required.
- **Single-Flight Advisory Locking**: Concurrent duplicate executions are rejected.
- **Provider Call Budget**: Budget is hard-capped (0 in dry-run, strictly $\le$ `provider_call_budget` in live execution).
- **Duplicate VALIDATED Narrative Reuse**: Validated narratives are reused; no overwrite or second generation.
- **Database Active Run Constraint**: Database-level partial unique index prevents concurrent active rows.
- **Scheduled Run Isolation**: `SCHEDULED` Celery triggers cannot invoke `--force` and strictly enforce `enabled=True` and approval gates.


---

## 8. Single-Flight Concurrency Control (`locking.py`)

Distributed execution safety is achieved through dual-layer locking:
1. **PostgreSQL Session Advisory Locks (`pg_try_advisory_lock`)**:
   - Computes a signed 64-bit integer lock key from the first 8 bytes of the SHA-256 execution identity.
   - Provides non-blocking acquisition across competing Celery workers.
   - Automatically releases on transaction/session close or explicit release.
2. **Database Active Run Constraint**:
   - `IntelligenceAutomationRun` unique partial index prevents concurrent rows in `['PENDING', 'ELIGIBILITY_CHECK', 'RUNNING']`.

---

## 9. Observability & Safe Audit Logging (`events.py`)

All pipeline transitions produce structured audit events logged with structured JSON:
- **Event Types**:
  - `automation.run.started`
  - `automation.stage.transition`
  - `automation.eligibility.blocked`
  - `automation.run.blocked`
  - `automation.run.completed`
  - `automation.run.failed`
- **Secret Sanitization**:
  - Sensitive patterns (OAuth bearer tokens, access tokens, client secrets, API keys, passwords) are automatically scrubbed via regex matching before emission.

---

## 10. Operational Interface & Controlled Scheduler Pilot (BS-6B)

### 10.1 CLI Management Command
```bash
python manage.py run_intelligence_automation \
    --client 3 \
    --dry-run \
    --explain \
    --period-start 2026-09-22 \
    --period-end 2026-10-22
```

### 10.2 Celery Task Architecture & Pilot Activation (`tasks.py`)
- `discover_and_enqueue_due_intelligence_automations`: Periodic scanner task that inspects enabled tenant configurations and computes due status in tenant local time.
- **Pilot PeriodicTask**: `intelligence-automation-daily-discovery` (PeriodicTask ID #18).
  - Schedule: Daily at 03:00 UTC (`0 3 * * *`).
  - Function: Calls `discover_and_enqueue_due_intelligence_automations`.
  - Invariant: Does **not** directly call LLMs, Ollama, or third-party APIs. Only discovers and enqueues due tenant runs.
- `run_intelligence_automation_task`: Worker task that executes a single tenant's automation unit with advisory locking.

### 10.3 Pilot Tenant (Client #3) Configuration
- `enabled`: `True`
- `timezone`: `'America/New_York'`
- `reporting_frequency`: `'MONTHLY'` (Day 1 at 02:00 local time)
- `generate_report`: `True`
- `generate_narrative`: `True` (guarded by approval boundary)
- `require_operator_approval`: `True` (enforces fail-closed blocking of autonomous LLM generation)
- `max_data_staleness_hours`: `24`
- `provider_call_budget`: `1`
- `max_retry_count`: `0`

### 10.4 Approval Model Design & Future Evolution (BS-6C Roadmap)
In the current BS-6B baseline, operator approval is enforced at the config level (`require_operator_approval=True`). This produces `OPERATOR_APPROVAL_REQUIRED` on scheduled runs and blocks unapproved narrative generation.
For BS-6C, the approval model will evolve to support **run-level or stage-level approval**:
- A scheduled run executes data synthesis (stages 1-6) and transitions to `AWAITING_APPROVAL` at the narrative stage.
- An operator reviews the generated report in the dashboard and clicks "Approve Narrative Generation", which releases the stage lock for that specific `run_id` without requiring `require_operator_approval` to be permanently disabled on the config.

---

## 11. Verification Matrix

The test matrix validates all BS-6A, BS-6A.1, and BS-6B invariants across 9 dedicated test modules:
1. `test_intelligence_automation_models.py` (Models, choices, defaults, active constraints)
2. `test_intelligence_automation_period.py` (Timezones, calendar boundaries, DST transitions)
3. `test_intelligence_automation_eligibility.py` (Fail-closed gates, freshness rules, budget limits)
4. `test_intelligence_automation_idempotency.py` (Deduplication, artifact reuse, identity stability)
5. `test_intelligence_automation_locking.py` (PostgreSQL advisory locking, collision handling)
6. `test_intelligence_automation_orchestration.py` (Stage progression, dry-run neutrality)
7. `test_intelligence_automation_security.py` (Tenant isolation, secret redaction)
8. `test_intelligence_automation_safety_contract.py` (Data eligibility vs authorization, force limits)
9. `test_intelligence_automation_scheduler_pilot.py` (Discovery scanner, cadence, due calculation, gate blocking)

**Result**: 60 passed in 1.99s. Full backend test suite: **1,152 passed** in 131.8s with zero regressions. Frontend test suite: **32 suites, 282 tests passed** in 34.1s.
