# BS-5 Multichannel Intelligence — Operations Runbook

## 1. System Overview & Architecture

### Purpose
The Multichannel Intelligence subsystem of Bop Social delivers deterministic, multi-platform analytics rollups, cross-platform business signals, executive reporting, and strictly grounded AI executive narratives across connected social platforms (Facebook and Instagram in v1).

### Architectural Invariants
1. **Deterministic Authority**: Metric comparisons, period rollups, and business signals are computed by pure Python deterministic functions. LLMs never compute metrics, totals, ranks, or deltas.
2. **Missing vs. Zero**: Missing or unavailable telemetry evaluates to `None` and comparison status `UNAVAILABLE`. It is never converted into an artificial `0.0`.
3. **Audience Limitation**: Followers and Page Likes represent raw audience capacity. They are strictly volume gauges (`ComparisonDirection.NEUTRAL`) and never imply competitive efficiency or outperformance.
4. **Volume vs. Efficiency**: Reactions, comments, and shares are volume metrics. Cross-platform comparisons must not fabricate percentage shifts when baseline values are zero or components are unavailable.
5. **Non-Comparable Metrics**: Metrics with divergent provider semantics (`SAVES`, `REACH`, `VIDEO_VIEWS`, `ENGAGEMENT_TOTAL`) evaluate to `NON_COMPARABLE` or `UNAVAILABLE` under degraded modes (`Instagram PARTIAL`).
6. **Strict Gating**: Live AI narrative generation operates under `single_attempt_strict` (`MAX_PROVIDER_CALLS = 1`, `fallback_enabled = False`). Automatic retries and speculative completions are forbidden.
7. **Multi-Tenant Isolation**: All operations, queries, and APIs strictly filter by `client_id`. Cross-tenant data access is blocked at the ORM and API middleware layers.

```
                           ┌────────────────────────┐
                           │ SocialMetricSnapshot   │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │  SocialMetricRollup    │
                           └───────────┬────────────┘
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          ┌────────────────────┐               ┌───────────────────┐
          │ Metric Compatibility│               │  BusinessSignal   │
          │ Registry (15 rules)│               │  Engine (IDs 6-9) │
          └──────────┬─────────┘               └─────────┬─────────┘
                     │                                   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │   ExecutiveReport      │
                           │   - Multi-Platform     │
                           │   - ReportLab PDF      │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │ Grounded Narrative Ctx │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │  Ollama / qwen3.5:9b   │
                           │  (Composed Delivery)   │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │ Deterministic Validator│
                           │ (8 Safety Gates)       │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │   ExecutiveNarrative   │
                           │   - Status: VALIDATED  │
                           └───────────┬────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │ REST API & Frontend UI │
                           └────────────────────────┘
```

---

## 2. Preflight Verification & Health Check

Before performing any operational task or executing controlled narrative generation, verify system health:

### Step 1: Container Runtime Health
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
Verify `agencyos-backend-1`, `agencyos-postgres-1`, and `agencyos-redis-1` are `healthy` or `Up`.

### Step 2: Django System Check
```bash
docker exec agencyos-backend-1 python manage.py check
```
Expected output:
```text
System check identified no issues (0 silenced).
```

