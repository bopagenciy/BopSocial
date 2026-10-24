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
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    UnifiedPost,
    PlatformPublishLog,
    PostMetric,
)
from .capabilities import get_provider_capability, SupportLevel
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
    Returns aggregated metric cards for a client across selected date range and platform,
    with full capability-awareness, reach safety, and data health status.
    """

    CANDIDATE_KPIS = [
        "FOLLOWERS_TOTAL",
        "FOLLOWERS_NET_CHANGE",
        "ENGAGEMENT_TOTAL",
        "REACTIONS",
        "COMMENTS",
        "SHARES",
        "PROFILE_VIEWS",
        "VIDEO_VIEWS",
        "REACH",
    ]

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        period = request.query_params.get("period", "day")
        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))
        metric_filter = request.query_params.get("metric")

        # Discover client platform capabilities safely (defer encrypted tokens)
        creds = list(PlatformCredential.objects.defer("access_token", "refresh_token").filter(client=client, is_active=True))
        capabilities = {}
        for cred in creds:
            cap = get_provider_capability(cred.platform, cred)
            status_str = "FULL" if cap.overall_support == SupportLevel.SUPPORTED else ("PARTIAL" if cap.overall_support == SupportLevel.PARTIAL else "UNSUPPORTED")
            guidance = None
            if cred.platform == "instagram" and status_str == "PARTIAL":
                guidance = "Advanced Instagram insights require additional Meta permissions."
            capabilities[cred.platform] = {
                "platform": cred.platform,
                "display_name": cap.display_name,
                "status": status_str,
                "notes": cap.notes,
                "permission_guidance": guidance,
                "supports_reach": cap.supports_reach,
                "supports_impressions": cap.supports_impressions,
                "supports_clicks": cap.supports_clicks,
                "supports_video_metrics": cap.supports_video_metrics,
            }

        # Instagram partial mode supported metrics
        ig_supported_metrics = {"FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"}

        qs = SocialMetricRollup.objects.filter(client=client, period=period)
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_start__lte=end_date)
        if metric_filter:
            qs = qs.filter(normalized_metric=metric_filter)

        rollups = list(qs)
        metrics_data: Dict[str, Dict] = {}

        # Group rollups by normalized_metric
        by_metric: Dict[str, List[SocialMetricRollup]] = {}
        for r in rollups:
            by_metric.setdefault(r.normalized_metric, []).append(r)

        # Keys to evaluate: candidate KPIs or filtered
        keys_to_evaluate = [metric_filter] if metric_filter else self.CANDIDATE_KPIS
        # Also include any rollups present that are not in candidate KPIs
        for m_key in by_metric.keys():
            if m_key not in keys_to_evaluate:
                keys_to_evaluate.append(m_key)

        for m_key in keys_to_evaluate:
            defn = CANONICAL_METRICS.get(m_key)
            behavior = defn.aggregation_behavior if defn else AggregationBehavior.SUMMABLE
            r_list = by_metric.get(m_key, [])

            # Check Instagram partial degradation
            if platform == "instagram" and m_key not in ig_supported_metrics:
                metrics_data[m_key] = {
                    "metric_key": m_key,
                    "display_name": defn.display_name if defn else m_key,
                    "value": None,
                    "is_available": False,
                    "unavailable_reason": "Not available with current Instagram permissions",
                    "permission_guidance": "Advanced Instagram insights require additional Meta permissions.",
                    "unit": defn.unit.value if defn else "count",
                    "aggregation_behavior": behavior.value,
                    "sample_count": 0,
                    "comparability_warning": None,
                }
                continue

            # REACH Aggregation Safety
            if m_key == "REACH":
                if period in ("week", "month"):
                    metrics_data["REACH"] = {
                        "metric_key": "REACH",
                        "display_name": "Reach",
                        "value": None,
                        "is_available": False,
                        "unavailable_reason": "Unavailable for aggregated period",
                        "caveat": "Unique daily audiences cannot be safely summed across days.",
                        "unit": "count",
                        "aggregation_behavior": AggregationBehavior.NON_AGGREGATABLE.value,
                        "sample_count": sum(r.sample_count for r in r_list),
                        "comparability_warning": "Unique daily audiences cannot be safely summed across days.",
                    }
                    continue
                elif period == "day" and len(r_list) > 1 and not start_date and not end_date:
                    # Multi-day range without single day
                    latest_r = max(r_list, key=lambda x: x.period_start)
                    metrics_data["REACH"] = {
                        "metric_key": "REACH",
                        "display_name": "Reach",
                        "value": float(latest_r.metric_value) if latest_r.metadata.get("is_available", True) else None,
                        "is_available": latest_r.metadata.get("is_available", True),
                        "unavailable_reason": None if latest_r.metadata.get("is_available", True) else "Unavailable for aggregated period",
                        "caveat": "Unique daily audiences cannot be safely summed across days.",
                        "unit": "count",
                        "aggregation_behavior": AggregationBehavior.NON_AGGREGATABLE.value,
                        "sample_count": sum(r.sample_count for r in r_list),
                        "comparability_warning": "Showing latest single day observation; unique daily audiences cannot be summed across days.",
                    }
                    continue

            if not r_list:
                # Metric supported but has no rollup observations in the requested window
                metrics_data[m_key] = {
                    "metric_key": m_key,
                    "display_name": defn.display_name if defn else m_key,
                    "value": None,
                    "is_available": False,
                    "unavailable_reason": "No observations in selected window",
                    "unit": defn.unit.value if defn else "count",
                    "aggregation_behavior": behavior.value,
                    "sample_count": 0,
                    "comparability_warning": None,
                }
                continue

            if behavior == AggregationBehavior.LATEST_VALUE:
                latest_r = max(r_list, key=lambda x: x.period_start)
                val = latest_r.metric_value
            elif behavior == AggregationBehavior.AVERAGE:
                val = sum((r.metric_value for r in r_list), Decimal("0")) / Decimal(str(len(r_list)))
            elif behavior == AggregationBehavior.NON_AGGREGATABLE:
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
                "is_available": True,
                "unavailable_reason": None,
                "unit": defn.unit.value if defn else "count",
                "aggregation_behavior": behavior.value,
                "sample_count": sum(r.sample_count for r in r_list),
                "comparability_warning": comparability_warning,
            }

        freshness_info = get_client_platform_freshness(client.id, platform or "facebook")

        # Health panel summaries
        fb_fresh = get_client_platform_freshness(client.id, "facebook")
        ig_fresh = get_client_platform_freshness(client.id, "instagram")
        data_health = [
            {
                "platform": "facebook",
                "display_name": "Facebook Page",
                "capability_mode": capabilities.get("facebook", {}).get("status", "FULL"),
                "freshness_status": fb_fresh.get("status", "Fresh"),
                "last_synced_at": fb_fresh.get("last_synced_at"),
                "age_seconds": fb_fresh.get("age_seconds"),
                "permission_guidance": None,
            },
            {
                "platform": "instagram",
                "display_name": "Instagram Professional",
                "capability_mode": capabilities.get("instagram", {}).get("status", "PARTIAL"),
                "freshness_status": ig_fresh.get("status", "Fresh"),
                "last_synced_at": ig_fresh.get("last_synced_at"),
                "age_seconds": ig_fresh.get("age_seconds"),
                "permission_guidance": "Advanced Instagram insights require additional Meta permissions.",
            },
        ]

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "period": period,
            "date_range": {
                "start": str(start_date) if start_date else None,
                "end": str(end_date) if end_date else None,
            },
            "capabilities": capabilities,
            "metrics": metrics_data,
            "freshness": freshness_info,
            "data_health": data_health,
        })


class AnalyticsTrendsView(AnalyticsBaseView):
    """
    GET /api/analytics/trends/
    Returns chronological timeseries points for a single metric with reach and capability handling.
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

        defn = CANONICAL_METRICS.get(metric)
        freshness_info = get_client_platform_freshness(client.id, platform or "facebook")

        # Check Instagram partial degradation
        ig_supported_metrics = {"FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"}
        if platform == "instagram" and metric not in ig_supported_metrics:
            return Response({
                "client_id": client.id,
                "platform": "instagram",
                "metric": metric,
                "display_name": defn.display_name if defn else metric,
                "period": period,
                "is_available": False,
                "unavailable_reason": "Not available with current Instagram permissions",
                "permission_guidance": "Advanced Instagram insights require additional Meta permissions.",
                "datapoints": [],
                "freshness": freshness_info,
            })

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
            # Check reach caveat for week/month
            is_avail = r.metadata.get("is_available", True)
            val = float(r.metric_value) if is_avail else None
            datapoints.append({
                "period_start": str(r.period_start),
                "metric_value": val,
                "sample_count": r.sample_count,
                "dimensions_hash": r.dimensions_hash,
                "extra_dimensions": r.extra_dimensions,
                "is_available": is_avail,
            })

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "metric": metric,
            "display_name": defn.display_name if defn else metric,
            "period": period,
            "is_available": True,
            "datapoints": datapoints,
            "freshness": freshness_info,
        })


