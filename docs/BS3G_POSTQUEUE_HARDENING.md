# BOP SOCIAL — PHASE BS-3G.2B
## POSTQUEUE CONCURRENCY, APPROVAL & TRACEABILITY HARDENING

**Repository:** `AgencyOS`  
**Branch:** `feature/bs-3c5-facebook-media-pilot`  
**Phase Target:** BS-3G.2B  
**Date:** October 21, 2026  
**Status:** **PASS / HARDENED / VERIFIED**

---

### 1. Executive Summary & Audit Findings

During Phase BS-3G.2A, an architectural audit of the PostQueue recurring dispatch pipeline revealed six critical governance and concurrency gaps:

1. **Concurrency Claim Gap:** `_pick_next_queued_item(queue)` performed an unlocked `.first()` read without database locking. Two overlapping Celery worker processes could claim the same `QueuedItem`, generating duplicate `UnifiedPost` rows and duplicate provider publications.
2. **Approval Governance Disconnect:** For tenants with `requires_approval=True`, `_dispatch_queued_item` generated a `UnifiedPost` in `queued` state with null approval fields. The orchestrator caught this and transitioned the post to `pending_approval`. However, the underlying `QueuedItem` had already been consumed (`used_at` set) and `queue.last_dispatched_at` had already advanced. Manual approval later triggered immediate publication outside of the intended recurring cron time slot.
3. **Early Item Consumption & Broker Risk:** `QueuedItem` was marked `status='used'` and `PostQueue.last_dispatched_at` was advanced before `publish_unified_post.delay()` completed. Broker failures (e.g., Redis outage or network hiccups) left the item consumed while publication was never queued or delivered, with no recovery mechanism.
4. **Traceability Gap:** `QueuedItem.unified_post` existed, but `UnifiedPost` lacked durable foreign keys to `source_queue` and `source_queued_item`. Deleting queues or items severed the audit trail.
5. **Hashtag Loss:** `QueuedItem.hashtags` were stored on the queue item but dropped during materialization into `UnifiedPost`.
6. **Media Preflight Gap:** Queue items were dispatched without multi-platform preflight or tenant ownership checks on referenced media assets.

Phase BS-3G.2B resolves all six vulnerabilities, establishing a deterministic, concurrency-safe, and approval-governed recurring publishing engine.

---

### 2. Approval Policy (Policy D: Hybrid / Pre-Approved Items)

The recurring publisher enforces **Policy D (Pre-Approved Items)**:

* **For tenants with `client.requires_approval = True`:**
  * Only items with canonical, explicit approval (`approved_by IS NOT NULL` and `approved_at IS NOT NULL`) are eligible for autonomous recurring dispatch.
  * Unapproved waiting items are safely skipped. The queue remains active, but `last_dispatched_at` is NOT advanced until an approved item is materialized.
  * Approval state is derived directly from `approved_by` and `approved_at` without redundant boolean flags.
* **For tenants with `client.requires_approval = False`:**
  * Explicit approval is not required; all items with `status='waiting'` are eligible for autonomous dispatch.
* **Approval Transfer:** Upon materialization, `QueuedItem.approved_by` and `QueuedItem.approved_at` are copied directly to `UnifiedPost.approved_by` and `UnifiedPost.approved_at`. The resulting post enters `status='queued'` with valid approval, bypassing unnecessary orchestrator re-approval.

---

### 3. Claim & Concurrency Locking Model

To guarantee slot idempotency and prevent duplicate dispatches under concurrent scheduler invocations:

1. **Queue-Level Slot Locking:**
   * Inside an atomic transaction, `PostQueue` is acquired via `select_for_update(skip_locked=True)`.
   * If a concurrent worker is already processing the queue, the lock is skipped immediately without blocking.
   * Before claiming any item, `_queue_is_due(queue, now)` is re-evaluated inside the transaction. If another worker recently dispatched the slot and advanced `last_dispatched_at`, the slot is recognized as already fulfilled and safely bypassed.
2. **Item-Level Row Locking:**
   * `QueuedItem` rows are queried using `select_for_update(skip_locked=True)` filtered by `status='waiting'` (and `approved_by__isnull=False` when required).
   * Two overlapping workers cannot select or claim the same queue item.
3. **Item-to-Post Uniqueness:**
   * A defensive check enforces `if item.unified_post_id is not None or item.status == 'used': raise ValueError(...)`.
   * Together with database row locking, this ensures a `QueuedItem` can materialize at most one `UnifiedPost` per lifecycle.

