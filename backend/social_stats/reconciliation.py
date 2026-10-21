# ============================================================================
#  Social Stats — BS-3J.1 Provider Reconciliation Adapters
# ============================================================================
"""
Dedicated provider reconciliation layer for Bop Social.
Inspects external provider-side state for ambiguous publications to deterministically
confirm whether a publication succeeded or definitely did not publish.

BS-3J.1 Provider Semantics Correction:
- Instagram container status_code == 'PUBLISHED':
    Direct evidence that the container media object was published on Instagram.
    Transitions PlatformPublishLog to 'success'.
    NOTE ON GRAPH API BEHAVIOR:
      GET /{container_id}?fields=status_code,status,id returns `id` which is the
      CONTAINER ID (not media_id). Meta Graph API does NOT expose a published media
      ID on the container node. Therefore, unless deterministically retrieved via
      a prior synchronous media_publish response, platform_post_id remains unpopulated.
      Heuristic caption/timestamp matching against recent media is strictly prohibited.
- Instagram container status_code == 'FINISHED':
    Container/media processing completed and is READY for media_publish, but publication
    is NOT yet confirmed. This is NOT a published state.
    Transitions reconciliation_status to 'READY_TO_PUBLISH_UNCONFIRMED'.
    log.status is NOT changed to 'success'. safe_to_retry remains False.
- Instagram container status_code == 'IN_PROGRESS':
    Container is still processing on Meta cluster.
    Transitions reconciliation_status to 'STILL_PROCESSING'. safe_to_retry remains False.
- Instagram container status_code in ('ERROR', 'EXPIRED'):
    Container failed or expired before publication could occur.
    Transitions reconciliation_status to 'CONFIRMED_NOT_PUBLISHED'.
    log.status transitions to 'failed'. safe_to_retry becomes True (controlled retry only).
- Fails closed for any heuristic, unknown, or ambiguous outcome.
- Reconciliation is strictly READ-ONLY: never issues POST or media_publish.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .models import PlatformCredential, PlatformPublishLog, UnifiedPost
from .publishers._graph_client import GraphClient
from .publishers.base import PublishError

logger = logging.getLogger(__name__)

OUTCOME_CONFIRMED_PUBLISHED          = 'CONFIRMED_PUBLISHED'
OUTCOME_CONFIRMED_NOT_PUBLISHED      = 'CONFIRMED_NOT_PUBLISHED'
OUTCOME_READY_TO_PUBLISH_UNCONFIRMED = 'READY_TO_PUBLISH_UNCONFIRMED'
OUTCOME_STILL_PROCESSING             = 'STILL_PROCESSING'
OUTCOME_AMBIGUOUS                    = 'AMBIGUOUS'
OUTCOME_RECONCILIATION_UNAVAILABLE   = 'RECONCILIATION_UNAVAILABLE'
OUTCOME_PROVIDER_ERROR               = 'PROVIDER_ERROR'


@dataclass
class ReconciliationResult:
    outcome: str
    provider_post_id: Optional[str] = None
    provider_container_id: Optional[str] = None
    provider_status: Optional[str] = None
    evidence_type: str = ''
    evidence_reference: str = ''
    safe_to_retry: bool = False
    message: str = ''


class BaseReconciliationAdapter:
    platform: str = ''

    def reconcile(
        self,
        post: UnifiedPost,
        log: PlatformPublishLog,
        credential: PlatformCredential,
    ) -> ReconciliationResult:
        raise NotImplementedError


class InstagramReconciliationAdapter(BaseReconciliationAdapter):
    platform = 'instagram'

    def reconcile(
        self,
        post: UnifiedPost,
        log: PlatformPublishLog,
        credential: PlatformCredential,
    ) -> ReconciliationResult:
        container_id = log.provider_container_id
        if not container_id:
            return ReconciliationResult(
                outcome=OUTCOME_RECONCILIATION_UNAVAILABLE,
                message='No provider_container_id stored; cannot deterministically inspect Instagram container',
                evidence_type='missing_container_id',
                safe_to_retry=False,
            )

        client = GraphClient(credential.access_token, timeout=15)
        try:
            res = client.get(f'/{container_id}', params={'fields': 'status_code,status,id'})
        except (PublishError, Exception) as exc:
            logger.warning('Instagram reconciliation error for container %s: %s', container_id, exc)
            return ReconciliationResult(
                outcome=OUTCOME_PROVIDER_ERROR,
                provider_container_id=container_id,
                message=f'Meta API error during container status query: {str(exc)[:200]}',
                evidence_type='provider_exception',
                evidence_reference=str(exc)[:100],
                safe_to_retry=False,
            )

        status_code = (res.get('status_code') or '').upper().strip()

        # 1. PUBLISHED: Container media object was definitively published by Meta
        if status_code == 'PUBLISHED':
            # Note on Provider Semantics:
            # GET /{container_id} returns id == container_id, NOT media_id.
            # If log.platform_post_id was already populated, retain it; otherwise leave empty.
            # Heuristic feed/caption matching is strictly prohibited.
            return ReconciliationResult(
                outcome=OUTCOME_CONFIRMED_PUBLISHED,
                provider_post_id=log.platform_post_id or None,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=False,
                message=f'Meta confirms media container {container_id} was PUBLISHED.',
            )

        # 2. FINISHED: Container processing completed and ready for media_publish, but publication is NOT confirmed
        if status_code == 'FINISHED':
            return ReconciliationResult(
                outcome=OUTCOME_READY_TO_PUBLISH_UNCONFIRMED,
                provider_post_id=None,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=False,
                message=f'Container {container_id} is FINISHED (ready for publication), but publication is not confirmed. Manual verification required.',
            )

        # 3. IN_PROGRESS: Still processing on Meta cluster
        if status_code == 'IN_PROGRESS':
            return ReconciliationResult(
                outcome=OUTCOME_STILL_PROCESSING,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=False,
                message=f'Meta container {container_id} is still in progress on provider cluster.',
            )

        # 4. ERROR: Container processing failed permanently on provider side
        if status_code == 'ERROR':
            err_msg = res.get('status') or 'Meta container processing failed with ERROR'
            return ReconciliationResult(
                outcome=OUTCOME_CONFIRMED_NOT_PUBLISHED,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=True,
                message=f'Meta container {container_id} failed processing ({err_msg}); media was definitely not published.',
            )

        # 5. EXPIRED: Container expired before publication
        if status_code == 'EXPIRED':
            return ReconciliationResult(
                outcome=OUTCOME_CONFIRMED_NOT_PUBLISHED,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=True,
                message=f'Meta container {container_id} expired; media was definitely not published.',
            )

        # 6. Unknown / Unrecognized status
        return ReconciliationResult(
            outcome=OUTCOME_AMBIGUOUS,
            provider_container_id=container_id,
            provider_status=status_code or 'UNKNOWN',
            evidence_type='meta_container_status',
            evidence_reference=f'{container_id}:{status_code or "UNKNOWN"}',
            safe_to_retry=False,
            message=f'Meta container returned unrecognized status: "{status_code}". Failing closed as AMBIGUOUS.',
        )


class FacebookReconciliationAdapter(BaseReconciliationAdapter):
    platform = 'facebook'

    def reconcile(
        self,
        post: UnifiedPost,
        log: PlatformPublishLog,
        credential: PlatformCredential,
    ) -> ReconciliationResult:
        # Case A: Existing platform_post_id can be verified directly
        if log.platform_post_id:
            client = GraphClient(credential.access_token, timeout=15)
            try:
                res = client.get(f'/{log.platform_post_id}', params={'fields': 'id,created_time'})
                if res.get('id'):
                    return ReconciliationResult(
                        outcome=OUTCOME_CONFIRMED_PUBLISHED,
                        provider_post_id=log.platform_post_id,
                        evidence_type='facebook_object_lookup',
                        evidence_reference=log.platform_post_id,
                        safe_to_retry=False,
                        message=f'Facebook confirmed publication exists (id={log.platform_post_id})',
                    )
            except Exception as exc:
                return ReconciliationResult(
                    outcome=OUTCOME_PROVIDER_ERROR,
                    message=f'Facebook query failed for post ID {log.platform_post_id}: {exc}',
                    evidence_type='provider_exception',
                    evidence_reference=str(exc)[:100],
                    safe_to_retry=False,
                )

        # Case B: No platform_post_id exists
        # Per BS-3J / BS-3J.1 Safety Policy: Facebook does not provide client-side idempotency keys.
        # Heuristic feed matching (same message, close timestamp) is strictly forbidden from
        # being treated as definitive proof.
        return ReconciliationResult(
            outcome=OUTCOME_RECONCILIATION_UNAVAILABLE,
            evidence_type='policy_restriction',
            evidence_reference='no_client_idempotency_token',
            safe_to_retry=False,
            message='Facebook Graph API does not provide client idempotency keys for unconfirmed feed posts. Heuristic feed matching is blocked by safety policy to prevent duplicates.',
        )


def get_reconciliation_adapter(platform: str) -> BaseReconciliationAdapter:
    platform = (platform or '').lower().strip()
    if platform == 'instagram':
        return InstagramReconciliationAdapter()
    if platform == 'facebook':
        return FacebookReconciliationAdapter()
    raise ValueError(f"No reconciliation adapter available for platform '{platform}'")
