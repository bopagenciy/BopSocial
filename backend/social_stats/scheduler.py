# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Composer scheduler — Celery beat tasks.

Two top-level tasks (registered in CELERY_BEAT_SCHEDULE in settings.py):

  process_scheduled_posts  — every minute. Picks UnifiedPost rows whose
    `scheduled_at` is in the past with status='scheduled' and dispatches
    them via the orchestrator.

  process_post_queues — every minute. Walks active PostQueue rows, evaluates
    their `schedule_rule` (cron expression) against `last_dispatched_at`,
    pulls the next QueuedItem according to `queue_strategy`, materializes it
    into a UnifiedPost, and queues for publishing.

BS-3G.2B Hardening:
  - Atomic row-level claim with select_for_update(skip_locked=True)
  - PostQueue row lock prevents same-cron-slot duplicate dispatches
  - Hybrid item-level approval policy (Policy D)
  - Pre-claim multi-platform media and cross-tenant validation
  - Durable bidirectional traceability (source_queue, source_queued_item)
  - Normalized hashtag materialization
  - Recoverable queued post state on Celery broker failure
  - Safe round-robin recycling with approval persistence
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from celery import shared_task
from croniter import croniter
from django.db import models, transaction
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import UnifiedPost, PostQueue, QueuedItem, MediaAsset
from .orchestrator import publish_unified_post
from .publishers import get_publisher

logger = logging.getLogger(__name__)


# ── Scheduled posts ───────────────────────────────────────────────────────────
@shared_task(bind=True)
def process_scheduled_posts(self):
    """Find scheduled UnifiedPosts whose time has come and dispatch them."""
    now = timezone.now()
    due = UnifiedPost.objects.filter(
        status='scheduled',
        scheduled_at__lte=now,
    ).order_by('scheduled_at')[:200]

    dispatched = 0
    for post in due:
        with transaction.atomic():
            updated = (UnifiedPost.objects
                       .filter(id=post.id, status='scheduled')
                       .update(status='queued', queued_at=now))
            if not updated:
                continue
        try:
            publish_unified_post.delay(post.id)
            dispatched += 1
            logger.info(
                'process_scheduled_posts: dispatched post_id=%s client_id=%s scheduled_at=%s',
                post.id, post.client_id, post.scheduled_at,
            )
        except Exception:
            logger.exception(
                'process_scheduled_posts: failed to dispatch post_id=%s client_id=%s',
                post.id, post.client_id,
            )

    if dispatched:
        logger.info('process_scheduled_posts dispatched %s posts', dispatched)
    return dispatched


# ── Recurring queues ──────────────────────────────────────────────────────────
@shared_task(bind=True)
def process_post_queues(self):
    """For each active queue, fire the next item if its cron slot is due."""
    fired = 0
    now = timezone.now()
    queue_ids = list(PostQueue.objects.filter(is_active=True).values_list('id', flat=True))

    for queue_id in queue_ids:
        try:
            if _process_single_queue(queue_id, now):
                fired += 1
        except Exception:
            logger.exception('process_post_queues: queue %s processing failed', queue_id)

    if fired:
        logger.info('process_post_queues dispatched %s queue items', fired)
    return fired


