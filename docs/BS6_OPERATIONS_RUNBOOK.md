# BS-6 Operations Runbook — Production Intelligence Automation

## 1. Scope & Purpose

This runbook provides operational instructions for managing, monitoring, triggering, and diagnosing the BOP Social Intelligence Automation subsystem across Phases **BS-6A, BS-6B, and BS-6C**.

The automation pipeline deterministically coordinates:
```
Provider Sync Verification ──► Metric Snapshots ──► Metric Rollups ──► Business Signals ──► Executive Report ──► Approval Pause ──► Grounded Executive Narrative
```

---

## 2. Safety Invariants & Pre-Execution Checks

Before initiating any manual run, operator approval, or modifying automation configurations, verify the following invariants:

1. **Automation Status**: Recurring scheduling is disabled by default. Do **not** create or enable `PeriodicTask` schedules without operator authorization.
2. **Provider Budget**: Default provider call budget is `1` for live runs and strictly `0` for dry runs. Never elevate budgets beyond verified quotas.
3. **Approval Boundary (BS-6C)**: Tenants with `require_operator_approval=True` pause execution at the narrative generation boundary, transitioning to `AWAITING_APPROVAL` with `approval_status='PENDING'`. Advisory locks are released while awaiting decision.
4. **Active Credentials**: Operations query credentials safely without decrypting tokens unless live provider sync is explicitly authorized.
5. **No Unauthorized Provider Calls**: Under no circumstances should live Ollama, OpenAI, Gemini, or Anthropic provider calls be triggered outside controlled phases. In Phase BS-6C, approved resume stops strictly at `PROVIDER_EXECUTION_READY`.

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

#### Example (Canonical Client #3):
```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py run_intelligence_automation \
    --client 3 \
    --dry-run \
    --explain \
    --period-start 2026-09-22 \
    --period-end 2026-10-22
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

### 3.4 Run-Level Approval Operations (BS-6C)

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

# Resume an approved run up to provider boundary
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py approve_intelligence_run \
    --run <RUN_ID> \
    --resume

# Combined Approve & Resume in a single command
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py approve_intelligence_run \
    --run <RUN_ID> \
    --comment "Operator approval" \
    --resume
```

#### REST API Endpoints
All approval endpoints require authentication and operator permissions:
- `POST /api/analytics/automation/runs/<run_id>/approve/`
  - Body: `{"comment": "Approved for delivery"}`
  - Response: `{"success": true, "run_id": 42, "approval_status": "APPROVED", ...}`
- `POST /api/analytics/automation/runs/<run_id>/reject/`
  - Body: `{"comment": "Rejected due to data revision"}`
  - Response: `{"success": true, "run_id": 42, "status": "CANCELLED", "approval_status": "REJECTED", ...}`
- `POST /api/analytics/automation/runs/<run_id>/resume/`
  - Response: `{"success": true, "run_id": 42, "status": "PROVIDER_EXECUTION_READY", "would_call_provider": true, "provider_call_count": 0, ...}`

#### Django Admin Actions
Under `/admin/social_stats/intelligenceautomationrun/`:
- Operators can filter by `Approval Status` (`PENDING`, `APPROVED`, `REJECTED`, `NOT_REQUIRED`).
- Bulk actions available:
  - **Approve selected intelligence runs**
  - **Reject selected intelligence runs**

---

## 4. Tenant Configuration Management

Configurations can be inspected or updated via Django shell or Django Admin (`/admin/social_stats/intelligenceautomationconfig/`).

### 4.1 Inspecting Tenant Config
```python
from social_stats.models import IntelligenceAutomationConfig
config = IntelligenceAutomationConfig.objects.filter(client_id=3).first()
if config:
    print(f"Enabled: {config.enabled}")
    print(f"Timezone: {config.timezone}")
    print(f"Cadence: {config.reporting_frequency} on day {config.reporting_day} at {config.reporting_hour}:00")
    print(f"Freshness Window: {config.minimum_data_freshness_hours}h")
    print(f"Approval Required: {config.require_operator_approval}")
```

### 4.2 Safe Tenant Onboarding
To safely configure automation for a client without enabling recurring runs:
```python
from social_stats.models import Client, IntelligenceAutomationConfig

client = Client.objects.get(id=3)
config, created = IntelligenceAutomationConfig.objects.get_or_create(
    client=client,
    defaults={
        "enabled": False,  # Keep disabled until rollout
        "timezone": "America/New_York",
        "reporting_frequency": "MONTHLY",
        "reporting_day": 1,
        "reporting_hour": 2,
        "lookback_days": 30,
        "minimum_data_freshness_hours": 48,
        "generate_report": True,
        "generate_narrative": True,
        "require_operator_approval": True,  # Pauses safely before narrative
        "provider_call_budget": 1,
        "max_retry_count": 0,
    }
)
```

---

## 5. Monitoring, Diagnostics & Scheduler Operations

