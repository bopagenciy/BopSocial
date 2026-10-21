"""
Rollup Backfill Service for Bop Social Analytics.
Provides safe, on-demand rebuilds of SocialMetricRollup from underlying SocialMetricSnapshot observations.
"""
import logging
from typing import Dict, List, Optional, Tuple

from social_stats.models import Client, SocialMetricSnapshot
from .rollups import build_rollups_for_client

logger = logging.getLogger(__name__)


def backfill_rollups(
    client_id: Optional[int] = None,
    platform: Optional[str] = None,
    periods: Tuple[str, ...] = ("day", "week", "month"),
    dry_run: bool = False,
) -> Dict[str, Dict]:
    """
    Backfills or reconciles SocialMetricRollups across all or specific clients.
    In dry_run mode, counts matching snapshots without generating rollups.
    """
    client_qs = Client.objects.filter(is_active=True)
    if client_id:
        client_qs = client_qs.filter(id=client_id)

    results = {}

    for client in client_qs:
        cid = client.id
        qs = SocialMetricSnapshot.objects.filter(client_id=cid)
        if platform:
            qs = qs.filter(platform=platform)

        snapshot_count = qs.count()

        if dry_run:
            results[str(cid)] = {
                "dry_run": True,
                "snapshots_found": snapshot_count,
                "periods": periods,
                "platform": platform or "all",
            }
        else:
            rollup_stats = build_rollups_for_client(
                client_id=cid,
                platform=platform,
                periods=periods,
            )
            results[str(cid)] = {
                "dry_run": False,
                "snapshots_processed": snapshot_count,
                "created": rollup_stats["created"],
                "updated": rollup_stats["updated"],
                "periods": periods,
                "platform": platform or "all",
            }

    return results