# ── Queued publication recovery watchdog ──────────────────────────────────────
@shared_task(bind=True)
def recover_orphaned_queued_posts(self, grace_seconds: int = 300) -> int:
    """
    Watchdog task to safely recover stranded UnifiedPost(status='queued') rows
    that were materialized in the database but never dispatched to Celery
    (e.g. broker connection failure during delay()).

    Safety boundaries:
      - Only status='queued'
      - Age >= grace_seconds (default: 300s / 5min)
      - select_for_update(skip_locked=True)
      - client.is_active is True
      - Approval state valid (if requires_approval, must have approved_by & approved_at)
        Otherwise transitioned to pending_approval and approver notified
      - Zero PlatformPublishLog rows (post never entered publish_unified_post execution)
      - Never touches status='publishing', 'published', 'partial', 'failed'
      - Secondary Celery inspect check (fails open on inspect error, but DB remains authoritative)
      - Re-enqueues via publish_unified_post.delay(post.id)
      - Preserves QueuedItem and source relations; never creates duplicate posts
    """
    now = timezone.now()
    cutoff = now - timedelta(seconds=grace_seconds)

    # Coalesce queued_at -> scheduled_at -> created_at for robust age detection
    candidate_ids = list(
        UnifiedPost.objects
        .filter(status='queued')
        .annotate(effective_queued_at=Coalesce('queued_at', 'scheduled_at', 'created_at'))
        .filter(effective_queued_at__lte=cutoff)
        .order_by('effective_queued_at')
        .values_list('id', flat=True)[:100]
    )

    if not candidate_ids:
        return 0

    recovered = 0
    for post_id in candidate_ids:
        decision = _evaluate_and_recover_post(post_id, now, cutoff, grace_seconds)
        if decision == 'RECOVERED':
            recovered += 1

    if recovered:
        logger.info('recover_orphaned_queued_posts recovered %s orphaned posts', recovered)
    return recovered


def _evaluate_and_recover_post(
    post_id: int,
    now: datetime,
    cutoff: datetime,
    grace_seconds: int,
) -> str:
    """
    Evaluate a candidate queued post under row lock and redispatch if provably safe.
    Returns the decision string (RECOVERED, SKIPPED_*, DISPATCH_FAILED).
    """
    with transaction.atomic():
        post = (
            UnifiedPost.objects
            .select_for_update(skip_locked=True)
            .select_related('client')
            .filter(id=post_id, status='queued')
            .first()
        )
        if not post:
            # Row locked by another concurrent worker or already transitioned out of queued
            logger.debug(
                'recover_orphaned_queued_posts: candidate_post_id=%s recovery_decision=SKIPPED_LOCKED reason="row locked or status changed"',
                post_id,
            )
            return 'SKIPPED_LOCKED'

        effective_queued_at = post.queued_at or post.scheduled_at or post.created_at
        effective_age = (now - effective_queued_at).total_seconds() if effective_queued_at else 0.0

        # Guard 1: Age check
        if effective_age < grace_seconds:
            logger.info(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=SKIPPED_FRESH reason="age < grace_period" recovery_timestamp=%s dispatch_attempt_result=NONE',
                post.id, post.client_id, effective_age, post.queued_at, now.isoformat(),
            )
            return 'SKIPPED_FRESH'

        # Guard 2: Inactive tenant
        if not post.client.is_active:
            logger.warning(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=SKIPPED_INACTIVE_CLIENT reason="client is inactive" recovery_timestamp=%s dispatch_attempt_result=NONE',
                post.id, post.client_id, effective_age, post.queued_at, now.isoformat(),
            )
            return 'SKIPPED_INACTIVE_CLIENT'

        # Guard 3: Approval safety
        if post.client.requires_approval:
            if not (post.approved_by_id and post.approved_at):
                # Transition to pending_approval and notify approver
                post.status = 'pending_approval'
                post.save(update_fields=['status'])
                logger.warning(
                    'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                    'recovery_decision=SKIPPED_UNAPPROVED reason="missing approval; reverted to pending_approval" recovery_timestamp=%s dispatch_attempt_result=NONE',
                    post.id, post.client_id, effective_age, post.queued_at, now.isoformat(),
                )
                try:
                    from .notification_watchers import notify_approver_for_post
                    notify_approver_for_post.delay(post.id)
                except Exception as exc:
                    logger.warning(
                        'recover_orphaned_queued_posts: failed to dispatch approver notification for post_id=%s: %s',
                        post.id, exc,
                    )
                return 'SKIPPED_UNAPPROVED'

        # Guard 4: Zero PlatformPublishLog rows (must have 0 logs)
        has_logs = post.publish_logs.exists()
        if has_logs:
            # Check for any success log, publishing log, or platform_post_id
            suspicious_logs = post.publish_logs.filter(
                models.Q(status__in=['success', 'publishing']) |
                ~models.Q(platform_post_id='')
            ).exists()
            decision = 'SKIPPED_AMBIGUOUS' if suspicious_logs else 'SKIPPED_HAS_LOGS'
            logger.warning(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=%s reason="post has existing platform publish logs" recovery_timestamp=%s dispatch_attempt_result=NONE',
                post.id, post.client_id, effective_age, post.queued_at, decision, now.isoformat(),
            )
            return decision

        # Guard 5: Secondary Celery inspect check (fails open on inspect error/timeout)
        if _is_task_active_in_celery(post.id):
            logger.info(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=SKIPPED_AMBIGUOUS reason="active/reserved task detected in Celery" recovery_timestamp=%s dispatch_attempt_result=NONE',
                post.id, post.client_id, effective_age, post.queued_at, now.isoformat(),
            )
            return 'SKIPPED_AMBIGUOUS'

        # Safe to redispatch
        try:
            publish_unified_post.delay(post.id)
            logger.info(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=RECOVERED reason="stale queued orphan successfully redispatched" recovery_timestamp=%s dispatch_attempt_result=SUCCESS',
                post.id, post.client_id, effective_age, post.queued_at, now.isoformat(),
            )
            return 'RECOVERED'
        except Exception as exc:
            logger.exception(
                'recover_orphaned_queued_posts: candidate_post_id=%s client_id=%s effective_queued_age=%.1fs queued_at=%s '
                'recovery_decision=DISPATCH_FAILED reason="broker failure during redispatch: %s" recovery_timestamp=%s dispatch_attempt_result=FAILED',
                post.id, post.client_id, effective_age, post.queued_at, exc, now.isoformat(),
            )
            return 'DISPATCH_FAILED'