### Step 3: Canonical Database Baselines
```bash
docker exec agencyos-backend-1 python manage.py shell -c "
from social_stats.models import (
    SocialMetricSnapshot, SocialMetricRollup, BusinessSignal,
    ExecutiveReport, ExecutiveNarrative, DailyMetric, PostMetric,
    SyncLog, UnifiedPost, PlatformPublishLog, PostQueue, QueuedItem
)
from django_celery_beat.models import PeriodicTask

print('Snapshots:', SocialMetricSnapshot.objects.count())
print('Rollups:', SocialMetricRollup.objects.count())
print('Signals:', BusinessSignal.objects.count())
print('Reports:', ExecutiveReport.objects.count())
print('Narratives:', ExecutiveNarrative.objects.count())
print('PeriodicTasks:', PeriodicTask.objects.count())
"
```
Baseline invariant values:
- `SocialMetricSnapshot`: 312
- `SocialMetricRollup`: 551
- `BusinessSignal`: 9 (4 multichannel signals: IDs 6, 7, 8, 9)
- `ExecutiveReport`: 2 (Report #2 is multichannel)
- `ExecutiveNarrative`: 2 (Narrative #2 is multichannel)
- `PeriodicTask`: 17

---

## 3. Operational Workflows

### 3.1 Controlled Live Narrative Generation (Operator-Gated)

Live narrative generation consumes LLM resources and must follow the single-attempt controlled execution procedure.

```python
# Execution inside agencyos-backend-1 container:
from social_stats.models import ExecutiveReport
from social_stats.analytics.narrative.service import generate_and_save_narrative
from social_stats.analytics.narrative.schemas import GENERATION_POLICY_SINGLE_ATTEMPT_STRICT

report = ExecutiveReport.objects.get(id=2)

narrative = generate_and_save_narrative(
    report=report,
    provider_name="ollama",
    mock_mode="VALID",
    generation_policy=GENERATION_POLICY_SINGLE_ATTEMPT_STRICT,
    fallback_enabled=False,
    force_regenerate=False,  # Enforces deduplication
)
```

**Execution Rules:**
1. `MAX_PROVIDER_CALLS` is hard-limited to 1.
2. `fallback_enabled` must be `False`.
3. If an identical `VALIDATED` narrative exists (matching `source_hash`, `context_hash`, `prompt_version`, and `provider`), deduplication returns the existing instance without creating a new database row.
4. If validation fails, `ControlledLiveExecutionError` is raised, rolling back any changes and preventing persistence.

### 3.2 Report Preview (Zero DB Mutation)

To test narrative generation or inspect model responses without persisting to the database:

```python
from social_stats.models import ExecutiveReport
from social_stats.analytics.narrative.service import preview_narrative

report = ExecutiveReport.objects.get(id=2)
preview = preview_narrative(
    report=report,
    provider_name="ollama",
    mock_mode="VALID",
)
print("Valid:", preview["is_valid"])
print("Summary:", preview["val_summary"])
```

### 3.3 Re-generating Executive Report PDF

If ReportLab PDF rendering needs to be tested or generated:

```python
from social_stats.models import ExecutiveReport
from social_stats.reports import generate_executive_pdf

report = ExecutiveReport.objects.get(id=2)
pdf_bytes = generate_executive_pdf(report)
print("PDF Size:", len(pdf_bytes))
```
Note: Report #2 PDF checksum is `a5fdb32acc963542b40184dbd6045c7762fecccbad3cc51eb5c86f73b163945e`.

---

## 4. Troubleshooting & Incident Response

### Failure Matrix

| Symptom | Root Cause | Resolution |
| :--- | :--- | :--- |
| **`ConnectionRefusedError: Ollama endpoint unavailable`** | Ollama container/service is stopped or unreachable at `http://host.docker.internal:11434`. | Check host Ollama status via `curl http://localhost:11434/api/tags`. Ensure host port forwarding is open to container. |
| **`ControlledLiveExecutionError: Malformed JSON`** | Model emitted thinking tokens or markdown formatting outside JSON fences. | Verify `OllamaNarrativeProvider` strips `<think>` tags and extracts JSON from markdown blocks. Verify model is `qwen3.5:9b`. |
| **`Claim-scope lock failed`** | Model generated broad competitive claims (e.g. `ventaja competitiva`, `lidera en interacciones`). | Ensure prompt delivery fix (`compose_ollama_prompt`) is active and `bs5e-prompt-v3` system instructions are embedded in the prompt. |
| **`Stale Narrative Warning (is_stale = True)`** | `report.source_hash != narrative.source_hash`, indicating source rollup data changed after narrative generation. | Re-run controlled narrative generation with operator approval to synchronize narrative with updated report source hash. |
| **`Tenant Access 404 on API`** | User attempting to access report/narrative belongs to a different client ID. | Verify `request.user` client tenancy. Never bypass `get_queryset().filter(client=user.client)` tenant filter. |
| **`Division by Zero in Comparison`** | Cross-platform comparison calculated relative delta with a zero baseline. | Verify `safe_relative_delta()` returns `None` with reason code `ZERO_BASELINE`. |

### Stuck Background Task Recovery Procedure

If a background task or container process hangs:
1. Identify the task: `manage_task(Action='list')` or inspect running processes via `docker top agencyos-backend-1`.
2. Terminate the hung process safely:
   ```bash
   docker exec agencyos-backend-1 kill -TERM <PID>
   ```
3. Verify no orphaned python or test processes remain:
   ```bash
   docker exec agencyos-backend-1 ps aux | grep python
   ```
4. Verify database counts against the canonical baseline (Section 2, Step 3).

---

## 5. Security & Boundary Guarantees

1. **Zero Secret Leakage**:
   - Provider tokens, Ollama internal configs, and API keys are strictly excluded from API serialization and `ExecutiveNarrative.metadata`.
   - Logging outputs sanitise credentials and prompt payloads.
2. **Provider Isolation**:
   - No automatic provider sync tasks or recurring narrative jobs are enabled in Celery Beat.
   - All 17 `PeriodicTask` entries are accounted for and documented.
3. **Immutability of Validated Narratives**:
   - Once validated and persisted, `ExecutiveNarrative` instances are treated as immutable audit records bound to their specific `source_hash` and `context_hash`.
