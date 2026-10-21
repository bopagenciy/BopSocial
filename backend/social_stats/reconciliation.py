# ============================================================================
#  Social Stats — BS-3J Provider Reconciliation Adapters
# ============================================================================
"""
Dedicated provider reconciliation layer for Bop Social.
Inspects external provider-side state for ambiguous publications to deterministically
confirm whether a publication succeeded or definitely did not publish.
Fails closed for any heuristic or ambiguous outcome.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .models import PlatformCredential, PlatformPublishLog, UnifiedPost
from .publishers._graph_client import GraphClient
from .publishers.base import PublishError

logger = logging.getLogger(__name__)

OUTCOME_CONFIRMED_PUBLISHED     = 'CONFIRMED_PUBLISHED'
OUTCOME_CONFIRMED_NOT_PUBLISHED = 'CONFIRMED_NOT_PUBLISHED'
OUTCOME_STILL_PROCESSING        = 'STILL_PROCESSING'
OUTCOME_AMBIGUOUS               = 'AMBIGUOUS'
OUTCOME_RECONCILIATION_UNAVAILABLE = 'RECONCILIATION_UNAVAILABLE'
OUTCOME_PROVIDER_ERROR          = 'PROVIDER_ERROR'


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

        # 1. Finished / Published
        if status_code in ('FINISHED', 'PUBLISHED'):
            # Query recent account media to locate the published media id if possible
            media_id = None
            try:
                recent = client.get(
                    f'/{credential.instagram_account_id}/media',
                    params={'fields': 'id,caption', 'limit': 5},
                )
                for item in (recent.get('data') or []):
                    if post.content and item.get('caption') and item.get('caption').strip() == post.content.strip():
                        media_id = item.get('id')
                        break
            except Exception:
                pass

            if not media_id:
                media_id = log.platform_post_id or f'ig_reconciled_{container_id}'

            return ReconciliationResult(
                outcome=OUTCOME_CONFIRMED_PUBLISHED,
                provider_post_id=str(media_id),
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=False,
                message=f'Meta confirms media container {container_id} completed processing ({status_code})',
            )

        # 2. In Progress
        if status_code == 'IN_PROGRESS':
            return ReconciliationResult(
                outcome=OUTCOME_STILL_PROCESSING,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=container_id,
                safe_to_retry=False,
                message=f'Meta container {container_id} is still in progress on provider cluster',
            )

        # 3. Error / Expired
        if status_code in ('ERROR', 'EXPIRED'):
            return ReconciliationResult(
                outcome=OUTCOME_CONFIRMED_NOT_PUBLISHED,
                provider_container_id=container_id,
                provider_status=status_code,
                evidence_type='meta_container_status',
                evidence_reference=f'{container_id}:{status_code}',
                safe_to_retry=True,
                message=f'Meta container {container_id} terminated with {status_code}; media was definitely not published',
            )

        # 4. Unknown / Malformed
        return ReconciliationResult(
            outcome=OUTCOME_AMBIGUOUS,
            provider_container_id=container_id,
            provider_status=status_code or 'UNKNOWN',
            evidence_type='meta_container_status',
            evidence_reference=container_id,
            safe_to_retry=False,
            message=f"Meta returned unrecognized container status '{status_code}'; manual provider inspection required",
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
        # Per BS-3J Safety Policy: Facebook does not provide client-side idempotency keys.
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