def _is_task_active_in_celery(post_id: int) -> bool:
    """
    Secondary non-authoritative sanity check using Celery inspect.
    Returns True if an active or reserved publish_unified_post task matching post_id is found.
    Fails open (returns False) on inspect timeout or error.
    """
    try:
        from dashboard.celery import app as celery_app
        insp = celery_app.control.inspect(timeout=0.5)
        if not insp:
            return False

        for task_dict in [insp.active(), insp.reserved(), insp.scheduled()]:
            if not task_dict:
                continue
            for worker_tasks in task_dict.values():
                for t in (worker_tasks or []):
                    if t.get('name') == 'social_stats.orchestrator.publish_unified_post':
                        args = t.get('args', [])
                        if args and args[0] == post_id:
                            return True
    except Exception:
        # Fails open per specification H
        pass
    return False


def _process_single_queue(queue_id: int, now: datetime) -> bool:
    """
    Process a single queue in its own isolated transaction with row-level locking.
    Returns True if an item was claimed, materialized and dispatched.
    """
    with transaction.atomic():
        # Lock queue row to ensure 1 claim per due cron slot across concurrent workers
        queue = (
            PostQueue.objects
            .select_for_update(skip_locked=True)
            .select_related('client')
            .filter(id=queue_id, is_active=True)
            .first()
        )
        if not queue:
            # Another worker is already processing this queue or it became inactive
            return False

        if not _queue_is_due(queue, now):
            return False

        item = _pick_and_claim_next_item(queue)
        if not item:
            # Empty queue or no approved items waiting (last_dispatched_at NOT advanced)
            return False

        # Media preflight & tenant isolation validation
        is_valid, reason = _preflight_check_item(queue, item)
        if not is_valid:
            logger.warning(
                'process_post_queues: preflight validation rejected queue_id=%s item_id=%s client_id=%s reason=%s',
                queue.id, item.id, queue.client_id, reason,
            )
            return False

        post = _dispatch_queued_item(queue, item, now)
        return post is not None


