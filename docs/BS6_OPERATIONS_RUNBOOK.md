# BS-6 Operations Runbook — Production Intelligence Automation

## 1. Scope & Purpose

This runbook provides operational instructions for managing, monitoring, triggering, and diagnosing the BOP Social Intelligence Automation subsystem across Phases **BS-6A, BS-6B, BS-6C, and BS-6C.0A**.

The automation pipeline deterministically coordinates:
```
Provider Sync Verification ──► Metric Snapshots ──► Metric Rollups ──► Business Signals ──► Executive Report ──► Approval Pause ──► Provider Boundary ──► Grounded Executive Narrative
```

---

## 2. Safety Invariants & Pre-Execution Checks

Before initiating any manual run, operator approval, or modifying automation configurations, verify the following invariants:

1. **Automation Status**: Recurring scheduling is disabled by default. Do **not** create or enable `PeriodicTask` schedules without operator authorization.
2. **Provider Budget**: Default provider call budget is `1` for live runs and strictly `0` for dry runs. Never elevate budgets beyond verified quotas.
3. **Approval Boundary (BS-6C)**: Tenants with `require_operator_approval=True` pause execution at the narrative generation boundary, transitioning to `AWAITING_APPROVAL` with `approval_status='PENDING'`. Advisory locks are released while awaiting decision.
4. **Execution-Ready Contract (BS-6C.0A)**: When resumed, approved runs transition to `PROVIDER_EXECUTION_READY`. This status is active and protected by the database unique constraint and scheduler scanner, preventing duplicate enqueues across all 96 daily ticks.
5. **No Unauthorized Provider Calls**: Under no circumstances should live Ollama, OpenAI, Gemini, or Anthropic provider calls be triggered outside authorized phases. In Phase BS-6C.0A, all operations are offline and provider-free.

---

## 3. Operational CLI Commands

### 3.1 Dry-Run Execution (Zero Side Effects)
To inspect eligibility, freshness, period calculation, and planned stages without making any DB mutations or provider calls:

```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py run_intelligence_automation \
    --client <CLIENT_ID> \
    --dry-run \
    --explain
```

### 3.2 Controlled Manual Execution
To execute a controlled live run for a tenant:

```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py run_intelligence_automation \
    --client <CLIENT_ID> \
    --trigger MANUAL
```

### 3.3 Force Execution Policy (`--force`)
The `--force` option is strictly an **operator override** for soft operational warnings during manual diagnostic execution:
- **Allowed**: Permits manual command execution when `IntelligenceAutomationConfig.enabled = False`.
- **FORBIDDEN (Inviolable Gates)**: `--force` CANNOT bypass tenant isolation, missing platform credentials, PostgreSQL advisory locks, provider call budgets, duplicate VALIDATED narrative reuse, or active run database uniqueness.
- **Scheduled Prohibition**: The automated Celery scheduler (`run_intelligence_automation_task`) NEVER accepts or utilizes `--force`. Scheduled runs must strictly satisfy `enabled=True`.

### 3.4 Run-Level Approval Operations (BS-6C & BS-6C.0A)

When an automation run enters `AWAITING_APPROVAL`, authorized operators can approve, reject, or resume the run via CLI, REST API, or Django Admin.

#### CLI Commands
```bash
# Approve a run awaiting operator decision
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py approve_intelligence_run \
    --run <RUN_ID> \
    --comment "Approved monthly intelligence report narrative"

# Reject a run
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py approve_intelligence_run \
    --run <RUN_ID> \
    --reject \
    --comment "Rejection reason: delayed client meeting"

# Resume an approved run up to provider boundary (reaches PROVIDER_EXECUTION_READY)
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py approve_intelligence_run \
    --run <RUN_ID> \
    --resume
```

#### REST API Endpoints
All approval endpoints require authentication and operator permissions:
- `POST /api/analytics/automation/runs/<run_id>/approve/`
- `POST /api/analytics/automation/runs/<run_id>/reject/`
- `POST /api/analytics/automation/runs/<run_id>/resume/`
  - Resumes approved run up to provider boundary, returning `status="PROVIDER_EXECUTION_READY"` with `provider_call_count=0`.

---

## 4. Provider Boundary & Concurrency Control (BS-6C.0A)

### 4.1 State Machine
```
AWAITING_APPROVAL ──► [Approve] ──► [Resume] ──► PROVIDER_EXECUTION_READY ──► [Reserve] ──► PROVIDER_EXECUTING ──► COMPLETED
                                                        │                                      ▲
                                                        ▼                                      │
                                                   CANCELLED                                 FAILED
```