---

### 4. Lifecycle & Approval Invalidation

* **Content Edit Invalidation:** If a user edits an approved item's `content`, `media_urls`, or `hashtags`, `QueuedItem.save()` automatically nulls `approved_by` and `approved_at`, requiring re-approval before recurring publication.
* **Reorder Safety:** Modifying `sort_order` alone preserves existing approvals without re-approval requirements.
* **Queue Platform Change Safety:** If `PostQueue.platforms` changes, approvals on all waiting items in the queue are invalidated because content must be vetted against the updated target platforms.
* **Round Robin Evergreen Recycling:** In `round_robin` mode, when all items are consumed, items are recycled from `used` back to `waiting`. Existing approvals are preserved upon recycling unless the item payload is modified.

---

### 5. Media Preflight & Tenant Isolation

Before an item is claimed or materialized:
* **Tenant Isolation:** Referenced media assets (`asset:<id>`) must belong strictly to `queue.client_id`. Cross-tenant asset references are blocked.
* **Platform Validation:** All target platforms in `queue.platforms` are validated for publisher support of the inferred `media_type` (text, image, video, carousel).
* **Multi-Platform All-Pass Policy:** If any target platform fails preflight validation, the entire item is blocked. The item remains in `status='waiting'`, structured warnings are logged, and `last_dispatched_at` is NOT advanced.

---

### 6. Failure Recovery & Traceability

* **Broker Failure Resilience:**
  * Item materialization and queue advance occur inside an atomic transaction.
  * If `publish_unified_post.delay()` fails (e.g. Celery broker disconnect), the exception is caught and logged with structured metadata (`queue_id`, `item_id`, `post_id`, `client_id`).
  * The `UnifiedPost` remains stored in `status='queued'`, linked bidirectionally to `source_queue` and `source_queued_item`.
  * Subsequent scheduler ticks do not duplicate the post because the item is `status='used'` and the queue slot has advanced. The post is fully recoverable and auditable.
* **Durable Foreign Key Traceability:**
  * `UnifiedPost.source_queue` (`ForeignKey(PostQueue, SET_NULL, null=True, blank=True)`)
  * `UnifiedPost.source_queued_item` (`ForeignKey(QueuedItem, SET_NULL, null=True, blank=True)`)
  * If a queue or queued item is deleted, historical `UnifiedPost` rows are preserved with references nulled (`ON DELETE SET NULL`). Reverse lookup `queue.unified_posts` lists historical materialized posts.

---

### 7. Hashtag Materialization

* `QueuedItem.hashtags` are normalized (whitespace trimmed, missing `#` prepended, duplicate `#` stripped).
* Deduplication is case-insensitive.
* Normalized hashtags are appended cleanly to `UnifiedPost.content` separated by `\n\n` without modifying the original `QueuedItem.content`.

---

### 8. API & UI Governance

* **Approval Endpoints:**
  * `POST /api/composer/queues/{queue_id}/items/{item_id}/approve/` — Approves a waiting item; idempotent.
  * `POST /api/composer/queues/{queue_id}/items/{item_id}/revoke_approval/` — Revokes approval; rejects with HTTP 400 if item was already consumed.
  * `GET /api/composer/queues/{queue_id}/items/` — Returns ordered list of queue items with approval audit fields.
* **Frontend (`QueueManagerPage`):**
  * Displays queued items list with status (`waiting`, `used`, `skipped`), media indicators, and approval status badges (`Approved`, `Pending Approval`).
  * Provides one-click "Approve" and "Revoke" actions on eligible items.
  * Displays linked `Post #{id}` for consumed items.
  * Includes Move Up / Move Down reordering controls.
  * Features a Policy D governance notice in `CreateQueueModal`.

---

### 9. Test Verification & Results

A dedicated hardening test suite was implemented in `backend/social_stats/tests/test_post_queues_hardening.py` covering 39 test cases:

```
Ran 39 tests in 4.644s — OK
```

Combined scheduled publishing & post queue test execution:

```
Ran 69 tests in 6.900s — OK (0 failures, 0 errors)
```

Frontend unit and translation tests (`ContentPublishingTranslation.test.jsx`):

```
Test Suites: 1 passed, 1 total
Tests:       11 passed, 11 total
```

All 6 AgencyOS services remain healthy. Real DB baseline (10 posts, 10 logs, 6 assets, 0 queues, 0 items) is completely intact. Celery worker and beat verify natural empty cycles with 0 dispatches and 0 external Meta calls.
