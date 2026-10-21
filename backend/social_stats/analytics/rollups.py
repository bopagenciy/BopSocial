"""
Rollup Service for Bop Social Analytics.
Transforms granular SocialMetricSnapshot observations into materialized SocialMetricRollup caches
honoring Canonical Metric Registry aggregation semantics, client timezones, and non-aggregatable metric safety.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple
import zoneinfo

from django.db import transaction
from django.utils import timezone

from social_stats.models import Client, SocialMetricSnapshot, SocialMetricRollup
from .registry import AggregationBehavior, CANONICAL_METRICS

logger = logging.getLogger(__name__)


def get_client_timezone(client: Client) -> zoneinfo.ZoneInfo:
    """Safely retrieves client timezone or falls back to UTC."""
    tz_name = getattr(client, "timezone", "") or "UTC"
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        logger.warning(f"Invalid timezone '{tz_name}' for client {client.id}. Falling back to UTC.")
        return zoneinfo.ZoneInfo("UTC")


def calculate_period_start(dt: datetime, period: str, client_tz: zoneinfo.ZoneInfo) -> date:
    """
    Converts a UTC datetime to client-local date and aligns to canonical period boundary.
    - 'day': exact local calendar date.
    - 'week': canonical ISO Monday.
    - 'month': 1st calendar day of local month.
    """
    if timezone.is_aware(dt):
        local_dt = dt.astimezone(client_tz)
    else:
        local_dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(client_tz)

    local_date = local_dt.date()

    if period == "day":
        return local_date
    elif period == "week":
        return local_date - timedelta(days=local_date.weekday())
    elif period == "month":
        return local_date.replace(day=1)
    elif period == "year":
        return local_date.replace(month=1, day=1)
    else:
        return local_date


def aggregate_snapshots(
    snapshots: List[SocialMetricSnapshot],
    normalized_metric: str,
    period: str,
) -> Tuple[Decimal, Dict]:
    """
    Computes aggregated value for a group of snapshots according to its AggregationBehavior.
    Returns (metric_value, metadata).
    """
    if not snapshots:
        return Decimal("0.0000"), {}

    definition = CANONICAL_METRICS.get(normalized_metric)
    behavior = definition.aggregation_behavior if definition else AggregationBehavior.SUMMABLE

    metadata = {
        "aggregation_behavior": behavior.value,
        "sample_count": len(snapshots),
        "is_available": True,
    }

    # 1. SUMMABLE: discrete events/counts that can be summed across time
    if behavior == AggregationBehavior.SUMMABLE:
        total = sum((s.metric_value for s in snapshots), Decimal("0"))
        return total.quantize(Decimal("0.0001")), metadata

    # 2. LATEST_VALUE: point-in-time gauges (e.g. followers)
    elif behavior == AggregationBehavior.LATEST_VALUE:
        sorted_snaps = sorted(snapshots, key=lambda s: (s.bucket_timestamp, s.captured_at))
        latest = sorted_snaps[-1]
        metadata["latest_bucket_timestamp"] = latest.bucket_timestamp.isoformat()
        return latest.metric_value.quantize(Decimal("0.0001")), metadata

    # 3. DELTA: net changes within periods (e.g. net followers)
    elif behavior == AggregationBehavior.DELTA:
        total = sum((s.metric_value for s in snapshots), Decimal("0"))
        return total.quantize(Decimal("0.0001")), metadata

    # 4. AVERAGE: ratios or durations that must be averaged
    elif behavior == AggregationBehavior.AVERAGE:
        total = sum((s.metric_value for s in snapshots), Decimal("0"))
        avg = total / Decimal(str(len(snapshots)))
        return avg.quantize(Decimal("0.0001")), metadata

    # 5. NON_AGGREGATABLE: unique user sets (e.g. REACH)
    elif behavior == AggregationBehavior.NON_AGGREGATABLE:
        if period == "day":
            # For daily rollups, take the latest single-day observation
            sorted_snaps = sorted(snapshots, key=lambda s: (s.bucket_timestamp, s.captured_at))
            return sorted_snaps[-1].metric_value.quantize(Decimal("0.0001")), metadata
        else:
            # Over multi-day periods (week, month), daily uniques CANNOT be mathematically summed.
            # Check if any snapshot explicitly has native multi-day period from provider.
            native_multi_day = [s for s in snapshots if s.bucket_period == period]
            if native_multi_day:
                sorted_multi = sorted(native_multi_day, key=lambda s: (s.bucket_timestamp, s.captured_at))
                metadata["provider_native_period"] = period
                return sorted_multi[-1].metric_value.quantize(Decimal("0.0001")), metadata

            # Strictly refuse to invent reach by summation
            metadata["is_available"] = False
            metadata["unavailable_reason"] = (
                f"Cannot sum {normalized_metric} across {len(snapshots)} daily observations into a multi-day {period} period. "
                "Audience overlap prevents mathematical summation."
            )
            return Decimal("0.0000"), metadata

    # Fallback to sum
    total = sum((s.metric_value for s in snapshots), Decimal("0"))
    return total.quantize(Decimal("0.0001")), metadata


@transaction.atomic
def build_rollups_for_client(
    client_id: int,
    platform: Optional[str] = None,
    periods: Tuple[str, ...] = ("day", "week", "month"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, int]:
    """
    Materializes SocialMetricRollup records for a client from existing SocialMetricSnapshots.
    Operates idempotently: existing records for the same unique tuple are updated in place.
    """
    client = Client.objects.get(id=client_id)
    client_tz = get_client_timezone(client)

    qs = SocialMetricSnapshot.objects.filter(client=client)
    if platform:
        qs = qs.filter(platform=platform)
    if start_date:
        qs = qs.filter(bucket_timestamp__date__gte=start_date)
    if end_date:
        qs = qs.filter(bucket_timestamp__date__lte=end_date)

    snapshots = list(qs)
    created_count = 0
    updated_count = 0

    for period in periods:
        # Group snapshots by unique rollup identity tuple
        grouped: Dict[Tuple, List[SocialMetricSnapshot]] = defaultdict(list)

        for s in snapshots:
            p_start = calculate_period_start(s.bucket_timestamp, period, client_tz)
            key = (
                s.platform,
                s.metric_scope,
                s.object_id,
                s.normalized_metric,
                s.dimensions_hash or "",
                p_start,
            )
            grouped[key].append(s)

        for (plat, scope, obj_id, metric, dim_hash, p_start), snap_group in grouped.items():
            val, agg_meta = aggregate_snapshots(snap_group, metric, period)
            extra_dims = snap_group[0].extra_dimensions or {}

            # Linkage metadata
            sample_snap = snap_group[0]
            rollup_meta = {
                **agg_meta,
                "timezone": str(client_tz),
                "unified_post_id": sample_snap.unified_post_id,
                "publish_log_id": sample_snap.publish_log_id,
            }

            rollup, created = SocialMetricRollup.objects.update_or_create(
                client=client,
                platform=plat,
                metric_scope=scope,
                object_id=obj_id,
                normalized_metric=metric,
                dimensions_hash=dim_hash,
                period=period,
                period_start=p_start,
                defaults={
                    "metric_value": val,
                    "extra_dimensions": extra_dims,
                    "sample_count": len(snap_group),
                    "metadata": rollup_meta,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

    logger.info(
        f"Built rollups for client {client_id} (platform={platform or 'all'}): "
        f"created={created_count}, updated={updated_count}"
    )
    return {"created": created_count, "updated": updated_count}