### 4.2 Active Unique Protection
`IntelligenceAutomationRun` enforces database-level uniqueness across:
- `PENDING`
- `ELIGIBILITY_CHECK`
- `RUNNING`
- `AWAITING_APPROVAL`
- `PROVIDER_EXECUTION_READY`
- `PROVIDER_EXECUTING`

A run parked in `PROVIDER_EXECUTION_READY` maintains active execution uniqueness. The periodic discovery scanner treats `PROVIDER_EXECUTION_READY` as active and skips re-enqueuing across all 96 daily scans.

### 4.3 Atomic Provider Reservation Protocol
Before ANY live provider call (Phase BS-6D):
1. Acquire PostgreSQL single-flight advisory lock (`SingleFlightLock(execution_identity)`).
2. Execute `select_for_update()` inside `transaction.atomic()`.
3. Verify `status == 'PROVIDER_EXECUTION_READY'` and `approval_status == 'APPROVED'`.
4. Re-verify approval token immutability (`compute_approval_token`).
5. Re-verify safety gates (client active, config enabled, credentials unexpired, telemetry fresh).
6. Re-verify narrative reuse race (if valid narrative appeared meanwhile, link it and mark `COMPLETED`).
7. Re-verify provider call budget (`provider_call_count < budget`).
8. Atomically transition to `PROVIDER_EXECUTING` and reserve call slot (`provider_call_count = 1`).

### 4.4 Crash Recovery & Ambiguity Policy
- **No Automatic Retry**: `max_retry_count = 0`.
- **Fail-Closed**: If a worker crashes before, during, or after a provider call, session advisory locks are automatically released by PostgreSQL.
- **Budget Protection**: Once reserved (`provider_call_count = 1`), subsequent runs cannot re-reserve without explicit operator intervention, guaranteeing **at-most-once** provider execution.

---

## 5. Monitoring & Diagnostics

### 5.1 Querying Recent Automation Runs & States
```python
from social_stats.models import IntelligenceAutomationRun

runs = IntelligenceAutomationRun.objects.filter(client_id=3).order_by("-started_at")[:5]
for r in runs:
    print(f"Run #{r.id} | Status: {r.status} | Approval: {r.approval_status} | Stage: {r.current_stage} | Calls: {r.provider_call_count}")
```

### 5.2 Checking Distributed Locks
If an execution is unexpectedly blocked on `CONCURRENCY_LOCK_ACTIVE`:
```sql
SELECT pid, locktype, mode, granted, objid
FROM pg_locks
WHERE locktype = 'advisory';
```
Note: Runs in `AWAITING_APPROVAL` and `PROVIDER_EXECUTION_READY` do **NOT** retain advisory locks.

---

## 6. Emergency Abort & Pilot Rollback Procedures

### 6.1 Emergency Abort Procedure
1. **Stop Celery Beat**:
   ```bash
   docker stop agencyos-celery-beat-1
   ```
2. **Revoke Active Tasks**:
   ```python
   from dashboard.celery import app
   app.control.purge()
   ```
3. **Cancel Active Runs in Database**:
   ```python
   from social_stats.models import IntelligenceAutomationRun
   IntelligenceAutomationRun.objects.filter(
       status__in=["PENDING", "ELIGIBILITY_CHECK", "RUNNING", "AWAITING_APPROVAL", "PROVIDER_EXECUTION_READY", "PROVIDER_EXECUTING"]
   ).update(status="CANCELLED", approval_status="REJECTED", error_code="OPERATOR_ABORT", error_message_safe="Aborted by operator")
   ```
4. **Verify Database Sentinels**: Confirm that baseline table counts remain invariant.

---

## 7. Phase BS-6D.0: Controlled Analytics Freshness Recovery & Pre-BS-6D.1 Checklist

### 7.1 Recovery Verification Procedure
Before approving a live provider call under BS-6D.1, the operator must verify that tenant analytics data is fresh (`< 24h` staleness):

```python
from django.utils import timezone
from datetime import timedelta
from social_stats.analytics.automation.freshness import evaluate_tenant_freshness
from social_stats.analytics.automation.eligibility import evaluate_intelligence_automation_eligibility

client_id = 3
now = timezone.now()
p_start = (now - timedelta(days=30)).date()
p_end = now.date()

freshness = evaluate_tenant_freshness(client_id, p_start, p_end, max_staleness_hours=24, now=now)
assert freshness.is_fresh, f"Data is not fresh: {freshness.code}"
assert freshness.data_age_hours < 24.0, f"Data age exceeds 24h: {freshness.data_age_hours}h"

elig = evaluate_intelligence_automation_eligibility(client_id, trigger_type="SCHEDULED", now=now)
assert elig.data_eligible, "Tenant data is not eligible"
assert elig.blocking_reasons == ["OPERATOR_APPROVAL_REQUIRED: automated recurring narrative generation requires operator approval"]
print("FRESHNESS RECOVERY VERIFIED: Sole blocker is OPERATOR_APPROVAL_REQUIRED.")
```

