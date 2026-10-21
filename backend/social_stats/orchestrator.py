# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Author    : Chandrabhan Shekhawat
#  Company   : Gigai Kripa Services
#  Website   : https://gigaikripaservices.com/
#  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
#  Released under the MIT License — see LICENSE. Keep this notice.
# ============================================================================
"""
Unified publishing orchestrator.

Two Celery tasks:
  - publish_unified_post(unified_post_id):
      Fan-out task: looks at the UnifiedPost's target_platforms, creates one
      PlatformPublishLog per platform, and dispatches publish_to_platform
      for each. Sets the parent post status to 'publishing'.

  - publish_to_platform(unified_post_id, platform):
      Per-platform task. Picks the right publisher method based on
      media_type, applies platform_overrides, persists the result on the
      log row, handles typed exceptions (token expired → deactivate +
      Alert; rate-limited → Celery retry; everything else → mark failed).

A small helper update_unified_post_status() recomputes the parent's status
from the children's statuses after each child task finishes.
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Optional

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    UnifiedPost, PlatformPublishLog, PlatformCredential, Alert,
    MediaAsset,
)
from .publishers import (
    get_publisher,
    PublishError, TokenExpiredError, RateLimitError,
    PermissionDeniedError, MediaTooLargeError,
)
from . import media_service
from .realtime import push_event
from .audit import log_action

logger = logging.getLogger(__name__)


# ── BS-3I Execution Modes ─────────────────────────────────────────────────────
MODE_INITIAL_PUBLISH   = 'INITIAL_PUBLISH'
MODE_WATCHDOG_RECOVERY = 'WATCHDOG_RECOVERY'
MODE_PLATFORM_RETRY    = 'PLATFORM_RETRY'


# ── Public entry points ───────────────────────────────────────────────────────
@shared_task(bind=True)
def publish_unified_post(self, unified_post_id: int, mode: str = MODE_INITIAL_PUBLISH, target_platform: Optional[str] = None):
    """
    Fan-out a UnifiedPost across target platforms with platform-level idempotency (BS-3I).
    Skipped targets with existing success evidence or in-flight executions.
    """
    try:
        post = UnifiedPost.objects.get(id=unified_post_id)
    except UnifiedPost.DoesNotExist:
        logger.warning('publish_unified_post: post %s not found', unified_post_id)
        return

    if post.status not in ('draft', 'scheduled', 'queued', 'pending_approval', 'partial', 'failed'):
        logger.info('publish_unified_post: post %s already in status %s — skipping',
                    unified_post_id, post.status)
        return

    # Approval gate
    if post.client.requires_approval and post.status != 'scheduled' and not post.approved_by_id:
        post.status = 'pending_approval'
        post.save(update_fields=['status'])
        from .notification_watchers import notify_approver_for_post
        notify_approver_for_post.delay(post.id)
        return

    all_targets = list(post.target_platforms or [])
    if not all_targets:
        post.status = 'failed'
        post.save(update_fields=['status'])
        logger.warning('publish_unified_post: no target_platforms on post %s', unified_post_id)
        return

    if mode == MODE_PLATFORM_RETRY:
        if not target_platform or target_platform not in all_targets:
            logger.warning('publish_unified_post: invalid target_platform %s for post %s', target_platform, unified_post_id)
            return
        targets = [target_platform]
    else:
        targets = all_targets

    to_dispatch = []
    for platform in targets:
        log = PlatformPublishLog.objects.filter(unified_post=post, platform=platform).first()
        if log:
            # 1. Success Immutability: definitive external success evidence must never be replayed
            if log.status == 'success' or bool(log.platform_post_id):
                logger.info(
                    'publish_unified_post: post %s platform %s already succeeded (id=%s) — skipping provider invocation (immutable)',
                    post.id, platform, log.platform_post_id,
                )
                continue

            # 2. In-flight protection
            if log.status == 'publishing' and log.attempted_at:
                logger.info('publish_unified_post: post %s platform %s is actively publishing — skipping duplicate fanout',
                            post.id, platform)
                continue

            # 3. Failed targets require explicit retry mode
            if log.status == 'failed' and mode != MODE_PLATFORM_RETRY:
                logger.info('publish_unified_post: post %s platform %s has failed — skipping automatic redispatch (explicit retry required)',
                            post.id, platform)
                continue

            # Reset log for dispatch
            log.status = 'pending'
            log.error_code = ''
            log.error_message = ''
            log.save(update_fields=['status', 'error_code', 'error_message'])
        else:
            log = PlatformPublishLog.objects.create(
                unified_post=post, platform=platform, status='pending',
            )

        to_dispatch.append(platform)

    if not to_dispatch:
        update_unified_post_status(post.id)
        return

    post.status = 'publishing'
    post.save(update_fields=['status'])

    for platform in to_dispatch:
        publish_to_platform.delay(post.id, platform)


@shared_task(bind=True, max_retries=3, default_retry_delay=120, acks_late=True)
def publish_to_platform(self, unified_post_id: int, platform: str):
    """Publish one UnifiedPost to one platform. Retries on transient errors."""
    try:
        post = UnifiedPost.objects.select_related('client').get(id=unified_post_id)
    except UnifiedPost.DoesNotExist:
        return

    with transaction.atomic():
        log, created = PlatformPublishLog.objects.select_for_update(of=('self',)).get_or_create(
            unified_post=post, platform=platform,
            defaults={'status': 'pending'},
        )
        # Defense-in-depth: Success Immutability
        if log.status == 'success' or bool(log.platform_post_id):
            logger.info(
                'publish_to_platform: post %s platform %s already succeeded (id=%s) — skipping provider invocation (immutable success)',
                post.id, platform, log.platform_post_id,
            )
            update_unified_post_status(post.id)
            return

        # Check in-flight publishing
        if log.status == 'publishing' and log.attempted_at and not created:
            attempt_age = (timezone.now() - log.attempted_at).total_seconds()
            if attempt_age < 300:  # 5 min active window
                logger.warning(
                    'publish_to_platform: post %s platform %s is actively publishing (age=%.1fs) — skipping concurrent execution',
                    post.id, platform, attempt_age,
                )
                return

        log.status = 'publishing'
        log.attempted_at = timezone.now()
        log.save(update_fields=['status', 'attempted_at'])

    # Find an active credential for this client+platform
    cred = PlatformCredential.objects.filter(
        client=post.client, platform=platform, is_active=True,
    ).first()
    if not cred:
        _mark_failed(log, code='no_credential',
                     message=f'No active {platform} credential — connect first')
        update_unified_post_status(post.id)
        return

    # Check publisher capability safely
    try:
        publisher = get_publisher(platform)
    except PublishError as e:
        _mark_failed(log, code=e.code or 'unsupported_platform', message=str(e)[:500])
        update_unified_post_status(post.id)
        return

    # Resolve content + media (apply per-platform overrides)
    overrides = (post.platform_overrides or {}).get(platform, {}) or {}
    content    = overrides.get('content', post.content) or ''
    media_urls = overrides.get('media_urls', post.media_urls) or []
    media_type = overrides.get('media_type', post.media_type) or 'text'

    # Resolve any internal MediaAsset IDs to provider-safe URLs (e.g. S3 presigned or validated public URL).
    try:
        media_urls = _resolve_media_urls(post, media_urls, platform=platform)
    except PublishError as e:
        _mark_failed(log, code=e.code or 'public_media_required', message=str(e)[:500])
        update_unified_post_status(post.id)
        return

    # Defense-in-depth: validate Instagram carousel uniformity before any Meta calls
    if platform == 'instagram' and media_type == 'carousel':
        asset_ids = []
        raw_urls = overrides.get('media_urls', post.media_urls) or []
        for u in raw_urls:
            if isinstance(u, str) and u.startswith('asset:'):
                try:
                    asset_ids.append(int(u.split(':', 1)[1]))
                except (ValueError, IndexError):
                    pass
        asset_qs = MediaAsset.objects.filter(id__in=asset_ids, client=post.client)
        asset_map = {a.id: a for a in asset_qs}
        post_assets = [asset_map[aid] for aid in asset_ids if aid in asset_map]
        lang = getattr(post.client, 'default_language', 'en') or 'en'
        c_vr = media_service.validate_carousel_for_platform(post_assets, 'instagram', lang=lang)
        if not c_vr.ok:
            _mark_failed(log, code='invalid_carousel_aspect_ratio', message=c_vr.errors[0])
            update_unified_post_status(post.id)
            return

    try:
        result = _dispatch_publish(publisher, cred, content, media_urls, media_type, post=post)
    except TokenExpiredError as e:
        # Mark credential dead + alert + persist
        _mark_failed(log, code='token_expired', message=str(e))
        cred.is_active = False
        cred.save(update_fields=['is_active'])
        Alert.objects.create(
            client=post.client, platform=platform, alert_type='token_expired',
            message=f'{platform} token expired — please reconnect to keep publishing.',
            dedup_key=f'token_expired:{platform}:{cred.id}:{timezone.now().date()}',
        )
        push_event('credential.token_expired', post.client_id, {
            'platform': platform, 'credential_id': cred.id,
        })
        log_action(post.created_by, post.client, 'credential.deactivated',
                   platform=platform, object_type='PlatformCredential', object_id=cred.id,
                   result='failed', error='Token expired during publish')
        update_unified_post_status(post.id)
        return

    except RateLimitError as e:
        wait = max(int(getattr(e, 'retry_after', None) or 60), 30)
        log.status = 'pending'
        log.error_code = 'rate_limited'
        log.error_message = str(e)[:500]
        log.save(update_fields=['status', 'error_code', 'error_message'])
        try:
            raise self.retry(exc=e, countdown=wait)
        except self.MaxRetriesExceededError:
            _mark_failed(log, code='rate_limited',
                         message=f'Rate limit exceeded after {self.max_retries} retries')
            update_unified_post_status(post.id)
        return

    except (PermissionDeniedError, MediaTooLargeError, PublishError) as e:
        _mark_failed(log, code=getattr(e, 'code', 'publish_error') or 'publish_error',
                     message=str(e)[:500])
        update_unified_post_status(post.id)
        return

    except Exception as e:
        logger.exception('publish_to_platform unexpected error post=%s platform=%s', post.id, platform)
        _mark_failed(log, code='unexpected', message=str(e)[:500])
        update_unified_post_status(post.id)
        return

    # Success (or semantic mismatch on successful platform publish)
    log.status = 'success'
    log.platform_post_id = result.platform_post_id or log.platform_post_id or ''
    log.platform_url = result.platform_url or ''
    log.completed_at = timezone.now()
    log.error_code = getattr(result, 'error_code', '') or ''
    log.error_message = getattr(result, 'error_message', '') or ''
    log.raw_response = result.raw_response or {}
    if hasattr(result, 'provider_container_id') and result.provider_container_id:
        log.provider_container_id = result.provider_container_id
    if hasattr(result, 'provider_request_id') and result.provider_request_id:
        log.provider_request_id = result.provider_request_id
    log.save(update_fields=[
        'status', 'platform_post_id', 'platform_url',
        'completed_at', 'error_code', 'error_message', 'raw_response',
        'provider_container_id', 'provider_request_id',
    ])

    # Mark referenced media as used
    MediaAsset.objects.filter(used_in_posts=post, is_used=False).update(is_used=True)

    update_unified_post_status(post.id)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _dispatch_publish(publisher, credential, content, media_urls, media_type, *, post):
    """Pick the right publisher method based on media_type."""
    media_type = (media_type or 'text').lower()

    if media_type == 'text':
        return publisher.publish_text(credential, content)
    if media_type == 'image':
        return publisher.publish_image(credential, content, media_urls)
    if media_type == 'video':
        first = media_urls[0] if media_urls else ''
        return publisher.publish_video(credential, content, first)
    if media_type == 'carousel':
        raw_urls = (post.platform_overrides or {}).get(publisher.platform, {}).get('media_urls') or post.media_urls
        children_metadata = _resolve_carousel_children(post, raw_urls, media_urls)
        return publisher.publish_carousel(
            credential,
            content,
            media_urls,
            children_metadata=children_metadata,
        )
    if media_type == 'reel':
        first = media_urls[0] if media_urls else ''
        return publisher.publish_reel(credential, first, content)
    if media_type == 'story':
        if not media_urls:
            raise PublishError('Story requires exactly one media asset', code='missing_media')
        if len(media_urls) > 1:
            raise PublishError('Story supports only one media asset', code='too_many_media')
        first = media_urls[0]
        raw_urls = (post.platform_overrides or {}).get(publisher.platform, {}).get('media_urls') or post.media_urls
        media_kind = _resolve_story_media_kind(post, raw_urls)
        return publisher.publish_story(credential, first, media_type=media_kind, media_kind=media_kind)

    raise PublishError(f'Unknown media_type: {media_type}', code='unknown_media_type')


def _resolve_carousel_children(post: UnifiedPost, raw_urls: list, resolved_urls: list) -> list[dict]:
    """
    Build ordered canonical child metadata pairing resolved provider URLs
    with explicit media_kind ('IMAGE' or 'VIDEO') based on MediaAsset.mime_type.
    """
    raw_urls = raw_urls or []
    resolved_urls = resolved_urls or []
    if len(raw_urls) != len(resolved_urls):
        raise PublishError(
            f'Carousel media metadata count ({len(raw_urls)}) does not match URL count ({len(resolved_urls)})',
            code='media_count_mismatch',
        )

    asset_ids = []
    for u in raw_urls:
        if isinstance(u, str) and u.startswith('asset:'):
            try:
                asset_ids.append(int(u.split(':', 1)[1]))
            except (ValueError, IndexError):
                pass

    asset_map = {}
    if asset_ids:
        qs = MediaAsset.objects.filter(id__in=asset_ids, client=post.client)
        asset_map = {a.id: a for a in qs}

    children = []
    for raw, url in zip(raw_urls, resolved_urls):
        asset = None
        if isinstance(raw, str) and raw.startswith('asset:'):
            try:
                aid = int(raw.split(':', 1)[1])
                asset = asset_map.get(aid)
            except (ValueError, IndexError):
                pass

        if asset and asset.mime_type:
            mime = asset.mime_type.lower().strip()
            if mime.startswith('video/'):
                media_kind = 'VIDEO'
            elif mime.startswith('image/'):
                media_kind = 'IMAGE'
            else:
                raise PublishError(
                    f'Unsupported carousel media MIME type: {asset.mime_type}',
                    code='unsupported_media_type',
                )
            children.append({
                'url': url,
                'media_kind': media_kind,
                'mime_type': asset.mime_type,
                'asset_id': asset.id,
            })
        else:
            # Safe URL fallback for legacy bare URLs
            path = urllib.parse.urlparse(str(url)).path.lower()
            if path.endswith(('.mp4', '.mov', '.webm')):
                media_kind = 'VIDEO'
            elif path.endswith(('.jpg', '.jpeg', '.png')):
                media_kind = 'IMAGE'
            else:
                raise PublishError(
                    f'Could not determine canonical media type (IMAGE/VIDEO) for carousel item: {url}',
                    code='unsupported_media_type',
                )
            children.append({
                'url': url,
                'media_kind': media_kind,
            })

    return children


def _resolve_story_media_kind(post: UnifiedPost, raw_urls: list) -> str:
    """
    Determine canonical media kind ('IMAGE' or 'VIDEO') from MediaAsset.mime_type.
    Falls back to safe URL path extension if no MediaAsset is linked.
    Raises PublishError on unknown/unsupported types.
    """
    if not raw_urls:
        raise PublishError('Story requires exactly one media asset', code='missing_media')

    first_raw = raw_urls[0] if raw_urls else ''
    asset = None
    if isinstance(first_raw, str) and first_raw.startswith('asset:'):
        try:
            aid = int(first_raw.split(':', 1)[1])
            asset = MediaAsset.objects.filter(id=aid, client=post.client).first()
        except (ValueError, IndexError):
            pass
    if not asset and hasattr(post, 'media_assets'):
        asset = post.media_assets.first()

    if asset and asset.mime_type:
        mime = asset.mime_type.lower().strip()
        if mime.startswith('video/'):
            return 'VIDEO'
        if mime.startswith('image/'):
            return 'IMAGE'
        raise PublishError(
            f'Unsupported Story media MIME type: {asset.mime_type}',
            code='unsupported_media_type',
        )

    # Fallback to parsing URL path safely if no MediaAsset metadata exists
    if isinstance(first_raw, str) and first_raw:
        path = urllib.parse.urlparse(first_raw).path.lower()
        if path.endswith(('.mp4', '.mov', '.webm')):
            return 'VIDEO'
        if path.endswith(('.jpg', '.jpeg', '.png')):
            return 'IMAGE'

    raise PublishError(
        'Could not determine canonical media type (IMAGE/VIDEO) for Story',
        code='unsupported_media_type',
    )


def _resolve_media_urls(post: UnifiedPost, media_urls: list, platform: Optional[str] = None) -> list:
    """
    Translate a mix of bare URLs and `asset:<id>` placeholders into final URLs.
    Resolves provider-safe public URLs using media_service.get_provider_media_url.
    """
    out = []
    lang = getattr(post.client, 'default_language', 'en') or 'en'
    for u in media_urls or []:
        if isinstance(u, str) and u.startswith('asset:'):
            try:
                asset_id = int(u.split(':', 1)[1])
                asset = MediaAsset.objects.filter(
                    id=asset_id, client=post.client,
                ).first()
                if asset:
                    if platform:
                        resolved = media_service.get_provider_media_url(asset, platform, lang=lang)
                    else:
                        resolved = media_service.presigned_url(asset)
                    if resolved:
                        out.append(resolved)
                    continue
            except (ValueError, IndexError):
                pass
        elif isinstance(u, str) and u:
            if platform:
                validated = media_service.validate_media_url_for_provider(u, platform, lang=lang)
                out.append(validated)
            else:
                out.append(u)
    return [u for u in out if u]


def _mark_failed(log: PlatformPublishLog, *, code: str, message: str):
    # Safety check: NEVER overwrite successful platform state
    if log.status == 'success' or bool(log.platform_post_id):
        logger.warning(
            'Refusing to mark failed: log %s for platform %s already succeeded (post_id=%s)',
            log.id, log.platform, log.platform_post_id,
        )
        return
    log.status = 'failed'
    log.error_code = (code or 'failed')[:80]
    log.error_message = (message or '')[:500]
    log.completed_at = timezone.now()
    log.save(update_fields=['status', 'error_code', 'error_message', 'completed_at'])


def update_unified_post_status(unified_post_id: int):
    """Recompute the parent UnifiedPost.status from its child publish_logs."""
    try:
        post = UnifiedPost.objects.get(id=unified_post_id)
    except UnifiedPost.DoesNotExist:
        return

    targets = list(post.target_platforms or [])
    if not targets:
        return

    logs = {l.platform: l for l in post.publish_logs.all()}

    # If any targeted platform has no log or log status in ('pending', 'publishing'),
    # then publication is still in-flight.
    in_flight = False
    for p in targets:
        log = logs.get(p)
        if not log or log.status in ('pending', 'publishing'):
            in_flight = True
            break

    if in_flight:
        if post.status != 'publishing':
            post.status = 'publishing'
            post.save(update_fields=['status'])
        return

    statuses = [logs[p].status for p in targets if p in logs]
    if len(statuses) < len(targets):
        if post.status != 'publishing':
            post.status = 'publishing'
            post.save(update_fields=['status'])
        return

    # All success
    if all(s == 'success' for s in statuses):
        post.status = 'published'
        if not post.published_at:
            post.published_at = timezone.now()
        post.save(update_fields=['status', 'published_at'])
        push_event('composer.post_published', post.client_id, {
            'unified_post_id': post.id,
            'title':           post.title or post.content[:60],
            'platforms':       post.target_platforms or [],
        })
        log_action(post.created_by, post.client, 'composer.published',
                   object_type='UnifiedPost', object_id=post.id,
                   result='success',
                   details={'platforms': post.target_platforms,
                            'title': post.title or post.content[:120]})
        try:
            from .events.publisher import EventPublisher
            EventPublisher.publish(
                'post.published',
                client=post.client,
                actor=post.created_by,
                payload={
                    'post_id': post.id,
                    'platforms': list(post.target_platforms or []),
                },
            )
        except Exception:
            pass
        return

    # All failed
    if all(s == 'failed' for s in statuses):
        post.status = 'failed'
        post.save(update_fields=['status'])
        push_event('composer.post_failed', post.client_id, {
            'unified_post_id': post.id,
            'title':           post.title or post.content[:60],
        })
        log_action(post.created_by, post.client, 'composer.published',
                   object_type='UnifiedPost', object_id=post.id,
                   result='failed',
                   details={'platforms': post.target_platforms,
                            'title': post.title or post.content[:120]})
        try:
            from .events.publisher import EventPublisher
            # Pull a representative reason from the first failed publish_log.
            failed_log = post.publish_logs.filter(status='failed').first()
            reason = (failed_log.error_message if failed_log and failed_log.error_message else 'all platforms failed')
            EventPublisher.publish(
                'post.failed',
                client=post.client,
                actor=post.created_by,
                payload={
                    'post_id': post.id,
                    'reason': reason[:300],
                },
            )
        except Exception:
            pass
        return

    # Mixed → partial
    if any(s == 'success' for s in statuses) and any(s == 'failed' for s in statuses):
        post.status = 'partial'
        if not post.published_at:
            post.published_at = timezone.now()
        post.save(update_fields=['status', 'published_at'])
        push_event('composer.post_partial', post.client_id, {
            'unified_post_id': post.id,
            'title':           post.title or post.content[:60],
            'success_count':   sum(1 for s in statuses if s == 'success'),
            'failed_count':    sum(1 for s in statuses if s == 'failed'),
        })
        log_action(post.created_by, post.client, 'composer.published',
                   object_type='UnifiedPost', object_id=post.id,
                   result='partial',
                   details={'platforms': post.target_platforms,
                            'success_count': sum(1 for s in statuses if s == 'success'),
                            'failed_count':  sum(1 for s in statuses if s == 'failed')})
