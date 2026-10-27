# BS-6 Operations Runbook — Production Intelligence Automation

## 1. Scope & Purpose

This runbook provides operational instructions for managing, monitoring, triggering, and diagnosing the BOP Social Intelligence Automation subsystem introduced in Phase **BS-6A**.

The automation pipeline deterministically coordinates:
```
Provider Sync Verification ──► Metric Snapshots ──► Metric Rollups ──► Business Signals ──► Executive Report ──► Grounded Executive Narrative
```

---

## 2. Safety Invariants & Pre-Execution Checks

Before initiating any manual run or modifying automation configurations, verify the following invariants:

1. **Automation Status**: Recurring scheduling is disabled by default. Do **not** create or enable `PeriodicTask` schedules without operator authorization.
2. **Provider Budget**: Default provider call budget is `1` for live runs and strictly `0` for dry runs. Never elevate budgets beyond verified quotas.
3. **Approval Boundary**: Tenants with `require_operator_approval=True` will reject autonomous `SCHEDULED` triggers.
4. **Active Credentials**: Operations query credentials safely without decrypting tokens unless live provider sync is explicitly authorized.

---

## 3. Operational CLI Commands

All operational tasks are managed via the Django management command `run_intelligence_automation`.

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

Expected output:
```text
=== Intelligence Automation Dry-Run Plan ===
Client: 3 (Bop Agencia)
Period: 2026-09-22 to 2026-10-22
Pipeline Version: bs6a-v1
Execution Identity: 5885cfa169f4ea5ab1572bc97d91ecab44fe2a3f769062eb45a75dbb13b73e5a
Trigger: MANUAL
Eligible: True
Status: BLOCKED / COMPLETE
Provider Call Budget: 0
Reuse Report: Yes (Report ID #2)
Reuse Narrative: Yes (Narrative ID #2)
Planned Stages:
  1. ELIGIBILITY: OK
  2. SYNC_CHECK: OK
  3. SNAPSHOT_CHECK: OK
  4. ROLLUP_CHECK: OK
  5. SIGNAL_CHECK: OK
  6. REPORT_CHECK: REUSE
  7. NARRATIVE_CHECK: REUSE
  8. COMPLETE: OK
[DRY-RUN] No changes were written to the database. Zero external provider calls made.
```

### 3.2 Controlled Manual Execution
To execute a controlled live run for a tenant:

```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py run_intelligence_automation \
    --client <CLIENT_ID> \
    --trigger MANUAL
```

### 3.3 Force Execution (Bypassing Approval Gate)
For operator-initiated overrides when `require_operator_approval=True`:

```bash
docker exec -e DJANGO_SETTINGS_MODULE=dashboard.settings agencyos-backend-1 python manage.py run_intelligence_automation \
    --client <CLIENT_ID> \
    --force
```

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
        "generate_narrative": False,  # Manual approval required
        "require_operator_approval": True,
        "provider_call_budget": 1,
        "max_retry_count": 0,
    }
)
```

---

## 5. Monitoring & Diagnostics

### 5.1 Querying Recent Automation Runs
```python
from social_stats.models import IntelligenceAutomationRun

runs = IntelligenceAutomationRun.objects.filter(client_id=3).order_by("-started_at")[:5]
for r in runs:
    print(f"Run #{r.id} | Status: {r.status} | Stage: {r.current_stage} | Error: {r.error_code} | DryRun: {r.dry_run}")
```

### 5.2 Checking Distributed Locks
If an execution is unexpectedly blocked on `CONCURRENCY_LOCK_ACTIVE`:
```sql
-- Check active Postgres advisory locks
SELECT pid, locktype, mode, granted, objid
FROM pg_locks
WHERE locktype = 'advisory';
```

Advisory locks automatically release when the acquiring connection closes. In the event of a hung worker, terminating the idle worker connection releases the lock cleanly:
```sql
SELECT pg_terminate_backend(<PID>);
```

---

## 6. Troubleshooting Common Blockers

| Error Code | Reason | Remediation |
|---|---|---|
| `CLIENT_INACTIVE` | Tenant client has `is_active=False` | Verify client subscription and active status in `Client` table. |
| `CONFIG_MISSING` | No `IntelligenceAutomationConfig` row exists | Create configuration row with safe defaults. |
| `AUTOMATION_DISABLED` | Config `enabled=False` on `SCHEDULED` run | Enable config when recurring automation milestone begins, or use `--trigger MANUAL`. |
| `APPROVAL_REQUIRED` | Config has `require_operator_approval=True` | Provide operator approval or execute via `--force`. |
| `NO_CREDENTIALS` | 0 active platform credentials found | Reconnect OAuth credentials in settings dashboard. |
| `DATA_STALE` | Last sync exceeds `minimum_data_freshness_hours` | Trigger provider sync task (`sync_all_client_stats`) before running automation. |
| `CONCURRENCY_LOCK_ACTIVE` | Duplicate run inflight or orphaned lock | Verify worker logs; ensure prior run completed; inspect advisory locks. |
| `BUDGET_EXCEEDED` | Provider call quota reached (`provider_call_count >= budget`) | Increase budget deliberately or reuse existing executive reports/narratives. |

---

## 7. Emergency Abort Procedure

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
3. **Cancel Inflight Runs in Database**:
   ```python
   from social_stats.models import IntelligenceAutomationRun
   IntelligenceAutomationRun.objects.filter(
       status__in=["PENDING", "ELIGIBILITY_CHECK", "RUNNING"]
   ).update(status="CANCELLED", error_code="OPERATOR_ABORT", error_message_safe="Aborted by operator")
   ```
4. **Verify Database Sentinels**: Confirm that baseline table counts remain invariant.