# ── Internals ─────────────────────────────────────────────────────────────────
def _queue_is_due(queue: PostQueue, now: datetime) -> bool:
    """
    A queue is due when its cron expression's next-fire-time after
    `last_dispatched_at` (or queue creation) is on or before `now`.
    """
    rule = (queue.schedule_rule or '').strip()
    if not rule:
        return False

    base_dt = queue.last_dispatched_at or queue.created_at or now
    tz = _client_tz(queue.client_id)
    try:
        cron = croniter(rule, base_dt.astimezone(tz))
    except (ValueError, KeyError):
        logger.warning('Bad schedule_rule on queue %s: %s', queue.id, rule)
        return False
    try:
        next_fire = cron.get_next(datetime)
    except Exception:
        logger.warning('Failed to compute next fire on queue %s: %s', queue.id, rule)
        return False

    if next_fire.tzinfo is None:
        next_fire = next_fire.replace(tzinfo=tz)
    return next_fire <= now.astimezone(tz)


def _client_tz(client_id) -> ZoneInfo:
    from .models import Client
    try:
        c = Client.objects.only('timezone').get(id=client_id)
        if c.timezone:
            return ZoneInfo(c.timezone)
    except (Client.DoesNotExist, ZoneInfoNotFoundError, Exception):
        pass
    return ZoneInfo('UTC')


def _pick_and_claim_next_item(queue: PostQueue) -> Optional[QueuedItem]:
    """
    Pull and lock the next eligible item according to strategy and Policy D approval.
    """
    waiting = queue.items.select_for_update(skip_locked=True).filter(status='waiting')
    if queue.client.requires_approval:
        waiting = waiting.filter(
            approved_by__isnull=False,
            approved_at__isnull=False,
        )

    strategy = (queue.queue_strategy or 'sequential')

    if strategy == 'random':
        return waiting.order_by('?').first()

    if strategy == 'round_robin':
        item = waiting.order_by('sort_order', 'id').first()
        if item:
            return item
        # Recycle used items back to waiting; preserve approval fields
        queue.items.filter(status='used').update(status='waiting', used_at=None, unified_post=None)
        recycled_waiting = queue.items.select_for_update(skip_locked=True).filter(status='waiting')
        if queue.client.requires_approval:
            recycled_waiting = recycled_waiting.filter(
                approved_by__isnull=False,
                approved_at__isnull=False,
            )
        return recycled_waiting.order_by('sort_order', 'id').first()

    # sequential (default)
    return waiting.order_by('sort_order', 'id').first()


def _pick_next_queued_item(queue: PostQueue) -> Optional[QueuedItem]:
    """Compatibility wrapper for testing and direct invocation."""
    return _pick_and_claim_next_item(queue)


def _preflight_check_item(queue: PostQueue, item: QueuedItem) -> tuple[bool, str]:
    """
    Validate queue item media, tenant boundaries, and target platform constraints
    BEFORE claim, materialization or dispatch.
    """
    platforms = queue.platforms or []
    if not platforms:
        return False, "Queue has no target platforms configured"

    media_type = _guess_media_type(item)
    media_urls = item.media_urls or []

    # 1. Resolve and validate media asset references
    asset_ids = []
    for u in media_urls:
        if isinstance(u, str) and u.startswith('asset:'):
            try:
                asset_ids.append(int(u.split(':', 1)[1]))
            except (ValueError, IndexError):
                pass

    assets = []
    if asset_ids:
        found_assets = list(MediaAsset.objects.filter(id__in=asset_ids))
        asset_map = {a.id: a for a in found_assets}
        for aid in asset_ids:
            if aid not in asset_map:
                return False, f"Media asset {aid} not found"
            a = asset_map[aid]
            if a.client_id != queue.client_id:
                return False, f"Media asset {aid} belongs to client {a.client_id}, not queue client {queue.client_id}"
            assets.append(a)

    # 2. Multi-platform validation across all target platforms
    from . import media_service
    for platform in platforms:
        # Check publisher support
        try:
            pub = get_publisher(platform)
            if not pub.supports(media_type):
                return False, f"Platform '{platform}' does not support media_type='{media_type}'"
        except NotImplementedError:
            return False, f"No publisher available for platform '{platform}'"
        except Exception as e:
            return False, f"Publisher error for platform '{platform}': {e}"

        # Platform media constraints
        if assets:
            if media_type == 'carousel':
                c_vr = media_service.validate_carousel_for_platform(assets, platform)
                if c_vr.errors:
                    return False, f"Carousel validation failed for {platform}: {'; '.join(c_vr.errors)}"
            else:
                for a in assets:
                    vr = media_service.validate_for_platform(a, platform, media_type)
                    if vr.errors:
                        return False, f"Asset #{a.id} validation failed for {platform}: {'; '.join(vr.errors)}"

    return True, ""