class AnalyticsTopPostsView(AnalyticsBaseView):
    """
    GET /api/analytics/top-posts/
    Returns ranked posts by engagement/reaction metrics, strictly deduplicated by unique content identity,
    distinguishing Bop-authored vs external organic content.
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
        )
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if start_date:
            qs = qs.filter(bucket_timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(bucket_timestamp__date__lte=end_date)

        snapshots = list(qs.order_by("-bucket_timestamp"))

        # Deduplicate strictly by (platform, object_id) - one post appears once in ranking
        post_objects: Dict = {}
        for s in snapshots:
            key = (s.platform, s.object_id)
            if key not in post_objects:
                post_objects[key] = {
                    "object_id": s.object_id,
                    "platform": s.platform,
                    "unified_post_id": s.unified_post_id,
                    "publish_log_id": s.publish_log_id,
                    "media_type": s.metadata.get("media_type") or s.metadata.get("post_type") or "post",
                    "bucket_timestamp": s.bucket_timestamp,
                    "metrics": {},
                }
            if s.normalized_metric not in post_objects[key]["metrics"]:
                post_objects[key]["metrics"][s.normalized_metric] = float(s.metric_value)

        # Preload PostMetrics and PlatformPublishLogs for metadata enrichment
        obj_ids = [k[1] for k in post_objects.keys()]
        pms = {pm.post_id: pm for pm in PostMetric.objects.filter(client=client, post_id__in=obj_ids)}
        pub_logs = {pl.platform_post_id: pl for pl in PlatformPublishLog.objects.filter(unified_post__client=client, platform_post_id__in=obj_ids)}

        ranked_posts = []
        for key, pdata in post_objects.items():
            platform_name, obj_id = key
            pm = pms.get(obj_id)
            pl = pub_logs.get(obj_id)

            is_bop = bool(pdata["unified_post_id"] or pdata["publish_log_id"] or pl or (pm and pm.unified_post_id))
            unified_id = pdata["unified_post_id"] or (pl.unified_post_id if pl else None) or (pm.unified_post_id if pm else None)

            caption = pm.caption if pm and pm.caption else ""
            if not caption and is_bop and unified_id:
                up = UnifiedPost.objects.filter(id=unified_id).first()
                if up:
                    caption = up.content or up.title or ""

            permalink = pm.post_url if pm and pm.post_url else (pl.platform_url if pl else None)
            media_type = pm.post_type if pm and pm.post_type else pdata["media_type"]
            published_at = pm.published_at.isoformat() if pm and pm.published_at else pdata["bucket_timestamp"].isoformat()

            rank_val = pdata["metrics"].get(ranking_metric, 0.0)

            ranked_posts.append({
                "object_id": obj_id,
                "platform": platform_name,
                "ranking_metric": ranking_metric,
                "ranking_value": rank_val,
                "is_bop_authored": is_bop,
                "source_label": "Published by Bop Social" if is_bop else "Organic / External",
                "unified_post_id": unified_id,
                "caption": caption,
                "permalink": permalink,
                "media_type": media_type,
                "published_at": published_at,
                "metrics": pdata["metrics"],
            })

        # Rank strictly by requested ranking metric value descending, then published_at descending
        ranked_posts.sort(key=lambda p: (p["ranking_value"], p["published_at"]), reverse=True)
        ranked_posts = ranked_posts[:limit]

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "ranking_metric": ranking_metric,
            "count": len(ranked_posts),
            "posts": ranked_posts,
        })


class AnalyticsInsightsView(AnalyticsBaseView):
    """
    GET /api/analytics/insights/
    Returns deterministic business intelligence signals for a client across a date window.
    Supports filtering by platform, signal_type, severity, confidence, and actionability.
    Tenant-isolated and capability-aware. Zero generative AI.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        metric_param = request.query_params.get("metric")
        start_date = _parse_date(request.query_params.get("date_from") or request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("date_to") or request.query_params.get("end_date"))
        signal_type = request.query_params.get("signal_type")
        severity = request.query_params.get("severity")
        confidence = request.query_params.get("confidence")
        is_actionable = request.query_params.get("is_actionable")
        scope = request.query_params.get("scope")

        from .intelligence.service import generate_business_signals

        signals = generate_business_signals(
            client_id=client.id,
            date_from=start_date,
            date_to=end_date,
            platform=platform,
            metric=metric_param,
            persist=False,
        )

        # Apply optional query filters
        filtered = []
        for s in signals:
            if metric_param and s.get("metric") and s.get("metric").upper() != metric_param.upper():
                continue
            if signal_type and s.get("signal_type") != signal_type:
                continue
            if severity and s.get("severity") != severity:
                continue
            if confidence and s.get("confidence_level") != confidence:
                continue
            if scope and s.get("scope") != scope:
                continue
            if is_actionable is not None:
                want_act = is_actionable.lower() in ("true", "1")
                if s.get("is_actionable") != want_act:
                    continue

            # Format signal for public JSON serialization
            filtered.append({
                "signal_identity": s["signal_identity"],
                "platform": s["platform"],
                "signal_type": s["signal_type"],
                "metric": s["metric"],
                "scope": s["scope"],
                "object_id": s["object_id"],
                "unified_post_id": s["unified_post_id"],
                "period_start": str(s["period_start"]),
                "period_end": str(s["period_end"]),
                "observed_value": float(s["observed_value"]) if s["observed_value"] is not None else None,
                "baseline_value": float(s["baseline_value"]) if s["baseline_value"] is not None else None,
                "absolute_delta": float(s["absolute_delta"]) if s["absolute_delta"] is not None else None,
                "relative_delta": float(s["relative_delta"]) if s["relative_delta"] is not None else None,
                "sample_size": s["sample_size"],
                "confidence_level": s["confidence_level"],
                "direction": s["direction"],
                "severity": s["severity"],
                "is_actionable": s["is_actionable"],
                "explanation": s["explanation"],
                "evidence": s["evidence"],
                "cohort_hash": s["cohort_hash"],
                "created_at": s["created_at"],
            })

        response_payload = {
            "client_id": client.id,
            "platform": platform or "all",
            "period": {
                "start": str(start_date) if start_date else None,
                "end": str(end_date) if end_date else None,
            },
            "count": len(filtered),
            "signals": filtered,
        }

        if metric_param:
            response_payload["metric"] = metric_param
            if (platform or "").lower() == "instagram" and metric_param.upper() == "ENGAGEMENT_TOTAL":
                response_payload["is_available"] = False
                response_payload["reason"] = "missing_required_components"
                response_payload["missing_components"] = ["SHARES"]
                response_payload["message"] = "Not available with current Instagram permissions"

        return Response(response_payload)