### 7.3 Secret Hygiene & Environment Configuration
In compliance with production security standards (SEC-02):
- **Never commit keys to source**: `FIELD_ENCRYPTION_KEYS` must be injected via container environment variables or `.env.docker` (which is `.gitignore`d).
- **Format**: Primary key first (used for all new writes), followed by comma-separated legacy keys (for decrypting historical credentials during rotation windows).
- **Sanitized Tests**: Synthetic tokens and dummy values in test suites must never mirror real provider token prefixes.

---

## 8. Phase BS-6D.0A: Pre-Live Execution Safety Gate Protocol

### 8.1 BS-6D.1 Trigger Contract
- **Trigger Type**: Strictly `MANUAL` / `ADMIN` controlled trigger.
- **Monthly Cadence Preserved**: The production configuration (`MONTHLY`, 1st of month at 02:00 AM America/New_York) remains untouched.
- **Fail-Closed Staleness Validation**: At the next monthly scheduled run (`2026-11-01T02:00:00-05:00`), data age without an intervening sync will be ~59.8h (>24h threshold), ensuring that the automation scheduler will safely fail closed unless a fresh synchronization occurs immediately prior to the execution window.
- **Deterministic Reporting Period**: The manual pilot run targets calendar month `2026-09-01` to `2026-09-30` (or rolling 30-day window ending with refreshed telemetry), ensuring that `ExecutiveReport` and `ExecutiveNarrative` do not exist, legitimately triggering the single authorized Ollama provider call.

---

## 9. Phase BS-6D.0B: Target-Period Coverage & Completeness Audit Protocol

### 9.1 Freshness vs Coverage Policy
Operational monitoring must maintain a strict separation between freshness and completeness:
1. **Freshness Metric**: Measures time since last provider sync (`finished_at`). Evaluates tenant data health relative to `max_data_staleness_hours` (e.g. 24h).
2. **Coverage Metric**: Measures availability of snapshots and rollups across the requested `[period_start, period_end]` date range.

### 9.2 September 2026 Telemetry Audit Summary
- **Expected Window**: `2026-09-01` to `2026-09-30` (30 calendar days).
- **Facebook Coverage**: 9 / 30 days (30.0%) across dates `2026-09-22` to `2026-09-30`. 21 days missing (`2026-09-01` to `2026-09-21`).
- **Instagram Coverage**: 0 / 30 days (0.0%).
- **Comparable Metrics**: 0 of 15 canonical metrics.
- **Signal Potential**: 1 signal (`PROVIDER_PARTIAL`), 0 multichannel signals.

### 9.3 Known Policy Gap
The automation engine previously lacked a target-period completeness rule (e.g., `minimum_coverage_percent = 80%`), which allowed September 2026 to appear eligible despite 70% missing data. This gap has been fully resolved by Phase BS-6D.0C.

---

## 10. Phase BS-6D.0C: Target-Period Completeness Safety Gate Protocol

### 10.1 Operational Gate Overview
Before authorizing live Ollama generation (`BS-6D.1`), the operator must verify that the target period meets the fail-closed coverage requirements. The system will reject execution if coverage falls below `minimum_period_coverage_percent` (default: 80%).

### 10.2 Inspecting Coverage via CLI
To inspect coverage and verify eligibility for a reporting period without mutating the database:

```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 \
  python manage.py run_intelligence_automation 3 \
  --period-start 2026-09-01 --period-end 2026-09-30 \
  --dry-run --explain
```

**Diagnostic Output Format**:
```
Target Period Coverage:
  - Overall Code: INSUFFICIENT
  - Primary Platform Coverage: 30.0% (Required: >= 80%)
  - Multichannel Complete: False
  - Expected Days: 30
  - Platform Breakdown:
    * facebook: 30.0% (9/30 days, 63 snapshots, 6 metrics) [Code: INSUFFICIENT]
    * instagram: 0.0% (0/30 days, 0 snapshots, 0 metrics) [Code: NO_DATA]
  - Warnings:
    * MONTH_ROLLUP_SAMPLE_DEFICIT: facebook month rollup has sample_count=10 < 30 expected days
    * PLATFORM_ZERO_COVERAGE: instagram has 0/30 days of data in period; cross-platform narrative claims are restricted
    * PLATFORM_PARTIAL_CAPABILITY: instagram operating in PARTIAL capability mode (0/15 metrics available)
```

### 10.3 Failure Modes and Remediation

