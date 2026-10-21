"""
Analytics API Read Layer for Bop Social.
Provides tenant-isolated, dashboard-ready summary, trend, and top-posts views.
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Max, Avg, Q
from django.utils import timezone

from social_stats.models import (
    Client,
    SocialMetricRollup,
    SocialMetricSnapshot,
    UnifiedPost,
    PlatformPublishLog,
)
from .freshness import get_client_platform_freshness
from .registry import AggregationBehavior, CANONICAL_METRICS

logger = logging.getLogger(__name__)


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


class AnalyticsBaseView(APIView):
    """Base view providing tenant validation and parameter parsing."""
    permission_classes = [permissions.IsAuthenticated]

    def validate_client(self, request, client_id_raw) -> Optional[Client]:
        if not client_id_raw:
            return None
        try:
            client_id = int(client_id_raw)
        except (ValueError, TypeError):
            return None

        # Staff can view any client; regular user can only view their own client
        qs = Client.objects.filter(id=client_id, is_active=True)
        if not request.user.is_staff:
            qs = qs.filter(owner_user=request.user)

        return qs.first()


class AnalyticsSummaryView(AnalyticsBaseView):
    """
    GET /api/analytics/summary/
    Returns aggregated metric cards for a client across selected date range and platform.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        period = request.query_params.get("period", "day")
        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))
        metric_filter = request.query_params.get("metric")

        qs = SocialMetricRollup.objects.filter(client=client, period=period)
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_start__lte=end_date)
        if metric_filter:
            qs = qs.filter(normalized_metric=metric_filter)

        # Aggregate across rollups according to each metric's aggregation behavior
        rollups = list(qs)
        metrics_data: Dict[str, Dict] = {}

        # Group rollups by normalized_metric
        by_metric: Dict[str, List[SocialMetricRollup]] = {}
        for r in rollups:
            by_metric.setdefault(r.normalized_metric, []).append(r)

        for m_key, r_list in by_metric.items():
            defn = CANONICAL_METRICS.get(m_key)
            behavior = defn.aggregation_behavior if defn else AggregationBehavior.SUMMABLE

            if behavior == AggregationBehavior.LATEST_VALUE:
                latest_r = max(r_list, key=lambda x: x.period_start)
                val = latest_r.metric_value
            elif behavior == AggregationBehavior.AVERAGE:
                val = sum((r.metric_value for r in r_list), Decimal("0")) / Decimal(str(len(r_list)))
            elif behavior == AggregationBehavior.NON_AGGREGATABLE:
                # If single rollup, return its value; if multiple across days, mark caveat
                if len(r_list) == 1:
                    val = r_list[0].metric_value
                else:
                    # Multi-period reach caveat
                    latest_r = max(r_list, key=lambda x: x.period_start)
                    val = latest_r.metric_value
            else:
                val = sum((r.metric_value for r in r_list), Decimal("0"))

            comparability_warning = None
            if not platform or platform == "all":
                if defn and "Not directly" in defn.cross_platform_comparability:
                    comparability_warning = defn.cross_platform_comparability

            metrics_data[m_key] = {
                "metric_key": m_key,
                "display_name": defn.display_name if defn else m_key,
                "value": float(val),
                "unit": defn.unit.value if defn else "count",
                "aggregation_behavior": behavior.value,
                "sample_count": sum(r.sample_count for r in r_list),
                "comparability_warning": comparability_warning,
            }

        freshness_info = get_client_platform_freshness(client.id, platform or "facebook")

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "period": period,
            "date_range": {
                "start": str(start_date) if start_date else None,
                "end": str(end_date) if end_date else None,
            },
            "metrics": metrics_data,
            "freshness": freshness_info,
        })


class AnalyticsTrendsView(AnalyticsBaseView):
    """
    GET /api/analytics/trends/
    Returns chronological timeseries points for a single metric.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        metric = request.query_params.get("metric")
        if not metric:
            return Response({"error": "Query param 'metric' is required"}, status=status.HTTP_400_BAD_REQUEST)

        platform = request.query_params.get("platform")
        period = request.query_params.get("period", "day")
        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))

        qs = SocialMetricRollup.objects.filter(
            client=client,
            normalized_metric=metric,
            period=period,
        )
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_start__lte=end_date)

        rollups = qs.order_by("period_start")
        datapoints = []
        for r in rollups:
            datapoints.append({
                "period_start": str(r.period_start),
                "metric_value": float(r.metric_value),
                "sample_count": r.sample_count,
                "dimensions_hash": r.dimensions_hash,
                "extra_dimensions": r.extra_dimensions,
                "is_available": r.metadata.get("is_available", True),
            })

        defn = CANONICAL_METRICS.get(metric)
        freshness_info = get_client_platform_freshness(client.id, platform or "facebook")

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "metric": metric,
            "display_name": defn.display_name if defn else metric,
            "period": period,
            "datapoints": datapoints,
            "freshness": freshness_info,
        })


class AnalyticsTopPostsView(AnalyticsBaseView):
    """
    GET /api/analytics/top-posts/
    Returns ranked posts by engagement/reaction metrics, distinguishing Bop-authored vs external posts.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        ranking_metric = request.query_params.get("metric", "REACTIONS")
        try:
            limit = min(50, max(1, int(request.query_params.get("limit", 10))))
        except (ValueError, TypeError):
            limit = 10

        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))

        qs = SocialMetricSnapshot.objects.filter(
            client=client,
            metric_scope__in=["post", "video", "reel"],
            normalized_metric=ranking_metric,
        )
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if start_date:
            qs = qs.filter(bucket_timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(bucket_timestamp__date__lte=end_date)

        # Distinct latest observations by object_id
        snapshots = qs.order_by("-metric_value", "-bucket_timestamp")[:limit]

        posts_data = []
        for s in snapshots:
            is_bop = bool(s.unified_post_id or s.publish_log_id)
            post_entry = {
                "object_id": s.object_id,
                "platform": s.platform,
                "metric": s.normalized_metric,
                "metric_value": float(s.metric_value),
                "is_bop_authored": is_bop,
                "unified_post_id": s.unified_post_id,
                "publish_log_id": s.publish_log_id,
                "bucket_timestamp": s.bucket_timestamp.isoformat(),
                "media_type": s.metadata.get("media_type") or s.metadata.get("post_type", "post"),
            }
            posts_data.append(post_entry)

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "ranking_metric": ranking_metric,
            "count": len(posts_data),
            "posts": posts_data,
        })
