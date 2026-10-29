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