| Failure Mode | CLI Error / Blocker | Cause | Remediation Procedure |
|---|---|---|---|
| **Zero Telemetry** | `TARGET_PERIOD_COVERAGE_INSUFFICIENT: 0 days of telemetry across all platforms` | No snapshots exist in the requested date range. | Run a targeted historical sync for the target range or adjust reporting period to synchronized dates. |
| **Partial / Sub-Threshold Coverage** | `TARGET_PERIOD_COVERAGE_INSUFFICIENT: platform 'facebook' temporal coverage 30.0% (9/30 days) is below minimum required 80%` | Only a subset of days was synchronized (e.g., 9 of 30 days). | 1. Execute backfill for missing dates (e.g. `2026-09-01` to `2026-09-21`).<br>2. Alternatively, target an overlapping period with full coverage (e.g., October MTD).<br>3. Lower threshold in `IntelligenceAutomationConfig` if business explicitly approves partial reporting. |
| **Zero Platform Coverage (Multichannel)** | Warning: `PLATFORM_ZERO_COVERAGE: instagram has 0/30 days` | One connected platform has 0 snapshots in period. | Tenant is restricted to single-platform narrative; multichannel signals will not be generated for unrepresented platform. |
| **Stale Telemetry with Complete Period** | `ANALYTICS_DATA_STALE: age > 24h` | Target period data is complete, but last sync was > 24h ago. | Execute a fresh synchronization (`sync_social_data`) to refresh provider status before scheduled run. |

### 10.4 Threshold Configuration
The minimum coverage threshold is stored on `IntelligenceAutomationConfig`:

```python
# To inspect current threshold:
config = IntelligenceAutomationConfig.objects.get(client_id=3)
print(config.minimum_period_coverage_percent)  # Default: 80

# To adjust threshold (e.g., for specialized tenant):
config.minimum_period_coverage_percent = 75
config.save(update_fields=["minimum_period_coverage_percent"])
```

### 10.5 Pre-Live Authorization Checklist
Before proceeding to Phase BS-6D.1 (First Live Ollama Generation):
- [x] Local and remote git branches aligned on `feature/bs-6a-production-intelligence-automation`.
- [x] Target-period coverage safety gate implemented and verified (`evaluate_target_period_coverage`).
- [x] Config schema updated with `minimum_period_coverage_percent` (default 80%).
- [x] All 18 coverage test matrix cases passing (100%).
- [x] Full backend regression passing: 1,249 tests passing, 0 failures, 0 errors.
- [x] September 2026 evaluated: fail-closed rejection confirmed (`TARGET_PERIOD_COVERAGE_INSUFFICIENT: 30.0% < 80%`).
- [x] October 2026 evaluated: sufficiency confirmed (Facebook 100.0%, overall PARTIAL, execution authorized).
- [x] Production database invariant: zero mutations across all 11 core tables.

---

## 11. Phase BS-6D.0D: Historical Coverage Recovery & Sync Provenance Protocol

### 11.1 Operational Provenance Separation
When operating analytics synchronizations:
- **`CURRENT`**: Standard operational sync for recent/rolling telemetry (e.g. daily scheduled sync). May advance `latest_sync_at` and reset the data staleness clock.
- **`HISTORICAL`**: Backfill for missing historical date ranges. Advances period coverage for the target dates, but **never** resets `latest_sync_at` or clears `ANALYTICS_DATA_STALE`.

### 11.2 Executing a Controlled Historical Sync
To recover missing telemetry for an incomplete historical period:

```python
from datetime import date
from social_stats.analytics.sync_service import sync_facebook_analytics

# Execute bounded historical sync
result = sync_facebook_analytics(
    client_id=3,
    since=date(2026, 9, 1),
    until=date(2026, 9, 21),
    sync_scope="HISTORICAL",
    dual_write=True,
)
```

### 11.3 Recomputing Rollups Post-Recovery
Always rebuild rollups bounded strictly to the recovered period:

```python
from datetime import date
from social_stats.analytics.rollups import build_rollups_for_client

build_rollups_for_client(
    client_id=3,
    platform="facebook",
    periods=("day", "week", "month"),
    start_date=date(2026, 9, 1),
    end_date=date(2026, 9, 30),
)
```

### 11.4 Verification Checklist Before Provider Generation
1. Check `evaluate_tenant_freshness(client_id=3)`: Verify `qualifying_sync_scope == 'CURRENT'` and `latest_sync_at` is unaffected by the backfill.
2. Check `evaluate_target_period_coverage(client_id=3, period_start, period_end)`: Verify `is_sufficient=True` ($\ge 80\%$).
3. If scheduled generation is planned: Ensure a fresh `CURRENT` sync is executed so `age < 24h`.





