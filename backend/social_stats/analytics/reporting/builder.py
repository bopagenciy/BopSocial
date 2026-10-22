"""
Deterministic Executive Report Builder for Bop Social (BS-4G).
Assembles structured report payloads from normalized analytics rollups, snapshots,
and persisted BusinessSignal records without generative AI or fabricated metrics.
"""
import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Sum, Max, Min, Avg, Q
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    BusinessSignal,
    UnifiedPost,
    PlatformPublishLog,
    PostMetric,
)
from ..capabilities import get_provider_capability, SupportLevel
from ..freshness import get_client_platform_freshness
from ..registry import AggregationBehavior, CANONICAL_METRICS
from ..intelligence.baselines import calculate_deltas, calculate_median
from .templates import BRANDING, get_report_strings, format_delta_display

logger = logging.getLogger(__name__)

TEMPLATE_VERSION = "bs4g-v1"


def compute_source_hash(
    client_id: int,
    period_start: date,
    period_end: date,
    platform: Optional[str],
    language: str,
    template_version: str,
    rollup_count: int,
    signal_identities: List[str],
) -> str:
    """
    Computes a deterministic SHA-256 digest over canonicalized source factors.
    Guarantees reproducibility and auditability.
    """
    normalized_signals = ",".join(sorted(signal_identities))
    raw_key = (
        f"{client_id}|{period_start.isoformat()}|{period_end.isoformat()}|"
        f"{platform or 'all'}|{language}|{template_version}|{rollup_count}|"
        f"{normalized_signals}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def build_executive_report_data(
    client_id: int,
    date_from: date,
    date_to: date,
    platform: Optional[str] = None,
    language: str = "es",
    report_type: str = "EXECUTIVE",
) -> Dict[str, Any]:
    """
    Builds a canonical, deterministic JSON-serializable executive report payload.
    No HTML/PDF code here; purely structured business intelligence.
    """
    client = Client.objects.filter(id=client_id, is_active=True).first()
    if not client:
        raise ValueError(f"Active client with ID {client_id} does not exist.")

    strings = get_report_strings(language)
    clean_platform = (platform or "").lower()
    if clean_platform in ("", "all", "none"):
        platform_filter = None
    else:
        platform_filter = clean_platform

    start_date = date_from
    end_date = date_to
    window_days = max(1, (end_date - start_date).days + 1)

    # Preceding comparable baseline window of equal duration
    baseline_end = start_date - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=window_days - 1)

    # 1. Credentials, Capabilities, and Data Health
    creds_qs = PlatformCredential.objects.defer("access_token", "refresh_token").filter(client=client, is_active=True)
    if platform_filter:
        creds_qs = creds_qs.filter(platform=platform_filter)
    creds = list(creds_qs)

    capabilities_by_plat = {}
    freshness_by_plat = {}
    for c in creds:
        cap = get_provider_capability(c.platform, c)
        capabilities_by_plat[c.platform] = cap
        freshness_by_plat[c.platform] = get_client_platform_freshness(client.id, c.platform)

    # 2. Source Rollups & Counts
    rollups_qs = SocialMetricRollup.objects.filter(
        client=client,
        period_start__gte=start_date,
        period_start__lte=end_date,
    )
    if platform_filter:
        rollups_qs = rollups_qs.filter(platform=platform_filter)
    source_rollup_count = rollups_qs.count()

    baseline_rollups_qs = SocialMetricRollup.objects.filter(
        client=client,
        period_start__gte=baseline_start,
        period_start__lte=baseline_end,
    )
    if platform_filter:
        baseline_rollups_qs = baseline_rollups_qs.filter(platform=platform_filter)

    # 3. Source Persisted Business Signals
    signals_qs = BusinessSignal.objects.filter(
        client=client,
        period_end__gte=start_date,
        period_start__lte=end_date,
    )
    if platform_filter:
        signals_qs = signals_qs.filter(platform=platform_filter)
    persisted_signals = list(signals_qs.order_by("-period_end", "id"))
    source_signal_count = len(persisted_signals)
    signal_identities = [s.signal_identity for s in persisted_signals]

    # Deterministic source hash
    source_hash = compute_source_hash(
        client_id=client.id,
        period_start=start_date,
        period_end=end_date,
        platform=platform_filter,
        language=language,
        template_version=TEMPLATE_VERSION,
        rollup_count=source_rollup_count,
        signal_identities=signal_identities,
    )

    # 4. KPI Overview Construction (With Strict Metric Semantics)
    CANDIDATE_KPIS = [
        "FOLLOWERS_TOTAL",
        "FOLLOWERS_NET_CHANGE",
        "ENGAGEMENT_TOTAL",
        "REACTIONS",
        "COMMENTS",
        "SHARES",
        "VIDEO_VIEWS",
        "PROFILE_VIEWS",
        "REACH",
    ]

    kpis_list = []
    # Identify which metrics are unsupported/partially supported per active platform
    for m_key in CANDIDATE_KPIS:
        # Check platform capability
        is_available = True
        unavailable_reason = None
        comparability_warning = None

        if platform_filter == "instagram":
            if m_key in ["SHARES", "SAVES", "REACH", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"]:
                is_available = False
                unavailable_reason = "No soportado con los permisos actuales de Instagram" if language == "es" else "Unsupported with current Instagram permissions"
        elif not platform_filter:
            # Multi-platform view: if all connected platforms lack it
            all_lacking = True
            for p_name, cap in capabilities_by_plat.items():
                if p_name == "instagram" and m_key in ["SHARES", "SAVES", "REACH", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"]:
                    continue
                all_lacking = False
            if all_lacking and "instagram" in capabilities_by_plat and len(capabilities_by_plat) == 1:
                is_available = False
                unavailable_reason = "No soportado con los permisos actuales de Instagram" if language == "es" else "Unsupported with current Instagram permissions"

        label = strings.get(f"kpi_{m_key.lower()}", m_key)
        is_gauge = (m_key == "FOLLOWERS_TOTAL")
        is_non_aggregatable = (m_key == "REACH")

        curr_val = None
        base_val = None
        abs_delta = None
        rel_delta = None

        if is_available:
            if is_gauge:
                # Latest point-in-time value for current window
                latest_curr = rollups_qs.filter(normalized_metric=m_key).order_by("-period_start").first()
                if latest_curr:
                    curr_val = latest_curr.metric_value
                # Latest point-in-time value for baseline window
                latest_base = baseline_rollups_qs.filter(normalized_metric=m_key).order_by("-period_start").first()
                if latest_base:
                    base_val = latest_base.metric_value
            elif is_non_aggregatable:
                # Average daily reach (never sum across days!)
                avg_curr = rollups_qs.filter(normalized_metric=m_key).aggregate(val=Avg("metric_value"))["val"]
                if avg_curr is not None:
                    curr_val = Decimal(str(avg_curr)).quantize(Decimal("0.0001"))
                avg_base = baseline_rollups_qs.filter(normalized_metric=m_key).aggregate(val=Avg("metric_value"))["val"]
                if avg_base is not None:
                    base_val = Decimal(str(avg_base)).quantize(Decimal("0.0001"))
                comparability_warning = strings["reach_note"]
            else:
                # Aggregatable metrics: sum rollups
                sum_curr = rollups_qs.filter(normalized_metric=m_key).aggregate(val=Sum("metric_value"))["val"]
                if sum_curr is not None:
                    curr_val = Decimal(str(sum_curr)).quantize(Decimal("0.0001"))
                sum_base = baseline_rollups_qs.filter(normalized_metric=m_key).aggregate(val=Sum("metric_value"))["val"]
                if sum_base is not None:
                    base_val = Decimal(str(sum_base)).quantize(Decimal("0.0001"))

            if curr_val is not None and base_val is not None:
                abs_d, rel_d = calculate_deltas(curr_val, base_val)
                abs_delta = abs_d
                rel_delta = rel_d
            elif curr_val is not None:
                abs_delta = None
                rel_delta = None

        kpi_entry = {
            "metric_key": m_key,
            "label": label,
            "is_available": is_available,
            "is_gauge": is_gauge,
            "is_non_aggregatable": is_non_aggregatable,
            "current_value": float(curr_val) if curr_val is not None else None,
            "baseline_value": float(base_val) if base_val is not None else None,
            "absolute_delta": float(abs_delta) if abs_delta is not None else None,
            "relative_delta": float(rel_delta) if rel_delta is not None else None,
            "delta_display": format_delta_display(
                float(abs_delta) if abs_delta is not None else None,
                float(rel_delta) if rel_delta is not None else None,
            ),
            "unavailable_reason": unavailable_reason,
            "comparability_warning": comparability_warning,
        }
        kpis_list.append(kpi_entry)

    # 5. Performance Trends (Daily series for charts)
    trend_metrics = ["REACTIONS", "COMMENTS", "SHARES", "FOLLOWERS_TOTAL"]
    daily_rollups = (
        rollups_qs.filter(normalized_metric__in=trend_metrics)
        .values("period_start", "normalized_metric")
        .annotate(total=Sum("metric_value"))
        .order_by("period_start")
    )
    trends_by_date: Dict[str, Dict[str, Any]] = {}
    for row in daily_rollups:
        d_str = row["period_start"].isoformat()
        if d_str not in trends_by_date:
            trends_by_date[d_str] = {"date": d_str}
        trends_by_date[d_str][row["normalized_metric"]] = float(row["total"])

    trends_series = sorted(trends_by_date.values(), key=lambda x: x["date"])

    # 6. Content Performance (Snapshots in period)
    posts_qs = SocialMetricSnapshot.objects.filter(
        client=client,
        metric_scope__in=["post", "video", "reel"],
        bucket_timestamp__date__range=(start_date, end_date),
    )
    if platform_filter:
        posts_qs = posts_qs.filter(platform=platform_filter)

    post_snapshots = list(posts_qs.order_by("-bucket_timestamp"))
    posts_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for s in post_snapshots:
        pkey = (s.platform, s.object_id)
        if pkey not in posts_map:
            media_type = s.metadata.get("media_type") or s.metadata.get("post_type") or "post"
            posts_map[pkey] = {
                "platform": s.platform,
                "object_id": s.object_id,
                "media_type": str(media_type).lower(),
                "published_at": s.bucket_timestamp.isoformat(),
                "unified_post_id": s.unified_post_id,
                "publish_log_id": s.publish_log_id,
                "reactions": 0,
                "comments": 0,
                "shares": None if (s.platform == "instagram" and capabilities_by_plat.get("instagram", None) and capabilities_by_plat["instagram"].overall_support == SupportLevel.PARTIAL) else 0,
            }
        val = int(s.metric_value)
        if s.normalized_metric == "REACTIONS":
            posts_map[pkey]["reactions"] = val
        elif s.normalized_metric == "COMMENTS":
            posts_map[pkey]["comments"] = val
        elif s.normalized_metric == "SHARES" and posts_map[pkey]["shares"] is not None:
            posts_map[pkey]["shares"] = val

    # Cross-reference UnifiedPosts to identify Bop Social authorship
    obj_ids = [k[1] for k in posts_map.keys()]
    pms = {pm.post_id: pm for pm in PostMetric.objects.filter(client=client, post_id__in=obj_ids)}
    pub_logs = {pl.platform_post_id: pl for pl in PlatformPublishLog.objects.filter(unified_post__client=client, platform_post_id__in=obj_ids)}

    content_list = []
    for pkey, pdata in posts_map.items():
        obj_id = pkey[1]
        pm = pms.get(obj_id)
        pl = pub_logs.get(obj_id)
        is_bop = bool(pdata["unified_post_id"] or pdata["publish_log_id"] or pl or (pm and pm.unified_post_id))
        pdata["is_bop_authored"] = is_bop
        pdata["source_label"] = strings["bop_authored"] if is_bop else strings["organic_external"]
        # Score for ordering (sum of reactions and comments)
        pdata["interaction_sum"] = (pdata["reactions"] or 0) + (pdata["comments"] or 0) + ((pdata["shares"] or 0) if pdata["shares"] is not None else 0)
        content_list.append(pdata)

    content_list.sort(key=lambda x: x["interaction_sum"], reverse=True)
    top_content = content_list[:10]

    # 7. Business Intelligence Signals (Preserve existing persisted rows)
    formatted_signals = []
    for sig in persisted_signals:
        conf_label = strings.get(f"conf_{sig.confidence_level.lower()}", sig.confidence_level)
        sev_label = strings.get(f"sev_{sig.severity.lower()}", sig.severity)
        
        rel_pct = None
        if sig.relative_delta is not None:
            rel_pct = float((sig.relative_delta * 100).quantize(Decimal("0.1")))

        formatted_signals.append({
            "id": sig.id,
            "signal_identity": sig.signal_identity,
            "platform": sig.platform,
            "signal_type": sig.signal_type,
            "metric": sig.metric,
            "direction": sig.direction,
            "confidence_level": sig.confidence_level,
            "confidence_label": conf_label,
            "severity": sig.severity,
            "severity_label": sev_label,
            "is_actionable": sig.is_actionable,
            "observed_value": float(sig.observed_value) if sig.observed_value is not None else None,
            "baseline_value": float(sig.baseline_value) if sig.baseline_value is not None else None,
            "relative_delta_pct": rel_pct,
            "sample_size": sig.sample_size,
            "explanation": sig.explanation_template,
            "evidence": sig.evidence,
        })

    # 8. Platform Breakdown
    platform_breakdown = []
    for p_name in ["facebook", "instagram"]:
        if platform_filter and platform_filter != p_name:
            continue
        cred = next((c for c in creds if c.platform == p_name), None)
        cap = capabilities_by_plat.get(p_name)
        fresh = freshness_by_plat.get(p_name, {})
        
        status_mode = "FULL" if (cap and cap.overall_support == SupportLevel.SUPPORTED) else "PARTIAL"
        mode_label = strings["full_mode"] if status_mode == "FULL" else strings["partial_mode"]
        
        p_rollups = rollups_qs.filter(platform=p_name)
        p_react = p_rollups.filter(normalized_metric="REACTIONS").aggregate(s=Sum("metric_value"))["s"] or 0
        p_comm = p_rollups.filter(normalized_metric="COMMENTS").aggregate(s=Sum("metric_value"))["s"] or 0
        
        avail_m = ["FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"]
        unavail_m = []
        if status_mode == "FULL":
            avail_m.extend(["SHARES", "SAVES", "CLICKS_TOTAL", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL", "REACH"])
        else:
            unavail_m = ["SHARES", "SAVES", "REACH", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"]

        platform_breakdown.append({
            "platform": p_name,
            "connected": cred is not None,
            "status_mode": status_mode,
            "mode_label": mode_label,
            "freshness": fresh.get("freshness_state", "FRESH"),
            "available_metrics": avail_m,
            "unavailable_metrics": unavail_m,
            "reactions_total": int(p_react),
            "comments_total": int(p_comm),
        })

    # 9. Format & Posting Time Optimization States
    # Guarded against small sample size
    winning_formats = {
        "has_sufficient_data": False,
        "message": strings["no_format_winner"],
        "formats": [],
    }
    posting_times = {
        "has_sufficient_data": False,
        "message": strings["no_posting_time"],
        "recommendations": [],
    }

    # 10. Deterministic Executive Summary Bullet Points
    summary_bullets = []
    # Statement 1: Audience & Followers
    fol_kpi = next((k for k in kpis_list if k["metric_key"] == "FOLLOWERS_TOTAL"), None)
    if fol_kpi and fol_kpi["current_value"] is not None:
        if fol_kpi["delta_display"] != "—":
            if language == "es":
                summary_bullets.append(f"La audiencia total se ubica en {int(fol_kpi['current_value']):,} seguidores, reflejando una variación de {fol_kpi['delta_display']} frente al período precedente.")
            else:
                summary_bullets.append(f"Total audience stands at {int(fol_kpi['current_value']):,} followers, reflecting a {fol_kpi['delta_display']} change against the previous period.")
        else:
            if language == "es":
                summary_bullets.append(f"La audiencia total registrada se ubica en {int(fol_kpi['current_value']):,} seguidores.")
            else:
                summary_bullets.append(f"Total recorded audience stands at {int(fol_kpi['current_value']):,} followers.")

    # Statement 2: Content Volume & Activity
    total_posts_analyzed = len(posts_map)
    bop_posts_count = sum(1 for p in posts_map.values() if p.get("is_bop_authored"))
    if total_posts_analyzed > 0:
        if language == "es":
            summary_bullets.append(f"Se analizaron {total_posts_analyzed} publicaciones en el período ({bop_posts_count} originadas desde Bop Social).")
        else:
            summary_bullets.append(f"Analyzed {total_posts_analyzed} posts during the period ({bop_posts_count} published via Bop Social).")
    else:
        if language == "es":
            summary_bullets.append("No se registraron nuevas publicaciones en las plataformas durante el período de reporte.")
        else:
            summary_bullets.append("No new posts were recorded across platforms during the reporting period.")

    # Statement 3: Provider Capabilities
    if any(p["status_mode"] == "PARTIAL" for p in platform_breakdown):
        if language == "es":
            summary_bullets.append("Instagram opera actualmente bajo capacidad analítica PARCIAL. Métricas esenciales (reacciones, comentarios, seguidores) están activas; métricas avanzadas requieren permisos adicionales de Meta.")
        else:
            summary_bullets.append("Instagram is currently operating under PARTIAL capability mode. Core metrics (reactions, comments, followers) are active; advanced metrics require additional Meta permissions.")

    # Statement 4: Business Intelligence Signals
    if source_signal_count > 0:
        if language == "es":
            summary_bullets.append(f"El motor de Inteligencia de Negocio identificó {source_signal_count} señales estratégicas determinísticas durante este período.")
        else:
            summary_bullets.append(f"The Business Intelligence engine identified {source_signal_count} deterministic strategic signals during this period.")

    # Statement 5: Data Sufficiency Note
    if not winning_formats["has_sufficient_data"]:
        summary_bullets.append(strings["no_format_winner"])

    # Build Complete Report Payload
    report_title = strings.get(f"report_title_{report_type.lower()}", strings["report_title_executive"])
    report_data = {
        "metadata": {
            "template_version": TEMPLATE_VERSION,
            "source_hash": source_hash,
            "source_rollup_count": source_rollup_count,
            "source_signal_count": source_signal_count,
            "generated_at": timezone.now().isoformat(),
            "language": language,
            "report_type": report_type,
            "client_id": client.id,
            "branding": BRANDING,
        },
        "cover": {
            "title": report_title,
            "subtitle": strings["cover_subtitle"],
            "client_name": client.company or client.name,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "period_label": f"{start_date.strftime('%d/%m/%Y')} — {end_date.strftime('%d/%m/%Y')}",
            "generation_date": timezone.now().strftime("%d/%m/%Y"),
            "platform_filter": platform_filter or strings["all_platforms"],
            "branding": BRANDING,
        },
        "executive_summary": {
            "title": strings["section_exec_summary"],
            "bullets": summary_bullets,
        },
        "kpi_overview": {
            "title": strings["section_kpis"],
            "kpis": kpis_list,
        },
        "performance_trends": {
            "title": strings["section_trends"],
            "series": trends_series,
        },
        "content_performance": {
            "title": strings["section_content"],
            "total_posts": len(posts_map),
            "top_posts": top_content,
        },
        "platform_breakdown": {
            "title": strings["section_platforms"],
            "platforms": platform_breakdown,
        },
        "business_intelligence_signals": {
            "title": strings["section_signals"],
            "count": len(formatted_signals),
            "signals": formatted_signals,
        },
        "winning_formats": {
            "title": strings["section_winning_formats"],
            **winning_formats,
        },
        "posting_time_insights": {
            "title": strings["section_posting_times"],
            **posting_times,
        },
        "data_health": {
            "title": strings["section_data_health"],
            "overall_status": "HEALTHY",
            "freshness": {p: f.get("freshness_state", "FRESH") for p, f in freshness_by_plat.items()},
            "capabilities": {p: ("PARTIAL" if c.overall_support == SupportLevel.PARTIAL else "FULL") for p, c in capabilities_by_plat.items()},
        },
        "methodology": {
            "title": strings["section_methodology"],
            "points": strings["methodology_points"],
        },
    }

    return report_data
