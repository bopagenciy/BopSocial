"""
Central Analytics Scheduler and Cadence Orchestrator for Bop Social.
Evaluates sync due conditions, enforces concurrency locks, respects rate-limits,
adapts to credential capabilities, and dispatches tasks to the dedicated analytics queue.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.core.cache import cache
from django.utils import timezone

from social_stats.models import PlatformCredential, SyncLog
from .adapters.instagram import has_instagram_insights_capability
from .rate_limits import evaluate_throttling

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 900  # 15 minutes


def get_sync_lock_key(client_id: int, platform: str) -> str:
    return f"analytics_sync_lock:{client_id}:{platform}"


def acquire_sync_lock(client_id: int, platform: str) -> bool:
    """
    Acquires a concurrency lock to prevent duplicate task dispatches for the same (client, platform).
    First checks running SyncLogs, then attempts atomic cache lock acquisition.
    """
    # 1. DB-level check: Any running SyncLog started within the lock window?
    active_run = SyncLog.objects.filter(
        client_id=client_id,
        platform=platform,
        status="running",
        started_at__gte=timezone.now() - timedelta(seconds=LOCK_TIMEOUT_SECONDS),
    ).exists()

    if active_run:
        logger.info(f"Sync lock rejected for client {client_id} platform {platform}: active SyncLog running.")
        return False

    # 2. Atomic cache lock
    lock_key = get_sync_lock_key(client_id, platform)
    acquired = cache.add(lock_key, timezone.now().isoformat(), timeout=LOCK_TIMEOUT_SECONDS)
    return bool(acquired)


def release_sync_lock(client_id: int, platform: str) -> None:
    """Releases the concurrency lock."""
    lock_key = get_sync_lock_key(client_id, platform)
    cache.delete(lock_key)


def is_sync_due(
    credential: PlatformCredential,
    cadence_hours: int = 24,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether an analytics sync is due for the given credential.
    Returns (is_due, reason).
    """
    current_time = now or timezone.now()

    if not credential.is_active:
        return False, "CREDENTIAL_INACTIVE"

    # Evaluate rate limits
    decision, wait_secs = evaluate_throttling(credential.rate_limit_state)
    if decision == "COOLDOWN":
        return False, f"RATE_LIMIT_COOLDOWN_{wait_secs}s"

    # Evaluate time since last sync
    last_log = (
        SyncLog.objects.filter(
            client_id=credential.client_id,
            platform=credential.platform,
            status__in=["success", "partial"],
        )
        .order_by("-finished_at")
        .first()
    )

    if not last_log or not last_log.finished_at:
        return True, "NEVER_SYNCED"

    elapsed_seconds = (current_time - last_log.finished_at).total_seconds()
    required_seconds = cadence_hours * 3600

    if elapsed_seconds >= required_seconds:
        return True, f"DUE_ELAPSED_{int(elapsed_seconds)}s"
    else:
        remaining = int(required_seconds - elapsed_seconds)
        return False, f"NOT_DUE_REMAINING_{remaining}s"


def run_analytics_orchestrator(
    dry_run: bool = False,
    force: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, List[Dict]]:
    """
    Main orchestrator run loop.
    Scans active PlatformCredentials, evaluates cadence and rate limits,
    acquires locks, and dispatches Celery tasks.
    """
    from social_stats.analytics_tasks import (
        sync_client_facebook_analytics_v2,
        sync_client_instagram_analytics_v2,
    )

    results = {
        "dispatched": [],
        "skipped": [],
        "locked": [],
    }

    credentials = PlatformCredential.objects.filter(
        platform__in=["facebook", "instagram"],
        is_active=True,
    ).select_related("client")

    for cred in credentials:
        client_id = cred.client_id
        platform = cred.platform

        # Check cadence
        due, reason = is_sync_due(cred, now=now)
        if not due and not force:
            results["skipped"].append({
                "client_id": client_id,
                "platform": platform,
                "reason": reason,
            })
            continue

        # Check concurrency lock
        if not dry_run:
            locked = acquire_sync_lock(client_id, platform)
            if not locked:
                results["locked"].append({
                    "client_id": client_id,
                    "platform": platform,
                    "reason": "CONCURRENT_DISPATCH_LOCKED",
                })
                continue

        # Evaluate capability mode for metadata logging
        capability_mode = "FULL"
        if platform == "instagram":
            has_insights = has_instagram_insights_capability(cred)
            capability_mode = "FULL" if has_insights else "PARTIAL"

        decision_info = {
            "client_id": client_id,
            "platform": platform,
            "reason": reason,
            "capability_mode": capability_mode,
        }

        if not dry_run:
            try:
                if platform == "facebook":
                    sync_client_facebook_analytics_v2.apply_async(
                        args=[client_id, 7],
                        queue="analytics",
                    )
                elif platform == "instagram":
                    sync_client_instagram_analytics_v2.apply_async(
                        args=[client_id, 30],
                        queue="analytics",
                    )
                decision_info["dispatched"] = True
            except Exception as e:
                logger.error(f"Failed to dispatch sync for client {client_id} platform {platform}: {e}")
                release_sync_lock(client_id, platform)
                decision_info["dispatch_error"] = str(e)

        results["dispatched"].append(decision_info)

    return results
