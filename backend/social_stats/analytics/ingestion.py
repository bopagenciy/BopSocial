"""
Ingestion Service for Bop Social Analytics.

Provides provider-independent, deterministic, idempotent ingestion for SocialMetricSnapshot
and SocialMetricRollup records with tenant scoping, dimensions hashing, and UnifiedPost linking.
"""
import hashlib
import json
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def compute_dimensions_hash(dimensions: Optional[Dict]) -> str:
    """
    Computes deterministic SHA256 hex digest of sorted canonical JSON extra_dimensions.
    Returns empty string '' if dimensions is empty or None.
    """
    if not dimensions:
        return ""
    try:
        serialized = json.dumps(dimensions, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
    except Exception as e:
        logger.warning(f"Failed to serialize dimensions for hashing: {e}")
        return ""


def find_publish_log_and_unified_post(
    client,
    platform: str,
    object_id: str,
):
    """
    Safely resolves PlatformPublishLog and UnifiedPost for a provider object ID.
    Strictly scoped by client and platform to prevent cross-tenant/cross-platform misattribution.
    """
    if not object_id or not client or not platform:
        return None, None

    from social_stats.models import PlatformPublishLog

    client_id = getattr(client, 'id', client)
    plat = platform.strip().lower()

    log = PlatformPublishLog.objects.filter(
        unified_post__client_id=client_id,
        platform=plat,
        platform_post_id=str(object_id).strip(),
    ).select_related('unified_post').first()

    if log:
        return log, log.unified_post
    return None, None


@transaction.atomic
def ingest_metric_snapshot(
    client,
    platform: str,
    metric_scope: str,
    object_id: str,
    normalized_metric: str,
    metric_value: Union[int, float, Decimal, str],
    raw_metric_name: str,
    account_id: str = "",
    bucket_period: str = "day",
    bucket_timestamp=None,
    extra_dimensions: Optional[Dict] = None,
    provider_timestamp=None,
    freshness_state: str = "FRESH",
    is_derived: bool = False,
    metadata: Optional[Dict] = None,
    link_authored_post: bool = True,
):
    """
    Idempotently ingests or updates a SocialMetricSnapshot row.
    Guarantees deterministic uniqueness and safe in-place settlement updates without duplicates.
    """
    from social_stats.models import SocialMetricSnapshot

    if bucket_timestamp is None:
        bucket_timestamp = timezone.now().replace(minute=0, second=0, microsecond=0)

    dims = extra_dimensions or {}
    dims_hash = compute_dimensions_hash(dims)
    meta = metadata or {}
    plat = platform.strip().lower()
    scope = metric_scope.strip().lower()
    obj_id = str(object_id).strip()
    norm_metric = normalized_metric.strip().upper()

    # Link authored post if applicable and requested
    publish_log = None
    unified_post = None
    if link_authored_post and scope in ("post", "reel", "video", "story"):
        publish_log, unified_post = find_publish_log_and_unified_post(
            client=client,
            platform=plat,
            object_id=obj_id,
        )

    # Ingest or update existing bucket (handling Meta settlement updates in-place)
    snapshot, created = SocialMetricSnapshot.objects.update_or_create(
        client=client,
        platform=plat,
        metric_scope=scope,
        object_id=obj_id,
        normalized_metric=norm_metric,
        dimensions_hash=dims_hash,
        bucket_period=bucket_period,
        bucket_timestamp=bucket_timestamp,
        defaults={
            "account_id": account_id or "",
            "raw_metric_name": raw_metric_name,
            "metric_value": Decimal(str(metric_value)),
            "extra_dimensions": dims,
            "unified_post": unified_post,
            "publish_log": publish_log,
            "provider_timestamp": provider_timestamp,
            "freshness_state": freshness_state,
            "is_derived": is_derived,
            "metadata": meta,
        }
    )

    return snapshot, created


@transaction.atomic
def ingest_observations(
    client,
    platform: str,
    object_id: str,
    observations: List,
    account_id: str = "",
    bucket_period: str = "day",
    bucket_timestamp=None,
    provider_timestamp=None,
    freshness_state: str = "FRESH",
    link_authored_post: bool = True,
) -> List:
    """
    Batch ingests a list of NormalizedObservation instances for a given object.
    """
    snapshots = []
    for obs in observations:
        snap, _ = ingest_metric_snapshot(
            client=client,
            platform=platform,
            metric_scope=obs.metric_scope,
            object_id=object_id,
            normalized_metric=obs.normalized_metric,
            metric_value=obs.metric_value,
            raw_metric_name=obs.raw_metric_name,
            account_id=account_id,
            bucket_period=bucket_period,
            bucket_timestamp=bucket_timestamp,
            extra_dimensions=obs.extra_dimensions,
            provider_timestamp=provider_timestamp,
            freshness_state=freshness_state,
            is_derived=obs.is_derived,
            metadata=obs.metadata,
            link_authored_post=link_authored_post,
        )
        snapshots.append(snap)
    return snapshots
