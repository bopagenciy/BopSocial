# BOP SOCIAL — PHASE BS-3G.1A
## SCHEDULED PUBLISHING & CELERY TASK REGISTRATION HARDENING REPORT

### 1. Executive Summary
During runtime operations, Celery worker logs repeatedly logged errors indicating unregistered tasks dispatched by Celery Beat:
- `Received unregistered task of type 'social_stats.scheduler.process_scheduled_posts'`
- `Received unregistered task of type 'social_stats.scheduler.process_post_queues'`

In this phase (BS-3G.1A), the task registration and discovery pipeline between Celery Beat, Celery Worker, and Django configuration was audited and hardened. A two-layer deterministic task discovery architecture was implemented, logging and error handling were enriched, and a targeted 18-scenario automated test suite was established.

Zero live publications were performed, zero calls were made to Meta/Instagram/Facebook APIs, and all historical database records (UnifiedPost #1–#9, PlatformPublishLog #1–#9, MediaAsset #1–#6) were preserved with 100% integrity.

---

### 2. Root Cause Analysis
1. **Celery Worker Autodiscovery Mechanism**:
   `backend/dashboard/celery.py` invokes `app.autodiscover_tasks()`. By Django-Celery default, `autodiscover_tasks()` scans installed apps for a file named `tasks.py` (i.e. `social_stats/tasks.py`).
2. **Sub-Task Module Omission**:
   The tasks `process_scheduled_posts` and `process_post_queues` are defined in `backend/social_stats/scheduler.py` via `@shared_task(bind=True)`. Because `scheduler.py` (along with `inbox_tasks.py`, `competitor_tasks.py`, `notification_watchers.py`, `meta_capi_tasks.py`) was never imported during worker boot, Celery worker initialized its registry without discovering or registering those tasks.
3. **Beat Dispatch Mismatch**:
   Celery Beat (configured via `django_celery_beat.schedulers.DatabaseScheduler` and `settings.CELERY_BEAT_SCHEDULE`) read task entries named `'social_stats.scheduler.process_scheduled_posts'` and `'social_stats.scheduler.process_post_queues'` every minute and submitted them to the message broker. The worker, lacking the imports, raised a `KeyError` / unregistered task exception on every incoming message.

---

### 3. Hardening Solution

#### Layer 1: Global Celery Configuration (`settings.py`)
Configured `CELERY_IMPORTS` in `backend/dashboard/settings.py` so Celery workers explicitly load all background task modules upon worker startup:
```python
CELERY_IMPORTS = (
    'social_stats.tasks',
    'social_stats.scheduler',
    'social_stats.inbox_tasks',
    'social_stats.competitor_tasks',
    'social_stats.notification_watchers',
    'social_stats.meta_capi_tasks',
    'social_stats.whatsapp_tasks',
    'social_stats.security.tasks',
    'social_stats.security.privacy_tasks',
)
```

#### Layer 2: In-App Module Discovery (`tasks.py`)
Imported sub-task modules in `backend/social_stats/tasks.py` to guarantee task discovery whenever `social_stats.tasks` is autodiscovered:
```python
from . import scheduler  # noqa: F401
from . import inbox_tasks  # noqa: F401
from . import competitor_tasks  # noqa: F401
from . import notification_watchers  # noqa: F401
from . import meta_capi_tasks  # noqa: F401
from . import whatsapp_tasks  # noqa: F401
```

#### Layer 3: Resilient Scheduler Dispatch & Sanitized Logging (`scheduler.py`)
Enriched `process_scheduled_posts` and `_dispatch_queued_item` in `backend/social_stats/scheduler.py` with granular `try...except` exception boundaries and structured logging (`post_id`, `client_id`, `scheduled_at`, `queue_id`) to ensure that a dispatch failure on one item does not abort the processing of subsequent items in the batch.

---

### 4. Canonical Registered Task Names & Beat Alignment
| Beat Schedule Entry | Target Task Name | Cadence | Worker Registry Status |
| :--- | :--- | :--- | :--- |
| `composer-process-scheduled-posts` | `social_stats.scheduler.process_scheduled_posts` | `crontab(minute='*')` (every minute) | **REGISTERED** |
| `composer-process-post-queues` | `social_stats.scheduler.process_post_queues` | `crontab(minute='*')` (every minute) | **REGISTERED** |
| `inbox-sync-every-5min` | `social_stats.inbox_tasks.sync_inbox_for_all_clients` | `crontab(minute='*/5')` | **REGISTERED** |
| `snapshot-competitors-daily-3am` | `social_stats.competitor_tasks.snapshot_competitors` | `crontab(hour=3, minute=0)` | **REGISTERED** |
| `smart-notifications-hourly` | `social_stats.notification_watchers.run_smart_notifications` | `crontab(minute=15)` | **REGISTERED** |
| `ctwa-sync-active-campaigns-daily-2am` | `social_stats.meta_capi_tasks.sync_active_ctwa_campaigns` | `crontab(hour=2, minute=30)` | **REGISTERED** |

---

### 5. Governance, Concurrency & Idempotency Audit
1. **Scheduled Post Selection**:
   `UnifiedPost.objects.filter(status='scheduled', scheduled_at__lte=now).order_by('scheduled_at')[:200]`
   - Draft posts (`status='draft'`) are excluded.
   - Pending approval posts (`status='pending_approval'`) are excluded.
   - Already published posts (`status='published'`) are excluded.
   - Future posts (`scheduled_at > now`) are excluded.
2. **Idempotency & Concurrency Safety**:
   Before triggering asynchronous dispatch, an atomic database update claims the post:
   ```python
   with transaction.atomic():
       updated = UnifiedPost.objects.filter(id=post.id, status='scheduled').update(status='queued')
       if not updated:
           continue
   ```
   If concurrent scheduler workers run simultaneously or overlap ticks, only the first worker receives `updated == 1`. Subsequent workers receive `updated == 0` and skip the post, preventing double publication.
3. **Approval Gate Integration**:
   `publish_unified_post` enforces client-level approval rules. If `client.requires_approval` is active and the post has not been approved (`post.approved_by_id` is null and status is not already approved/scheduled), it is marked `pending_approval` and routed to the approver.
4. **Timezone Semantics**:
   - `scheduled_at` in `UnifiedPost` is stored as a timezone-aware UTC datetime.
   - `PostQueue` evaluation calculates cron fire times against `Client.timezone` (defaulting to UTC if unset), ensuring local business-hour compliance (e.g. 10:00 AM Bogota time).
5. **Worker Queue & Routing**:
   The Celery worker consumes the default `celery` queue. Scheduler tasks do not override queue routing and therefore dispatch cleanly to the default queue.

---

### 6. Automated Verification & Test Coverage
Created `backend/social_stats/tests/test_scheduled_publishing.py` with 18 comprehensive test scenarios:
1. `test_01_scheduler_tasks_registered`: Verifies both scheduler tasks are present in `celery_app.tasks`.
2. `test_02_task_names_match_beat_config`: Confirms exact string match with `CELERY_BEAT_SCHEDULE`.
3. `test_03_due_approved_post_dispatched`: Verifies due post is transitioned to `status='queued'` and dispatched.
4. `test_04_future_post_skipped`: Verifies future post is ignored.
5. `test_05_draft_post_skipped`: Verifies draft post is ignored.
6. `test_06_pending_approval_skipped`: Verifies pending approval post is ignored.
7. `test_07_published_post_skipped`: Verifies already published post is ignored.
8. `test_08_duplicate_scheduler_run_safe`: Verifies consecutive runs on same post do not double-dispatch.
9. `test_09_queue_processor_registered`: Verifies queue processor is registered and callable.
10. `test_10_queue_processor_empty_run_safe`: Verifies empty queues return 0 without error.
11. `test_11_queue_processor_eligible_item`: Verifies eligible queue item creates UnifiedPost and is marked used.
12. `test_12_already_processed_queue_item_skipped`: Verifies used queue item is not re-fired.
13. `test_13_dispatch_exception_handled`: Verifies broker dispatch errors do not crash scheduler loop.
14. `test_14_no_real_meta_calls`: Verifies no external HTTP calls are triggered during scheduler execution.
15. `test_15_no_historical_db_mutation`: Verifies test runner operates on isolated test DB.
16. `test_16_timezone_aware_comparison`: Verifies timezone-aware timestamp filtering.
17. `test_17_worker_queue_compatibility`: Verifies default queue compatibility between task and worker.
18. `test_18_beat_schedule_import_valid`: Verifies all tasks defined in `CELERY_BEAT_SCHEDULE` are importable.

**Test Run Results**:
- `test_scheduled_publishing.py`: **18 passed** (0.460s)
- `test_orchestrator.py`: **8 passed** (0.716s)
- `test_carousel_validation.py` + `test_instagram_story_media_routing.py` + `test_instagram_carousel_media_routing.py`: **61 passed** (1.769s)

---

### 7. Runtime Verification
- Worker status via `celery inspect registered`:
  `social_stats.scheduler.process_post_queues` : **REGISTERED**
  `social_stats.scheduler.process_scheduled_posts` : **REGISTERED**
- Worker live logs after restart: Zero unregistered task errors.
- Beat live logs: Successfully dispatches both tasks every minute without exception.
- Database state:
  - UnifiedPost: 9 (Posts #1–#9 preserved)
  - PlatformPublishLog: 9 (Logs #1–#9 preserved)
  - MediaAsset: 6
  - Video Assets: 1
  - Post #10 created: **0**
  - External Meta calls: **0**

---

### 8. Recommended Next Phase
With Celery scheduler registration hardened and validated at runtime, the platform is ready for **BS-3G.1B: Controlled Scheduled Post Publication Pilot** (e.g. scheduled single image or scheduled story with operator authorization).