### 5.1 Periodic Discovery Scanner Cadence & Timezone Handling
The periodic discovery scanner (`discover_and_enqueue_due_intelligence_automations`) runs every 15 minutes (`*/15 * * * *` UTC) via PeriodicTask `intelligence-automation-discovery` (ID #18).
- **Timezone Independence**: The 15-minute global tick inspects each tenant's local time (`get_tenant_local_datetime`) and threshold (`is_tenant_due`). A tenant configured for 02:00 local time will be detected on the first scanner tick after 02:00 local time arrives, regardless of UTC offset or daylight saving time cutover.
- **Missed-Tick Recovery**: If Celery Beat or workers experience downtime during a tenant's due window, the next scanner cycle evaluates `local_now >= due_threshold` and processes the due period immediately.
- **Row-Storm & Duplicate Protection**:
  - The scanner computes a material `block_state_hash` for any tenant whose prior attempt ended in `BLOCKED`.
  - The scanner explicitly ignores tenants that currently have an active run in `['PENDING', 'ELIGIBILITY_CHECK', 'RUNNING', 'AWAITING_APPROVAL']`. An approval-pending run holds active uniqueness at the database level, preventing spurious concurrent runs across all 96 daily scans.

### 5.2 Querying Recent Automation Runs & Approval States
```python
from social_stats.models import IntelligenceAutomationRun

runs = IntelligenceAutomationRun.objects.filter(client_id=3).order_by("-started_at")[:5]
for r in runs:
    print(f"Run #{r.id} | Status: {r.status} | Approval: {r.approval_status} | Stage: {r.current_stage} | Token: {r.approval_token[:10]}...")
```

### 5.3 Checking Distributed Locks
If an execution is unexpectedly blocked on `CONCURRENCY_LOCK_ACTIVE`:
```sql
-- Check active Postgres advisory locks
SELECT pid, locktype, mode, granted, objid
FROM pg_locks
WHERE locktype = 'advisory';
```

Note: Runs in `AWAITING_APPROVAL` status **must not** retain advisory locks. If an advisory lock remains active while a run is waiting for approval, it indicates an abnormal worker hang rather than the approval pause.

---

## 6. Troubleshooting Common Blockers

| Error Code | Reason | Remediation |
|---|---|---|
| `CLIENT_INACTIVE` | Tenant client has `is_active=False` | Verify client subscription and active status in `Client` table. |
| `CONFIG_MISSING` | No `IntelligenceAutomationConfig` row exists | Create configuration row with safe defaults. |
| `AUTOMATION_DISABLED` | Config `enabled=False` on `SCHEDULED` run | Enable config when recurring automation milestone begins, or use `--trigger MANUAL`. |
| `APPROVAL_REQUIRED` | Config has `require_operator_approval=True` | Provide operator approval or execute via `--force`. In BS-6C, the run pauses in `AWAITING_APPROVAL`. |
| `NO_CREDENTIALS` | 0 active platform credentials found | Reconnect OAuth credentials in settings dashboard. |
| `DATA_STALE` | Last sync exceeds `minimum_data_freshness_hours` | Trigger provider sync task (`sync_all_client_stats`) before running automation. |
| `CONCURRENCY_LOCK_ACTIVE` | Duplicate run inflight or orphaned lock | Verify worker logs; ensure prior run completed; inspect advisory locks. |
| `BUDGET_EXCEEDED` | Provider call quota reached (`provider_call_count >= budget`) | Increase budget deliberately or reuse existing executive reports/narratives. |
| `APPROVAL_STATE_INVALID` | Attempted approval/rejection on run not in `AWAITING_APPROVAL` | Verify run status; ensure run was not already approved or rejected. |
| `APPROVAL_IDENTITY_MISMATCH` | Execution identity, period, or report ID changed between request and resume | Re-trigger clean run; approval tokens protect against stale material execution drift. |

---

## 7. Emergency Abort & Pilot Rollback Procedures

### 7.1 Emergency Abort Procedure
If an uncoordinated automated execution occurs:

1. **Stop Celery Beat**:
   ```bash
   docker stop agencyos-celery-beat-1
   ```
2. **Revoke Active Tasks**:
   ```python
   from dashboard.celery import app
   app.control.purge()
   ```
3. **Cancel Inflight and Approval-Pending Runs in Database**:
   ```python
   from social_stats.models import IntelligenceAutomationRun
   IntelligenceAutomationRun.objects.filter(
       status__in=["PENDING", "ELIGIBILITY_CHECK", "RUNNING", "AWAITING_APPROVAL"]
   ).update(status="CANCELLED", approval_status="REJECTED", error_code="OPERATOR_ABORT", error_message_safe="Aborted by operator")
   ```
4. **Verify Database Sentinels**: Confirm that baseline table counts remain invariant.

### 7.2 Pilot Rollback Procedure
If the controlled pilot activation needs to be safely reverted or disabled without data loss:

1. **Disable Client #3 Automation Config**:
   ```python
   from social_stats.models import IntelligenceAutomationConfig
   IntelligenceAutomationConfig.objects.filter(client_id=3).update(enabled=False)
   ```
2. **Disable Pilot Discovery PeriodicTask**:
   ```python
   from django_celery_beat.models import PeriodicTask
   PeriodicTask.objects.filter(name="intelligence-automation-discovery").update(enabled=False)
   ```
3. **Historical Run Immutability Invariant**:
   - Do NOT delete or modify existing `IntelligenceAutomationRun` rows. They serve as canonical immutable audit records.
4. **Zero Provider Impact**:
   - Rollback operations require zero external network or LLM calls.
