# ============================================================================
#  Social Stats — BS-3H Publication Operations & Manual Recovery Console
# ============================================================================
"""
Publication Operations layer for Bop Social.

Provides deterministic recovery classification, attention signals, timeline
reconstruction, and operator-controlled safe recovery without direct database
or Celery intervention.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ActionLog, PlatformPublishLog, UnifiedPost
from .orchestrator import publish_unified_post
from .tenant_mixins import TenantScopedMixin

logger = logging.getLogger(__name__)


# ============================================================================
# 1. DETERMINISTIC RECOVERY CLASSIFICATION & ATTENTION
# ============================================================================

# ── BS-3I Platform Target States ─────────────────────────────────────────────
PLATFORM_NOT_TARGETED       = 'PLATFORM_NOT_TARGETED'
PLATFORM_SUCCESS            = 'PLATFORM_SUCCESS'
PLATFORM_FAILED_RETRYABLE   = 'PLATFORM_FAILED_RETRYABLE'
PLATFORM_AMBIGUOUS          = 'PLATFORM_AMBIGUOUS'
PLATFORM_PUBLISHING_ACTIVE  = 'PLATFORM_PUBLISHING_ACTIVE'
PLATFORM_PUBLISHING_STALLED = 'PLATFORM_PUBLISHING_STALLED'
PLATFORM_PENDING_SAFE       = 'PLATFORM_PENDING_SAFE'
PLATFORM_BLOCKED            = 'PLATFORM_BLOCKED'


def classify_platform_target(post: UnifiedPost, platform: str, log: Optional[PlatformPublishLog], now: Optional[datetime] = None) -> dict:
    """
    Evaluates individual platform target eligibility and retryability (BS-3I).
    Guarantees that platforms with external success evidence or ambiguity are non-retryable.
    """
    if now is None:
        now = timezone.now()

    targets = list(post.target_platforms or [])
    if platform not in targets:
        return {
            'platform': platform,
            'state': PLATFORM_NOT_TARGETED,
            'can_retry': False,
            'retry_ineligible_reason': f"Platform '{platform}' is not targeted by post",
            'is_immutable': False,
        }

    # Governance / active checks
    if not post.client.is_active:
        return {
            'platform': platform,
            'state': PLATFORM_BLOCKED,
            'can_retry': False,
            'retry_ineligible_reason': 'Tenant workspace is inactive',
            'is_immutable': False,
        }

    if post.client.requires_approval and not (post.approved_by_id and post.approved_at):
        return {
            'platform': platform,
            'state': PLATFORM_BLOCKED,
            'can_retry': False,
            'retry_ineligible_reason': 'Post requires approver sign-off',
            'is_immutable': False,
        }

    if not log:
        return {
            'platform': platform,
            'state': PLATFORM_PENDING_SAFE,
            'can_retry': False,
            'retry_ineligible_reason': 'Target has not been dispatched yet',
            'is_immutable': False,
        }

    # 1. Definitive Success Evidence -> Immutable
    if log.status == 'success' or bool(log.platform_post_id):
        return {
            'platform': platform,
            'state': PLATFORM_SUCCESS,
            'can_retry': False,
            'retry_ineligible_reason': 'Platform has already published successfully (immutable)',
            'is_immutable': True,
        }

    # 2. In-flight / Publishing
    if log.status == 'publishing':
        attempt_age = (now - log.attempted_at).total_seconds() if log.attempted_at else 0.0
        if attempt_age > 900:  # > 15 minutes without result
            return {
                'platform': platform,
                'state': PLATFORM_AMBIGUOUS,
                'can_retry': False,
                'retry_ineligible_reason': 'Publish attempt timed out with no platform confirmation; manual provider review required',
                'is_immutable': False,
            }
        return {
            'platform': platform,
            'state': PLATFORM_PUBLISHING_ACTIVE,
            'can_retry': False,
            'retry_ineligible_reason': 'Platform is actively publishing',
            'is_immutable': False,
        }

    # 3. Pending
    if log.status == 'pending':
        if log.attempted_at is None:
            return {
                'platform': platform,
                'state': PLATFORM_PENDING_SAFE,
                'can_retry': False,
                'retry_ineligible_reason': 'Platform is pending initial worker dispatch',
                'is_immutable': False,
            }
        # Pending with attempted_at set (e.g. rate-limited retry in Celery)
        return {
            'platform': platform,
            'state': PLATFORM_PUBLISHING_ACTIVE,
            'can_retry': False,
            'retry_ineligible_reason': 'Platform is queued for Celery rate-limit retry',
            'is_immutable': False,
        }

    # 4. Failed
    if log.status == 'failed':
        return {
            'platform': platform,
            'state': PLATFORM_FAILED_RETRYABLE,
            'can_retry': True,
            'retry_ineligible_reason': None,
            'is_immutable': False,
        }

    return {
        'platform': platform,
        'state': PLATFORM_AMBIGUOUS,
        'can_retry': False,
        'retry_ineligible_reason': f"Unrecognized log status '{log.status}'",
        'is_immutable': False,
    }

def classify_publication(post: UnifiedPost, now: Optional[datetime] = None) -> dict:
    """
    Deterministic operational classification layer considering:
      - UnifiedPost.status
      - queued_at, scheduled_at, created_at, published_at
      - PlatformPublishLog rows (status, attempted_at, platform_post_id)
      - target_platforms
      - approval governance
      - client status
      - provenance (source_queue, source_queued_item)
    """
    if now is None:
        now = timezone.now()

    post_status = post.status
    logs = list(post.publish_logs.all())
    log_count = len(logs)

    # ── A. Rollup / Terminal States ──────────────────────────────────────────
    if post_status == 'published':
        return {
            'classification': 'PUBLISHED_SUCCESS',
            'attention_required': False,
            'attention_reason': 'Post successfully published across all target platforms',
            'severity': 'INFO',
            'can_recover': False,
            'recovery_ineligible_reason': 'Published posts cannot be retried',
        }

    if post_status == 'failed':
        return {
            'classification': 'FAILED_TERMINAL',
            'attention_required': True,
            'attention_reason': 'All target platform publications failed; manual review or recomposition required',
            'severity': 'ERROR',
            'can_recover': False,
            'recovery_ineligible_reason': 'Failed posts cannot be automatically recovered; re-dispatching could duplicate provider side-effects',
        }

    if post_status == 'partial':
        return {
            'classification': 'PARTIAL_FAILURE',
            'attention_required': True,
            'attention_reason': 'Publication partially succeeded; one or more platforms failed',
            'severity': 'ERROR',
            'can_recover': False,
            'recovery_ineligible_reason': 'Partial publication cannot be generically retried to avoid duplicate publishing on successful platforms',
        }

    if post_status == 'pending_approval':
        return {
            'classification': 'PENDING_APPROVAL',
            'attention_required': True,
            'attention_reason': 'Post requires approver sign-off before publication',
            'severity': 'INFO',
            'can_recover': False,
            'recovery_ineligible_reason': 'Post is pending approval; approval cannot be bypassed',
        }

    if post_status in ('draft', 'scheduled'):
        return {
            'classification': 'NORMAL',
            'attention_required': False,
            'attention_reason': f"Post is in {post_status} state",
            'severity': 'INFO',
            'can_recover': False,
            'recovery_ineligible_reason': f'Post in status {post_status} is not queued for publication',
        }

    # ── B. Status 'publishing' ───────────────────────────────────────────────
    if post_status == 'publishing':
        has_ambiguous_provider = False
        has_stalled_task = False

        for log in logs:
            if log.status == 'publishing' and log.attempted_at:
                attempt_age = (now - log.attempted_at).total_seconds()
                if attempt_age > 900:  # > 15 minutes
                    if not log.platform_post_id:
                        has_ambiguous_provider = True
                    else:
                        has_stalled_task = True
            elif log.status == 'pending' and log.attempted_at is None:
                fanout_age = (now - (post.queued_at or post.created_at)).total_seconds()
                if fanout_age > 900:
                    has_stalled_task = True

        if has_ambiguous_provider:
            return {
                'classification': 'MANUAL_REVIEW_REQUIRED',
                'attention_required': True,
                'attention_reason': 'Provider acceptance cannot be determined safely from local state (publish attempt timed out without platform ID)',
                'severity': 'CRITICAL',
                'can_recover': False,
                'recovery_ineligible_reason': 'Provider response is ambiguous; manual inspection on social network is required',
            }

        if has_stalled_task:
            return {
                'classification': 'PUBLISHING_STALLED',
                'attention_required': True,
                'attention_reason': 'Publishing execution has been in progress for over 15 minutes without completing',
                'severity': 'WARNING',
                'can_recover': False,
                'recovery_ineligible_reason': 'Publishing tasks in-flight or stalled cannot be auto-recovered; worker status must be investigated',
            }

        return {
            'classification': 'PUBLISHING_ACTIVE',
            'attention_required': False,
            'attention_reason': 'Post is actively being dispatched to target platforms',
            'severity': 'INFO',
            'can_recover': False,
            'recovery_ineligible_reason': 'Post is currently actively publishing',
        }

    # ── C. Status 'queued' ───────────────────────────────────────────────────
    if post_status == 'queued':
        # Rule 1: Check logs existence
        if log_count > 0:
            has_success_or_id = any(
                l.status in ('success', 'publishing') or bool(l.platform_post_id)
                for l in logs
            )
            if has_success_or_id:
                return {
                    'classification': 'MANUAL_REVIEW_REQUIRED',
                    'attention_required': True,
                    'attention_reason': 'Post is queued but contains external platform publication evidence or platform ID',
                    'severity': 'CRITICAL',
                    'can_recover': False,
                    'recovery_ineligible_reason': 'Post contains platform logs indicating prior execution; auto-recovery blocked to prevent duplicates',
                }
            return {
                'classification': 'QUEUED_AMBIGUOUS',
                'attention_required': True,
                'attention_reason': 'Post is queued but has pre-existing platform log rows',
                'severity': 'WARNING',
                'can_recover': False,
                'recovery_ineligible_reason': 'Post already has PlatformPublishLog entries; manual audit required',
            }

        # Rule 2: Tenant active check
        if not post.client.is_active:
            return {
                'classification': 'MANUAL_REVIEW_REQUIRED',
                'attention_required': True,
                'attention_reason': 'Post is queued for an inactive tenant',
                'severity': 'WARNING',
                'can_recover': False,
                'recovery_ineligible_reason': 'Tenant client is inactive',
            }

        # Rule 3: Approval check
        if post.client.requires_approval and not (post.approved_by_id and post.approved_at):
            return {
                'classification': 'PENDING_APPROVAL',
                'attention_required': True,
                'attention_reason': 'Client requires approval but approval audit fields are missing',
                'severity': 'WARNING',
                'can_recover': False,
                'recovery_ineligible_reason': 'Missing approval signature on approval-requiring tenant',
            }

        # Rule 4: Effective age check (grace period: 300 seconds)
        effective_time = post.queued_at or post.scheduled_at or post.created_at
        effective_age = (now - effective_time).total_seconds() if effective_time else 0.0

        if effective_age >= 300:
            return {
                'classification': 'QUEUED_RECOVERABLE',
                'attention_required': True,
                'attention_reason': 'Publication is stranded in queue (no active task, zero logs); safe to recover',
                'severity': 'WARNING',
                'can_recover': True,
                'recovery_ineligible_reason': None,
                'effective_queued_age_seconds': effective_age,
            }
        else:
            return {
                'classification': 'QUEUED_FRESH',
                'attention_required': False,
                'attention_reason': 'Recently queued; awaiting standard worker pickup',
                'severity': 'INFO',
                'can_recover': False,
                'recovery_ineligible_reason': f'Queued within grace period ({effective_age:.1f}s < 300s)',
                'effective_queued_age_seconds': effective_age,
            }

    # Fallback
    return {
        'classification': 'NORMAL',
        'attention_required': False,
        'attention_reason': f'Status: {post_status}',
        'severity': 'INFO',
        'can_recover': False,
        'recovery_ineligible_reason': 'Unrecognized status',
    }


# ============================================================================
# 2. SOURCE PROVENANCE DETERMINATION
# ============================================================================

def get_source_provenance(post: UnifiedPost) -> dict:
    """Determine publication provenance without modifying queue records."""
    if post.source_queue_id or post.source_queued_item_id:
        return {
            'type': 'POST_QUEUE',
            'queue_id': post.source_queue_id,
            'queue_name': post.source_queue.name if post.source_queue else None,
            'queued_item_id': post.source_queued_item_id,
            'description': f"Recurring Queue: {post.source_queue.name if post.source_queue else f'#{post.source_queue_id}'}",
        }
    if post.scheduled_at:
        return {
            'type': 'SCHEDULED',
            'scheduled_at': post.scheduled_at.isoformat(),
            'description': f"Scheduled for {post.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}",
        }
    if post.approved_by_id:
        return {
            'type': 'APPROVAL',
            'approved_by': post.approved_by.username if post.approved_by else None,
            'approved_at': post.approved_at.isoformat() if post.approved_at else None,
            'description': 'Direct Approval Dispatch',
        }
    return {
        'type': 'DIRECT',
        'description': 'Immediate Composer Dispatch',
    }


# ============================================================================
# 3. TIMELINE RECONSTRUCTION
# ============================================================================

def get_publication_timeline(post: UnifiedPost) -> list[dict]:
    """Reconstruct unified operational timeline from DB timestamps and logs."""
    events = []

    # 1. Post creation
    if post.created_at:
        events.append({
            'timestamp': post.created_at.isoformat(),
            'event_type': 'post_created',
            'platform': None,
            'status': 'created',
            'source': 'composer',
            'description': f"Post created by {post.created_by.get_full_name() or post.created_by.username if post.created_by else 'system'}",
            'severity': 'info',
            'metadata': {'media_type': post.media_type},
        })

    # 2. PostQueue provenance
    if post.source_queue_id or post.source_queued_item_id:
        q_name = post.source_queue.name if post.source_queue else f"Queue #{post.source_queue_id}"
        events.append({
            'timestamp': (post.queued_at or post.created_at).isoformat(),
            'event_type': 'postqueue_materialized',
            'platform': None,
            'status': 'queued',
            'source': 'post_queue',
            'description': f"Materialized from {q_name} (Item #{post.source_queued_item_id or ''})",
            'severity': 'info',
            'metadata': {'queue_id': post.source_queue_id, 'item_id': post.source_queued_item_id},
        })

    # 3. Scheduled intent
    if post.scheduled_at:
        events.append({
            'timestamp': post.scheduled_at.isoformat(),
            'event_type': 'post_scheduled',
            'platform': None,
            'status': 'scheduled',
            'source': 'scheduler',
            'description': f"Scheduled for publication at {post.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}",
            'severity': 'info',
            'metadata': {'scheduled_at': post.scheduled_at.isoformat()},
        })

    # 4. Approval
    if post.approved_at:
        events.append({
            'timestamp': post.approved_at.isoformat(),
            'event_type': 'post_approved',
            'platform': None,
            'status': 'approved',
            'source': 'approval',
            'description': f"Approved by {post.approved_by.username if post.approved_by else 'authorized user'}",
            'severity': 'info',
            'metadata': {'approved_by_id': post.approved_by_id},
        })

    # 5. Queued timestamp
    if post.queued_at:
        events.append({
            'timestamp': post.queued_at.isoformat(),
            'event_type': 'post_queued',
            'platform': None,
            'status': 'queued',
            'source': 'orchestrator',
            'description': 'Dispatched to publication queue',
            'severity': 'info',
            'metadata': {'queued_at': post.queued_at.isoformat()},
        })

    # 6. ActionLog events (e.g. manual recovery or watchdog recovery)
    action_logs = ActionLog.objects.filter(
        client=post.client,
        object_type='UnifiedPost',
        object_id=str(post.id),
    ).order_by('created_at')

    for al in action_logs:
        events.append({
            'timestamp': al.created_at.isoformat(),
            'event_type': al.action,
            'platform': al.platform or None,
            'status': al.result,
            'source': al.actor.username if al.actor else 'system',
            'description': f"Action {al.action}: {al.result}",
            'severity': 'info' if al.result == 'success' else 'warning',
            'metadata': al.details or {},
        })

    # 7. PlatformPublishLogs
    for log in post.publish_logs.all():
        if log.attempted_at:
            events.append({
                'timestamp': log.attempted_at.isoformat(),
                'event_type': 'platform_attempt',
                'platform': log.platform,
                'status': 'publishing',
                'source': 'orchestrator',
                'description': f"Started publication attempt to {log.platform.capitalize()}",
                'severity': 'info',
                'metadata': {'platform': log.platform},
            })
        if log.completed_at:
            is_success = log.status == 'success'
            events.append({
                'timestamp': log.completed_at.isoformat(),
                'event_type': 'platform_completed',
                'platform': log.platform,
                'status': log.status,
                'source': 'provider',
                'description': (
                    f"Successfully published to {log.platform.capitalize()} (ID: {log.platform_post_id})"
                    if is_success else
                    f"Failed publishing to {log.platform.capitalize()}: {log.error_message or log.error_code or 'Unknown error'}"
                ),
                'severity': 'success' if is_success else 'error',
                'metadata': {
                    'platform_post_id': log.platform_post_id,
                    'platform_url': log.platform_url,
                    'error_code': log.error_code,
                    'error_message': log.error_message,
                },
            })

    # 8. Final published status
    if post.published_at:
        events.append({
            'timestamp': post.published_at.isoformat(),
            'event_type': 'post_published',
            'platform': None,
            'status': 'published',
            'source': 'orchestrator',
            'description': f"Terminal publication outcome: {post.status}",
            'severity': 'success' if post.status == 'published' else 'info',
            'metadata': {'status': post.status},
        })

    events.sort(key=lambda e: e['timestamp'])
    return events


# ============================================================================
# 4. SERIALIZATION
# ============================================================================

def serialize_publication_operation(post: UnifiedPost, now: Optional[datetime] = None) -> dict:
    """Full operational view serialization for a UnifiedPost."""
    if now is None:
        now = timezone.now()

    classification_info = classify_publication(post, now)
    source_info = get_source_provenance(post)

    # Multi-platform logs map
    logs_map = {log.platform: log for log in post.publish_logs.all()}
    target_platforms = list(post.target_platforms or [])

    platform_progress = []
    for p in target_platforms:
        log = logs_map.get(p)
        eval_res = classify_platform_target(post, p, log, now)
        platform_progress.append({
            'platform': p,
            'status': log.status if log else 'not_dispatched',
            'state': eval_res['state'],
            'can_retry': eval_res['can_retry'],
            'retry_ineligible_reason': eval_res['retry_ineligible_reason'],
            'is_immutable': eval_res.get('is_immutable', False),
            'attempted_at': log.attempted_at.isoformat() if log and log.attempted_at else None,
            'completed_at': log.completed_at.isoformat() if log and log.completed_at else None,
            'platform_post_id': log.platform_post_id if log else '',
            'platform_url': log.platform_url if log else '',
            'error_code': log.error_code if log else '',
            'error_message': log.error_message if log else '',
            'provider_container_id': log.provider_container_id if log else '',
            'provider_request_id': log.provider_request_id if log else '',
        })

    effective_time = post.queued_at or post.scheduled_at or post.created_at
    effective_age_sec = (now - effective_time).total_seconds() if effective_time else 0.0

    return {
        'id': post.id,
        'client': {
            'id': post.client_id,
            'name': post.client.name,
            'company': post.client.company,
            'is_active': post.client.is_active,
            'requires_approval': post.client.requires_approval,
        },
        'title': post.title,
        'content_preview': post.content[:150] if post.content else '',
        'media_urls': post.media_urls or [],
        'media_type': post.media_type,
        'target_platforms': target_platforms,
        'status': post.status,
        'scheduled_at': post.scheduled_at.isoformat() if post.scheduled_at else None,
        'queued_at': post.queued_at.isoformat() if post.queued_at else None,
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'created_at': post.created_at.isoformat() if post.created_at else None,
        'updated_at': post.updated_at.isoformat() if post.updated_at else None,
        'effective_age_seconds': round(effective_age_sec, 1),
        'source': source_info,
        'approval': {
            'requires_approval': post.client.requires_approval,
            'is_approved': bool(post.approved_by_id and post.approved_at),
            'approved_by': post.approved_by.username if post.approved_by else None,
            'approved_at': post.approved_at.isoformat() if post.approved_at else None,
        },
        'classification': classification_info,
        'platform_progress': platform_progress,
    }


# ============================================================================
# 5. CANONICAL SAFE MANUAL RECOVERY
# ============================================================================

def execute_safe_recovery(post_id: int, user) -> dict:
    """
    Operator-triggered recovery calling the canonical safe recovery boundary.
    Re-validates row lock, status, logs, approval, and tenant.
    """
    now = timezone.now()
    with transaction.atomic():
        post = (
            UnifiedPost.objects
            .select_for_update(of=('self',), skip_locked=True)
            .select_related('client')
            .filter(id=post_id)
            .first()
        )
        if not post:
            return {
                'success': False,
                'error': 'Post not found or currently locked by another worker',
                'status_code': 409,
            }

        classification_info = classify_publication(post, now)
        if not classification_info['can_recover']:
            return {
                'success': False,
                'error': f"Cannot recover publication: {classification_info['recovery_ineligible_reason'] or 'Not eligible'}",
                'classification': classification_info['classification'],
                'status_code': 400,
            }

        try:
            publish_unified_post.delay(post.id)
        except Exception as exc:
            logger.exception('execute_safe_recovery: broker failure for post %s: %s', post.id, exc)
            return {
                'success': False,
                'error': f'Broker failure during redispatch: {exc}',
                'status_code': 502,
            }

        ActionLog.objects.create(
            actor=user if user.is_authenticated else None,
            client=post.client,
            action='composer.manual_recovery',
            object_type='UnifiedPost',
            object_id=str(post.id),
            result='success',
            details={
                'classification': classification_info['classification'],
                'effective_queued_age_seconds': classification_info.get('effective_queued_age_seconds'),
            },
        )

        logger.info(
            'execute_safe_recovery: post_id=%s client_id=%s user=%s dispatched successfully',
            post.id, post.client_id, user.username if user.is_authenticated else 'system',
        )

        return {
            'success': True,
            'post_id': post.id,
            'detail': 'Publication successfully redispatched for publishing',
            'classification': classification_info['classification'],
            'status_code': 200,
        }


# ============================================================================
# 5B. CANONICAL SAFE PLATFORM RETRY (BS-3I)
# ============================================================================

def retry_failed_platform(post_id: int, platform: str, user=None) -> dict:
    """
    Canonical safe platform retry service (BS-3I).
    Exclusively retries the specified failed platform without replaying successful platforms.
    """
    now = timezone.now()
    with transaction.atomic():
        post = (
            UnifiedPost.objects
            .select_for_update(of=('self',), skip_locked=True)
            .select_related('client')
            .filter(id=post_id)
            .first()
        )
        if not post:
            return {
                'success': False,
                'error': 'Post not found or currently locked by another operation',
                'status_code': 409,
            }

        # 1. Tenant client active check
        if not post.client.is_active:
            return {
                'success': False,
                'error': 'Cannot retry platform publication: client workspace is inactive',
                'status_code': 400,
            }

        # 2. Approval governance
        if post.client.requires_approval and not (post.approved_by_id and post.approved_at):
            return {
                'success': False,
                'error': 'Cannot retry platform publication: post requires approval',
                'status_code': 400,
            }

        # 3. Target platforms validation
        targets = list(post.target_platforms or [])
        if platform not in targets:
            return {
                'success': False,
                'error': f"Platform '{platform}' is not targeted by this post ({targets})",
                'status_code': 400,
            }

        # 4. Target log state & lock
        log = (
            PlatformPublishLog.objects
            .select_for_update(of=('self',), skip_locked=True)
            .filter(unified_post=post, platform=platform)
            .first()
        )
        if not log:
            return {
                'success': False,
                'error': f"No publish log exists for platform '{platform}'",
                'status_code': 400,
            }

        target_eval = classify_platform_target(post, platform, log, now)
        if not target_eval['can_retry']:
            return {
                'success': False,
                'error': f"Cannot retry platform '{platform}': {target_eval['retry_ineligible_reason'] or 'State is not retryable'}",
                'state': target_eval['state'],
                'status_code': 400,
            }

        # Immutable check: any platform with success evidence must never be retried
        if log.status == 'success' or bool(log.platform_post_id):
            return {
                'success': False,
                'error': f"Platform '{platform}' has already published successfully and is immutable",
                'status_code': 400,
            }

        successful_platforms = [
            l.platform for l in post.publish_logs.all()
            if l.platform != platform and (l.status == 'success' or bool(l.platform_post_id))
        ]

        previous_status = log.status

        # Reset ONLY this platform log to pending
        log.status = 'pending'
        log.error_code = ''
        log.error_message = ''
        log.completed_at = None
        log.save(update_fields=['status', 'error_code', 'error_message', 'completed_at'])

        # Set parent post to publishing
        post.status = 'publishing'
        post.save(update_fields=['status'])

        # Dispatch ONLY this platform
        from .orchestrator import publish_to_platform
        try:
            publish_to_platform.delay(post.id, platform)
        except Exception as exc:
            logger.exception('retry_failed_platform: broker dispatch failure for post %s platform %s: %s', post.id, platform, exc)
            return {
                'success': False,
                'error': f'Broker failure during platform redispatch: {exc}',
                'status_code': 502,
            }

        # Audit log in ActionLog
        ActionLog.objects.create(
            actor=user if user and user.is_authenticated else None,
            client=post.client,
            action='composer.platform_retry',
            platform=platform,
            object_type='UnifiedPost',
            object_id=str(post.id),
            result='success',
            details={
                'platform': platform,
                'previous_status': previous_status,
                'untouched_successful_platforms': successful_platforms,
            },
        )

        return {
            'success': True,
            'post_id': post.id,
            'platform': platform,
            'detail': f"Platform '{platform}' successfully queued for retry; {len(successful_platforms)} successful platforms untouched",
            'untouched_platforms': successful_platforms,
            'status_code': 200,
        }


# ============================================================================
# 6. OPERATOR API VIEWS
# ============================================================================

class PublicationOperationsListView(TenantScopedMixin, APIView):
    """
    List and filter publication operations across the authenticated tenant.
    Supports filtering by status, platform, source_type, attention_required,
    recovery_classification, and sorting.
    """
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def get_queryset(self):
        return UnifiedPost.objects.all().select_related(
            'client', 'source_queue', 'source_queued_item', 'created_by', 'approved_by'
        ).prefetch_related('publish_logs')

    def get(self, request):
        qs = self.get_queryset()
        # TenantScopedMixin filter
        profile = self._profile()
        if not profile:
            return Response({'count': 0, 'results': []})

        f = self.client_field_name
        if profile.role == 'superadmin':
            cid = request.query_params.get('client_id')
            if cid:
                qs = qs.filter(**{f'{f}_id': cid})
        elif profile.role == 'staff':
            qs = qs.filter(**{f'{f}__in': profile.assigned_clients.all()})
        else:
            agency_ids = self._agency_client_ids(profile)
            if agency_ids:
                qs = qs.filter(**{f'{f}_id__in': agency_ids})
            elif profile.client_id:
                qs = qs.filter(**{f'{f}_id': profile.client_id})
            else:
                return Response({'count': 0, 'results': []})

        # Filter by status
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # Filter by platform
        platform_param = request.query_params.get('platform')
        if platform_param:
            qs = qs.filter(target_platforms__contains=[platform_param])

        # Filter by source_type
        source_type = request.query_params.get('source_type')
        if source_type == 'POST_QUEUE':
            qs = qs.filter(source_queue__isnull=False)
        elif source_type == 'SCHEDULED':
            qs = qs.filter(scheduled_at__isnull=False, source_queue__isnull=True)
        elif source_type == 'DIRECT':
            qs = qs.filter(scheduled_at__isnull=True, source_queue__isnull=True)

        # Filter by date range
        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        # Sorting
        sort = request.query_params.get('sort', '-created_at')
        if sort == 'longest_stuck':
            qs = qs.filter(status__in=['queued', 'publishing']).order_by('queued_at', 'created_at')
        elif sort in ('newest', '-created_at'):
            qs = qs.order_by('-created_at')
        elif sort in ('oldest', 'created_at'):
            qs = qs.order_by('created_at')
        elif sort == '-updated_at':
            qs = qs.order_by('-updated_at')
        else:
            qs = qs.order_by('-created_at')

        # Evaluate and filter by classification or attention_required if requested
        now = timezone.now()
        attention_param = request.query_params.get('attention_required')
        class_param = request.query_params.get('classification')

        items = []
        for post in qs:
            data = serialize_publication_operation(post, now)
            if attention_param is not None:
                want_attention = attention_param.lower() in ('true', '1', 'yes')
                if data['classification']['attention_required'] != want_attention:
                    continue
            if class_param and data['classification']['classification'] != class_param:
                continue
            items.append(data)

        # Pagination
        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page, page_size = 1, 20

        total_count = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        paged_items = items[start:end]

        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size if page_size else 1,
            'results': paged_items,
        })


class PublicationOperationsDetailView(TenantScopedMixin, APIView):
    """Detail view returning publication health, target progress, and guidance."""
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def get_queryset(self):
        return UnifiedPost.objects.all().select_related(
            'client', 'source_queue', 'source_queued_item', 'created_by', 'approved_by'
        ).prefetch_related('publish_logs')

    def get(self, request, pk: int):
        qs = self.get_queryset()
        # Tenant isolation check
        profile = self._profile()
        if not profile:
            return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        f = self.client_field_name
        if profile.role == 'superadmin':
            pass
        elif profile.role == 'staff':
            qs = qs.filter(**{f'{f}__in': profile.assigned_clients.all()})
        else:
            agency_ids = self._agency_client_ids(profile)
            if agency_ids:
                qs = qs.filter(**{f'{f}_id__in': agency_ids})
            elif profile.client_id:
                qs = qs.filter(**{f'{f}_id': profile.client_id})
            else:
                return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        post = qs.filter(id=pk).first()
        if not post:
            return Response({'detail': 'Publication not found'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        data = serialize_publication_operation(post, now)
        data['timeline'] = get_publication_timeline(post)

        # Operator Guidance Notes
        classification = data['classification']['classification']
        if classification == 'QUEUED_RECOVERABLE':
            guidance = "Safe for manual recovery. Publication was materialized but no Celery task exists and no provider calls were attempted. Clicking 'Recover Publication' will safely re-enqueue dispatch."
        elif classification == 'PUBLISHING_ACTIVE':
            guidance = "Publication is currently in-flight with workers. Allow standard queue processing to complete."
        elif classification == 'MANUAL_REVIEW_REQUIRED':
            guidance = "Provider ambiguity or historical logs detected. Do NOT re-dispatch without verifying external social network directly to prevent duplicate public posts."
        elif classification == 'PUBLISHING_STALLED':
            guidance = "Worker processing exceeded 15 minutes. Verify worker cluster health before taking action."
        elif classification == 'PARTIAL_FAILURE':
            guidance = "Some platforms succeeded while others failed. Generic retry is prohibited to protect successful platforms."
        elif classification == 'PUBLISHED_SUCCESS':
            guidance = "Publication succeeded across all target platforms."
        else:
            guidance = "Follow standard operational review procedures."

        data['operator_guidance'] = guidance
        return Response(data)


class PublicationOperationsRecoverView(TenantScopedMixin, APIView):
    """Controlled manual safe recovery endpoint."""
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def post(self, request, pk: int):
        # Tenant permission check
        post = UnifiedPost.objects.select_related('client').filter(id=pk).first()
        if not post:
            return Response({'detail': 'Publication not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = self._profile()
        if not profile:
            raise PermissionDenied('No profile found')

        # Check tenant access
        if profile.role != 'superadmin':
            if profile.role == 'staff':
                if not profile.assigned_clients.filter(id=post.client_id).exists():
                    raise PermissionDenied('Access denied to this tenant')
            else:
                agency_ids = self._agency_client_ids(profile)
                if agency_ids and post.client_id not in agency_ids:
                    raise PermissionDenied('Access denied to this tenant')
                elif not agency_ids and profile.client_id != post.client_id:
                    raise PermissionDenied('Access denied to this tenant')

        res = execute_safe_recovery(post.id, request.user)
        if not res['success']:
            return Response({'detail': res['error']}, status=res.get('status_code', 400))
        return Response(res, status=status.HTTP_200_OK)


class PublicationOrphansListView(TenantScopedMixin, APIView):
    """Quick view of all publications requiring operational attention."""
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def get(self, request):
        view = PublicationOperationsListView()
        view.request = request
        request.GET = request.GET.copy()
        request.GET['attention_required'] = 'true'
        return view.get(request)


class PublicationTimelineView(TenantScopedMixin, APIView):
    """Detailed timeline endpoint for a publication."""
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def get(self, request, pk: int):
        post = UnifiedPost.objects.select_related('client').filter(id=pk).first()
        if not post:
            return Response({'detail': 'Publication not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = self._profile()
        if not profile:
            raise PermissionDenied('No profile found')

        # Tenant boundary check
        if profile.role != 'superadmin':
            if profile.role == 'staff':
                if not profile.assigned_clients.filter(id=post.client_id).exists():
                    raise PermissionDenied('Access denied to this tenant')
            else:
                agency_ids = self._agency_client_ids(profile)
                if agency_ids and post.client_id not in agency_ids:
                    raise PermissionDenied('Access denied to this tenant')
                elif not agency_ids and profile.client_id != post.client_id:
                    raise PermissionDenied('Access denied to this tenant')

        timeline = get_publication_timeline(post)
        return Response({
            'post_id': post.id,
            'client_id': post.client_id,
            'timeline': timeline,
        })


class PublicationPlatformRetryView(TenantScopedMixin, APIView):
    """Controlled manual safe platform retry endpoint (BS-3I)."""
    permission_classes = [IsAuthenticated]
    client_field_name = 'client'

    def post(self, request, pk: int):
        post = UnifiedPost.objects.select_related('client').filter(id=pk).first()
        if not post:
            return Response({'detail': 'Publication not found'}, status=status.HTTP_404_NOT_FOUND)

        profile = self._profile()
        if not profile:
            raise PermissionDenied('No profile found')

        # Tenant boundary check
        if profile.role != 'superadmin':
            if profile.role == 'staff':
                if not profile.assigned_clients.filter(id=post.client_id).exists():
                    raise PermissionDenied('Access denied to this tenant')
            else:
                agency_ids = self._agency_client_ids(profile)
                if agency_ids and post.client_id not in agency_ids:
                    raise PermissionDenied('Access denied to this tenant')
                elif not agency_ids and profile.client_id != post.client_id:
                    raise PermissionDenied('Access denied to this tenant')

        platform = request.data.get('platform')
        if not platform or not isinstance(platform, str):
            return Response({'detail': "Missing or invalid 'platform' in request payload"}, status=status.HTTP_400_BAD_REQUEST)

        res = retry_failed_platform(post.id, platform.lower().strip(), user=request.user)
        if not res['success']:
            return Response({'detail': res['error']}, status=res.get('status_code', 400))
        return Response(res, status=status.HTTP_200_OK)
