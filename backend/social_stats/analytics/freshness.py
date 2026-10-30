"""
Freshness Evaluation Service for Bop Social Analytics.
Provides centralized detection of data staleness, data age, and next expected sync cadence
across account metrics, recent posts, maturing posts, old posts, and ephemeral stories.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from django.utils import timezone

from social_stats.models import SyncLog, SocialMetricSnapshot
from .registry import FreshnessState

logger = logging.getLogger(__name__)


def evaluate_freshness(
    last_synced_at: Optional[datetime],
    metric_scope: str = "account",
    post_published_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Tuple[FreshnessState, int, Optional[datetime]]:
    """
    Evaluates freshness state, data age in seconds, and projected next sync time.
    Returns (freshness_state, data_age_seconds, next_scheduled_sync).
    """
    current_time = now or timezone.now()

    if not last_synced_at:
        return FreshnessState.UNAVAILABLE, -1, None

    data_age_seconds = max(0, int((current_time - last_synced_at).total_seconds()))

    # 1. Story scope (<24h lifetime)
    if metric_scope == "story":
        if post_published_at and (current_time - post_published_at).total_seconds() > 86400:
            # Story has expired from provider API
            return FreshnessState.UNAVAILABLE, data_age_seconds, None

        cadence_seconds = 3 * 3600  # 3 hours
        next_sync = last_synced_at + timedelta(seconds=cadence_seconds)
        if data_age_seconds < cadence_seconds:
            return FreshnessState.FRESH, data_age_seconds, next_sync
        elif data_age_seconds < 6 * 3600:
            return FreshnessState.AGING, data_age_seconds, next_sync
        else:
            return FreshnessState.STALE, data_age_seconds, next_sync

    # 2. Post / Reel / Video scopes
    elif metric_scope in ("post", "reel", "video"):
        post_age_days = (
            (current_time - post_published_at).total_seconds() / 86400.0
            if post_published_at
            else 0.0
        )

        if post_age_days <= 2.0:
            # Recent post (<48h old): 4h cadence
            cadence_seconds = 4 * 3600
            aging_threshold = 12 * 3600
        elif post_age_days <= 14.0:
            # Maturing post (3–14 days old): 24h cadence
            cadence_seconds = 24 * 3600
            aging_threshold = 48 * 3600
        else:
            # Old post (>14 days old): weekly cadence
            cadence_seconds = 7 * 86400
            aging_threshold = 14 * 86400

        next_sync = last_synced_at + timedelta(seconds=cadence_seconds)
        if data_age_seconds < cadence_seconds:
            return FreshnessState.FRESH, data_age_seconds, next_sync
        elif data_age_seconds < aging_threshold:
            return FreshnessState.AGING, data_age_seconds, next_sync
        else:
            return FreshnessState.STALE, data_age_seconds, next_sync

    # 3. Account / Channel scope (default 24h cadence)
    else:
        cadence_seconds = 24 * 3600  # 1 day
        next_sync = last_synced_at + timedelta(seconds=cadence_seconds)
        if data_age_seconds < cadence_seconds:
            return FreshnessState.FRESH, data_age_seconds, next_sync
        elif data_age_seconds < 48 * 3600:
            return FreshnessState.AGING, data_age_seconds, next_sync
        else:
            return FreshnessState.STALE, data_age_seconds, next_sync


def get_client_platform_freshness(client_id: int, platform: str) -> Dict:
    """
    Retrieves current data freshness summary for a client and platform.
    """
    last_log = (
        SyncLog.objects.filter(
            client_id=client_id,
            platform=platform,
            status__in=["success", "partial"],
            sync_scope="CURRENT",
        )
        .order_by("-finished_at")
        .first()
    )

    last_synced_at = last_log.finished_at if last_log else None
    state, age_secs, next_sync = evaluate_freshness(last_synced_at, metric_scope="account")

    return {
        "client_id": client_id,
        "platform": platform,
        "freshness_state": state.value,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "data_age_seconds": age_secs,
        "next_scheduled_sync": next_sync.isoformat() if next_sync else None,
    }