def _build_post_content(raw_content: str, hashtags: list) -> str:
    """
    Combine item content and clean hashtags.
    Preserves item content, appends clean deduplicated hashtags without double hashes.
    """
    content = (raw_content or '').rstrip()
    if not hashtags:
        return content

    clean_tags = []
    seen = set()
    for tag in hashtags:
        if not tag:
            continue
        tag_str = str(tag).strip()
        if not tag_str:
            continue
        while tag_str.startswith('#'):
            tag_str = tag_str[1:]
        if not tag_str:
            continue
        tag_str = f"#{tag_str}"
        lower_tag = tag_str.lower()
        if lower_tag not in seen:
            seen.add(lower_tag)
            clean_tags.append(tag_str)

    if not clean_tags:
        return content

    tag_block = ' '.join(clean_tags)
    if content:
        return f"{content}\n\n{tag_block}"
    return tag_block


def _dispatch_queued_item(queue: PostQueue, item: QueuedItem, now: Optional[datetime] = None) -> UnifiedPost:
    """
    Materialize a QueuedItem into a UnifiedPost with durable bidirectional traceability
    and approval audit fields, advance queue schedule, and dispatch to Celery.
    """
    if now is None:
        now = timezone.now()

    if item.unified_post_id is not None or item.status == 'used':
        raise ValueError(f"QueuedItem {item.id} is already materialized into UnifiedPost {item.unified_post_id}")

    content = _build_post_content(item.content, item.hashtags)
    media_type = _guess_media_type(item)
    requires_approval = queue.client.requires_approval

    with transaction.atomic():
        post = UnifiedPost.objects.create(
            client_id=queue.client_id,
            content=content,
            media_urls=item.media_urls or [],
            media_type=media_type,
            target_platforms=queue.platforms or [],
            status='queued',
            queued_at=now,
            ai_generated=False,
            approved_by=item.approved_by if requires_approval else None,
            approved_at=item.approved_at if requires_approval else None,
            source_queue=queue,
            source_queued_item=item,
        )
        item.status = 'used'
        item.used_at = now
        item.unified_post = post
        item.save(update_fields=['status', 'used_at', 'unified_post'])

        queue.last_dispatched_at = now
        queue.save(update_fields=['last_dispatched_at'])

    try:
        publish_unified_post.delay(post.id)
        logger.info(
            'process_post_queues: dispatched queue_id=%s item_id=%s post_id=%s client_id=%s',
            queue.id, item.id, post.id, queue.client_id,
        )
    except Exception as exc:
        logger.exception(
            'process_post_queues: broker dispatch failure for queue_id=%s item_id=%s post_id=%s client_id=%s: %s',
            queue.id, item.id, post.id, queue.client_id, exc,
        )

    return post


def _guess_media_type(item: QueuedItem) -> str:
    urls = item.media_urls or []
    if not urls:
        return 'text'
    if len(urls) > 1:
        return 'carousel'
    first = str(urls[0]).lower()
    if first.endswith(('.mp4', '.mov', '.webm', '.m4v')):
        return 'video'
    if first.startswith('asset:'):
        try:
            aid = int(first.split(':', 1)[1])
            asset = MediaAsset.objects.filter(id=aid).only('mime_type').first()
            if asset and asset.mime_type and asset.mime_type.startswith('video'):
                return 'video'
        except (ValueError, IndexError):
            pass
    return 'image'