class AnalyticsExecutiveSummaryView(AnalyticsBaseView):
    """
    GET /api/analytics/executive-summary/
    Returns structured deterministic executive summary fields including:
    best_performing_content, weakest_performing_content, engagement_direction,
    follower_direction, winning_formats, posting_time_insights, platform_health,
    data_quality, and key_signals.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        start_date = _parse_date(request.query_params.get("date_from") or request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("date_to") or request.query_params.get("end_date"))

        from .intelligence.service import get_executive_summary

        summary = get_executive_summary(
            client_id=client.id,
            date_from=start_date,
            date_to=end_date,
            platform=platform,
        )

        return Response(summary)


class AnalyticsInsightsHistoryView(AnalyticsBaseView):
    """
    GET /api/analytics/insights/history/
    Returns historical persisted BusinessSignals for client review.
    Tenant-isolated.
    """

    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform = request.query_params.get("platform")
        signal_type = request.query_params.get("signal_type")
        severity = request.query_params.get("severity")
        start_date = _parse_date(request.query_params.get("date_from") or request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("date_to") or request.query_params.get("end_date"))

        from social_stats.models import BusinessSignal

        qs = BusinessSignal.objects.filter(client=client)
        if platform and platform != "all":
            qs = qs.filter(platform=platform)
        if signal_type:
            qs = qs.filter(signal_type=signal_type)
        if severity:
            qs = qs.filter(severity=severity)
        if start_date:
            qs = qs.filter(period_start__gte=start_date)
        if end_date:
            qs = qs.filter(period_end__lte=end_date)

        records = list(qs.order_by("-period_end", "-created_at")[:100])
        signals_data = []
        for s in records:
            signals_data.append({
                "id": s.id,
                "signal_identity": s.signal_identity,
                "platform": s.platform,
                "signal_type": s.signal_type,
                "metric": s.metric,
                "scope": s.scope,
                "object_id": s.object_id,
                "unified_post_id": s.unified_post_id,
                "period_start": str(s.period_start),
                "period_end": str(s.period_end),
                "observed_value": float(s.observed_value) if s.observed_value is not None else None,
                "baseline_value": float(s.baseline_value) if s.baseline_value is not None else None,
                "absolute_delta": float(s.absolute_delta) if s.absolute_delta is not None else None,
                "relative_delta": float(s.relative_delta) if s.relative_delta is not None else None,
                "sample_size": s.sample_size,
                "confidence_level": s.confidence_level,
                "direction": s.direction,
                "severity": s.severity,
                "is_actionable": s.is_actionable,
                "explanation": s.explanation_template,
                "evidence": s.evidence,
                "created_at": s.created_at.isoformat(),
            })

        return Response({
            "client_id": client.id,
            "platform": platform or "all",
            "count": len(signals_data),
            "signals": signals_data,
        })


# ── BS-4G Executive Reporting API Views ──────────────────────────────────────
from datetime import timedelta
from django.http import FileResponse, Http404
from social_stats.models import ExecutiveReport, ExecutiveNarrative
from .reporting.service import (
    preview_executive_report,
    save_executive_report,
    generate_pdf_for_report,
    delete_executive_report,
)
from .narrative import (
    preview_narrative,
    generate_and_save_narrative,
    get_latest_narrative_for_report,
)


class ExecutiveReportPreviewView(AnalyticsBaseView):
    """
    POST /api/analytics/reports/preview/
    Read-only preview generation.
    Computes deterministic executive report JSON payload without DB persistence.
    """

    def post(self, request):
        client_id_raw = request.data.get('client_id') or request.query_params.get('client_id')
        client = self.validate_client(request, client_id_raw)
        if not client:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        start_date = _parse_date(request.data.get('date_from') or request.data.get('start_date'))
        end_date = _parse_date(request.data.get('date_to') or request.data.get('end_date'))

        today = timezone.now().date()
        end_date = end_date or today
        start_date = start_date or (end_date - timedelta(days=30))

        platform = request.data.get('platform')
        language = request.data.get('language', 'es')
        report_type = request.data.get('report_type', 'EXECUTIVE')

        try:
            report_data = preview_executive_report(
                client_id=client.id,
                date_from=start_date,
                date_to=end_date,
                platform=platform,
                language=language,
                report_type=report_type,
            )
            return Response(report_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f'Error previewing executive report for client {client.id}: {e}')
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExecutiveReportListView(AnalyticsBaseView):
    """
    GET  /api/analytics/reports/  — List saved executive reports for client
    POST /api/analytics/reports/  — Persist an executive report
    """

    def get(self, request):
        client_id_raw = request.query_params.get('client_id')
        client = self.validate_client(request, client_id_raw)
        if not client:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        report_type = request.query_params.get('report_type')
        status_param = request.query_params.get('status')

        qs = ExecutiveReport.objects.filter(client=client)
        if report_type:
            qs = qs.filter(report_type=report_type)
        if status_param:
            qs = qs.filter(status=status_param)

        reports = []
        for r in qs.order_by('-period_end', '-generated_at')[:50]:
            pdf_url = None
            if r.pdf_file:
                pdf_url = request.build_absolute_uri(f'/api/analytics/reports/{r.id}/download/')

            reports.append({
                'id': r.id,
                'client_id': r.client_id,
                'title': r.title,
                'report_type': r.report_type,
                'period_start': r.period_start.isoformat(),
                'period_end': r.period_end.isoformat(),
                'platform_filter': r.platform_filter,
                'language': r.language,
                'status': r.status,
                'generated_at': r.generated_at.isoformat(),
                'source_rollup_count': r.source_rollup_count,
                'source_signal_count': r.source_signal_count,
                'source_hash': r.source_hash,
                'has_pdf': bool(r.pdf_file),
                'pdf_checksum': r.pdf_checksum,
                'pdf_url': pdf_url,
                'template_version': r.template_version,
            })

        return Response({
            'client_id': client.id,
            'count': len(reports),
            'reports': reports,
        })

    def post(self, request):
        client_id_raw = request.data.get('client_id')
        client = self.validate_client(request, client_id_raw)
        if not client:
            return Response({'error': 'Client not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        start_date = _parse_date(request.data.get('date_from') or request.data.get('start_date'))
        end_date = _parse_date(request.data.get('date_to') or request.data.get('end_date'))

        today = timezone.now().date()
        end_date = end_date or today
        start_date = start_date or (end_date - timedelta(days=30))

        platform = request.data.get('platform')
        language = request.data.get('language', 'es')
        report_type = request.data.get('report_type', 'EXECUTIVE')
        title = request.data.get('title')

        try:
            report = save_executive_report(
                client_id=client.id,
                date_from=start_date,
                date_to=end_date,
                platform=platform,
                language=language,
                report_type=report_type,
                user=request.user,
                title=title,
            )
            return Response({
                'id': report.id,
                'client_id': report.client_id,
                'title': report.title,
                'report_type': report.report_type,
                'period_start': report.period_start.isoformat(),
                'period_end': report.period_end.isoformat(),
                'language': report.language,
                'status': report.status,
                'generated_at': report.generated_at.isoformat(),
                'source_rollup_count': report.source_rollup_count,
                'source_signal_count': report.source_signal_count,
                'source_hash': report.source_hash,
                'report_data': report.report_data,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception(f'Error saving executive report: {e}')
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExecutiveReportDetailView(AnalyticsBaseView):
    """
    GET    /api/analytics/reports/<int:pk>/  — Retrieve full report metadata and report_data
    DELETE /api/analytics/reports/<int:pk>/  — Delete report without touching analytics source
    """

    def _get_authorized_report(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            return None
        # Tenant isolation
        client = self.validate_client(request, report.client_id)
        if not client:
            return None
        return report

    def get(self, request, pk):
        report = self._get_authorized_report(request, pk)
        if not report:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        pdf_url = None
        if report.pdf_file:
            pdf_url = request.build_absolute_uri(f'/api/analytics/reports/{report.id}/download/')

        return Response({
            'id': report.id,
            'client_id': report.client_id,
            'title': report.title,
            'report_type': report.report_type,
            'period_start': report.period_start.isoformat(),
            'period_end': report.period_end.isoformat(),
            'platform_filter': report.platform_filter,
            'language': report.language,
            'status': report.status,
            'generated_at': report.generated_at.isoformat(),
            'source_rollup_count': report.source_rollup_count,
            'source_signal_count': report.source_signal_count,
            'source_hash': report.source_hash,
            'has_pdf': bool(report.pdf_file),
            'pdf_checksum': report.pdf_checksum,
            'pdf_url': pdf_url,
            'template_version': report.template_version,
            'report_data': report.report_data,
        })

    def delete(self, request, pk):
        report = self._get_authorized_report(request, pk)
        if not report:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        delete_executive_report(report.id, report.client)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExecutiveReportGeneratePDFView(AnalyticsBaseView):
    """
    POST /api/analytics/reports/<int:pk>/pdf/
    Renders deterministic PDF using WeasyPrint and saves to media storage.
    """

    def post(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

        client = self.validate_client(request, report.client_id)
        if not client:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        try:
            report, _ = generate_pdf_for_report(report)
            pdf_url = request.build_absolute_uri(f'/api/analytics/reports/{report.id}/download/')
            return Response({
                'id': report.id,
                'status': report.status,
                'pdf_checksum': report.pdf_checksum,
                'pdf_url': pdf_url,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f'Error generating PDF for report {report.id}: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExecutiveReportDownloadPDFView(AnalyticsBaseView):
    """
    GET /api/analytics/reports/<int:pk>/download/
    Authenticated streaming download of generated PDF report.
    Never exposes internal filesystem paths.
    """

    def get(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            raise Http404('Report not found')

        client = self.validate_client(request, report.client_id)
        if not client:
            raise Http404('Report not found or unauthorized')

        if not report.pdf_file:
            # Auto-generate if missing
            report, _ = generate_pdf_for_report(report)

        try:
            company_clean = (report.client.company or 'client').replace(' ', '_')
            safe_filename = f"{company_clean}_Report_{report.period_start.isoformat()}_{report.period_end.isoformat()}.pdf"
            response = FileResponse(report.pdf_file.open('rb'), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
            return response
        except Exception as e:
            logger.exception(f'Error downloading PDF for report {report.id}: {e}')
            raise Http404('PDF file could not be read')


# ── BS-4H Grounded AI Narrative API Views ───────────────────────────────────

class ReportNarrativePreviewView(AnalyticsBaseView):
    """
    POST /api/analytics/reports/<int:pk>/narrative/preview/
    Generates deterministic preview of AI narrative for a report.
    Guarantees 0 database rows are created.
    """

    def post(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
        client = self.validate_client(request, report.client_id)
        if not client:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        language = request.data.get('language') or report.language
        style = request.data.get('style', 'EXECUTIVE')
        provider = request.data.get('provider', 'fake')
        mock_mode = request.data.get('mock_mode', 'VALID')

        try:
            preview_data = preview_narrative(
                report=report,
                language=language,
                style=style,
                provider_name=provider,
                mock_mode=mock_mode,
            )
            return Response(preview_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f'Error previewing narrative for report {report.id}: {e}')
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReportNarrativeView(AnalyticsBaseView):
    """
    GET  /api/analytics/reports/<int:pk>/narrative/  — Retrieve latest narrative with stale detection
    POST /api/analytics/reports/<int:pk>/narrative/  — Generate and persist narrative
    """

    def get(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
        client = self.validate_client(request, report.client_id)
        if not client:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        narrative, is_stale = get_latest_narrative_for_report(report)
        if not narrative:
            return Response({
                'status': 'NOT_GENERATED',
                'narrative': None,
                'is_stale': False,
            }, status=status.HTTP_200_OK)

        return Response({
            'id': narrative.id,
            'report_id': narrative.executive_report_id,
            'client_id': narrative.client_id,
            'status': narrative.status,
            'language': narrative.language,
            'provider': narrative.provider,
            'model_name': narrative.model_name,
            'prompt_version': narrative.prompt_version,
            'context_schema_version': narrative.context_schema_version,
            'source_hash': narrative.source_hash,
            'context_hash': narrative.context_hash,
            'narrative': narrative.narrative_json,
            'rendered_text': narrative.rendered_text,
            'validation_status': narrative.validation_status,
            'validation_results': narrative.validation_results,
            'is_stale': is_stale,
            'generated_at': narrative.generated_at.isoformat(),
        }, status=status.HTTP_200_OK)

    def post(self, request, pk):
        report = ExecutiveReport.objects.filter(id=pk).first()
        if not report:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
        client = self.validate_client(request, report.client_id)
        if not client:
            return Response({'error': 'Report not found or unauthorized'}, status=status.HTTP_404_NOT_FOUND)

        language = request.data.get('language') or report.language
        style = request.data.get('style', 'EXECUTIVE')
        provider = request.data.get('provider', 'fake')
        mock_mode = request.data.get('mock_mode', 'VALID')
        force_regenerate = bool(request.data.get('force_regenerate', False))

        try:
            narrative = generate_and_save_narrative(
                report=report,
                user=request.user,
                language=language,
                style=style,
                provider_name=provider,
                mock_mode=mock_mode,
                force_regenerate=force_regenerate,
            )
            return Response({
                'id': narrative.id,
                'report_id': narrative.executive_report_id,
                'client_id': narrative.client_id,
                'status': narrative.status,
                'language': narrative.language,
                'provider': narrative.provider,
                'model_name': narrative.model_name,
                'prompt_version': narrative.prompt_version,
                'context_schema_version': narrative.context_schema_version,
                'source_hash': narrative.source_hash,
                'context_hash': narrative.context_hash,
                'narrative': narrative.narrative_json,
                'rendered_text': narrative.rendered_text,
                'validation_status': narrative.validation_status,
                'validation_results': narrative.validation_results,
                'is_stale': narrative.is_stale,
                'generated_at': narrative.generated_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception(f'Error generating narrative for report {report.id}: {e}')
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


ReportNarrativeSaveView = ReportNarrativeView
ReportNarrativeDetailView = ReportNarrativeView




# ==============================================================================
# BS-5A MULTICHANNEL METRIC COMPATIBILITY & COMPARISON VIEWS
# ==============================================================================

class MultichannelCompatibilityView(AnalyticsBaseView):
    """
    GET /api/analytics/multichannel/compatibility/
    Read-only view exposing cross-platform metric compatibility matrix and rules.
    Tenant-safe: requires authentication; optional client_id parameter is validated.
    """
    def get(self, request):
        client_id_raw = request.query_params.get("client_id")
        if client_id_raw:
            client = self.validate_client(request, client_id_raw)
            if not client:
                return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        platform_a = request.query_params.get("platform_a", "facebook")
        platform_b = request.query_params.get("platform_b", "instagram")
        metric_filter = request.query_params.get("metric")

        from .multichannel import get_metric_comparison_rule, FB_IG_RULES, get_reason_labels

        if metric_filter:
            rule = get_metric_comparison_rule(metric_filter, platform_a, platform_b)
            if not rule:
                return Response({"error": f"Rule not found for metric '{metric_filter}' on pair {platform_a} <-> {platform_b}"}, status=status.HTTP_404_NOT_FOUND)
            return Response({
                "metric": rule.metric,
                "platform_a": rule.platform_a,
                "platform_b": rule.platform_b,
                "compatibility": rule.compatibility.value,
                "normalization": rule.normalization.value,
                "direction": rule.direction.value,
                "rankable": rule.rankable,
                "required_metrics": rule.required_metrics,
                "minimum_sample": rule.minimum_sample,
                "notes": rule.notes,
                "default_reason_code": rule.default_reason_code.value,
                "reason_labels": get_reason_labels(rule.default_reason_code),
            })

        rules_data = []
        for rule in FB_IG_RULES.values():
            oriented_rule = get_metric_comparison_rule(rule.metric, platform_a, platform_b) or rule
            rules_data.append({
                "metric": oriented_rule.metric,
                "platform_a": oriented_rule.platform_a,
                "platform_b": oriented_rule.platform_b,
                "compatibility": oriented_rule.compatibility.value,
                "normalization": oriented_rule.normalization.value,
                "direction": oriented_rule.direction.value,
                "rankable": oriented_rule.rankable,
                "required_metrics": oriented_rule.required_metrics,
                "minimum_sample": oriented_rule.minimum_sample,
                "notes": oriented_rule.notes,
                "default_reason_code": oriented_rule.default_reason_code.value,
                "reason_labels": get_reason_labels(oriented_rule.default_reason_code),
            })

        return Response({
            "platform_a": platform_a,
            "platform_b": platform_b,
            "rules_count": len(rules_data),
            "rules": rules_data,
        })


class MultichannelCompareView(AnalyticsBaseView):
    """
    GET /api/analytics/multichannel/compare/
    Deterministic, read-only cross-platform metric comparison.
    Enforces strict tenant isolation: requires authenticated user possessing access to client.
    """
    def get(self, request):
        client = self.validate_client(request, request.query_params.get("client_id"))
        if not client:
            return Response({"error": "Client not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        metric = request.query_params.get("metric")
        if not metric:
            return Response({"error": "metric query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        platform_a = request.query_params.get("platform_a", "facebook")
        platform_b = request.query_params.get("platform_b", "instagram")
        period = request.query_params.get("period", "day")
        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))

        from .multichannel import compare_metric_across_platforms

        result = compare_metric_across_platforms(
            client=client,
            metric=metric,
            platform_a=platform_a,
            platform_b=platform_b,
            start_date=start_date,
            end_date=end_date,
            period=period,
        )

        return Response(result.to_dict())
