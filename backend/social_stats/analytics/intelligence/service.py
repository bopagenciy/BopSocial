"""
Deterministic Business Intelligence Service for Bop Social.
Extracts normalized analytics data, applies statistical cohorts and baselines,
and outputs explainable machine-readable Business Signals without generative AI.
"""
import hashlib
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import zoneinfo

from django.db.models import Max, Q, Sum
from django.utils import timezone

from social_stats.models import (
    BusinessSignal,
    Client,
    PlatformCredential,
    PlatformPublishLog,
    PostMetric,
    SocialMetricRollup,
    SocialMetricSnapshot,
    UnifiedPost,
)
from ..capabilities import SupportLevel, get_provider_capability
from ..freshness import get_client_platform_freshness
from ..registry import AggregationBehavior, CANONICAL_METRICS
from ..derived import can_derive_metric, derive_canonical_engagement_total
from .baselines import (
    calculate_deltas,
    calculate_mad,
    calculate_mean,
    calculate_median,
    detect_anomalies,
)
from .rules import (
    SAMPLE_THRESHOLDS,
    SignalType,
    PerformanceTier,
    calculate_confidence,
    classify_performance_tier,
    determine_direction,
    determine_severity,
    is_signal_actionable,
)
from .templates import build_explanation

logger = logging.getLogger(__name__)


def compute_signal_identity(
    client_id: int,
    platform: str,
    signal_type: str,
    metric: str,
    scope: str,
    object_id: str,
    period_start: date,
    period_end: date,
    cohort_hash: str,
) -> str:
    """
    Computes a deterministic SHA256 digest ensuring zero duplicate signals.
    """
    key_str = f"{client_id}:{platform}:{signal_type}:{metric}:{scope}:{object_id}:{period_start.isoformat()}:{period_end.isoformat()}:{cohort_hash}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def get_client_timezone(client: Client) -> zoneinfo.ZoneInfo:
    tz_str = getattr(client, "timezone", None) or "UTC"
    try:
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        return zoneinfo.ZoneInfo("UTC")


def get_hour_bucket(hour: int) -> str:
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "afternoon"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "late_night"


def generate_business_signals(
    client_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
    metric: Optional[str] = None,
    persist: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates deterministic Business Signals for a client across the specified window.
    If persist=True, saves/updates signals in BusinessSignal model idempotently.
    """
    client = Client.objects.filter(id=client_id, is_active=True).first()
    if not client:
        return []

    today = timezone.now().date()
    end_date = date_to or today
    start_date = date_from or (end_date - timedelta(days=30))
    window_days = (end_date - start_date).days or 30

    # Historical baseline window (preceding period of same length)
    baseline_start = start_date - timedelta(days=window_days)
    baseline_end = start_date - timedelta(days=1)

    # 1. Inspect credentials, capability modes, and freshness
    creds_qs = PlatformCredential.objects.filter(client=client, is_active=True)
    if platform and platform != "all":
        creds_qs = creds_qs.filter(platform=platform)

    creds = list(creds_qs)
    client_tz = get_client_timezone(client)

    capabilities_by_plat = {}
    freshness_by_plat = {}
    for c in creds:
        cap = get_provider_capability(c.platform, c)
        capabilities_by_plat[c.platform] = cap
        freshness_by_plat[c.platform] = get_client_platform_freshness(client.id, c.platform)

    signals: List[Dict[str, Any]] = []

    # 2. Data Health & Provider Signals
    for p_name, cap in capabilities_by_plat.items():
        fresh = freshness_by_plat.get(p_name, {})
        is_stale = fresh.get("is_stale", False)
        hours_stale = fresh.get("hours_since_last_sync", 0)

        if cap.overall_support == SupportLevel.PARTIAL:
            sig = _build_signal_dict(
                client=client,
                platform=p_name,
                signal_type=SignalType.PROVIDER_PARTIAL,
                metric="",
                scope="account",
                object_id="",
                unified_post=None,
                period_start=start_date,
                period_end=end_date,
                observed_value=None,
                baseline_value=None,
                absolute_delta=None,
                relative_delta=None,
                sample_size=0,
                confidence_level="HIGH",
                direction="NEUTRAL",
                severity="INFO",
                is_actionable=False,
                evidence={
                    "platform": p_name,
                    "support_level": "PARTIAL",
                    "available_metrics": ["FOLLOWERS_TOTAL", "REACTIONS", "COMMENTS"],
                    "unavailable_metrics": ["REACH", "SAVES", "SHARES", "VIDEO_VIEWS", "ENGAGEMENT_TOTAL"],
                    "reason": "Requires instagram_manage_insights Meta permission",
                },
                context={"platform": p_name},
                cohort_hash="provider_cap",
            )
            signals.append(sig)

            # Explicit unavailable signal for ENGAGEMENT_TOTAL if requested or evaluating partial capability
            if metric and metric.upper() == "ENGAGEMENT_TOTAL":
                unavail_sig = _build_signal_dict(
                    client=client,
                    platform=p_name,
                    signal_type=SignalType.METRIC_UNAVAILABLE,
                    metric="ENGAGEMENT_TOTAL",
                    scope="account",
                    object_id="",
                    unified_post=None,
                    period_start=start_date,
                    period_end=end_date,
                    observed_value=None,
                    baseline_value=None,
                    absolute_delta=None,
                    relative_delta=None,
                    sample_size=0,
                    confidence_level="NONE",
                    direction="NEUTRAL",
                    severity="INFO",
                    is_actionable=False,
                    evidence={
                        "platform": p_name,
                        "metric": "ENGAGEMENT_TOTAL",
                        "is_available": False,
                        "reason": "missing_required_components",
                        "missing_components": ["SHARES"],
                        "permission_guidance": "Not available with current Instagram permissions",
                    },
                    context={"platform": p_name, "metric": "Total Engagement"},
                    cohort_hash=f"unavailable:{p_name}:ENGAGEMENT_TOTAL",
                )
                signals.append(unavail_sig)

        if is_stale:
            sig = _build_signal_dict(
                client=client,
                platform=p_name,
                signal_type=SignalType.DATA_STALE,
                metric="",
                scope="account",
                object_id="",
                unified_post=None,
                period_start=start_date,
                period_end=end_date,
                observed_value=Decimal(str(hours_stale)) if hours_stale else None,
                baseline_value=Decimal("24.0000"),
                absolute_delta=Decimal(str(hours_stale - 24)) if hours_stale else None,
                relative_delta=None,
                sample_size=1,
                confidence_level="HIGH",
                direction="DOWN",
                severity="WARNING",
                is_actionable=True,
                evidence={
                    "platform": p_name,
                    "hours_stale": hours_stale,
                    "threshold_hours": 24,
                    "freshness_state": fresh.get("freshness_state"),
                },
                context={"platform": p_name, "hours_stale": hours_stale},
                cohort_hash="data_freshness",
            )
            signals.append(sig)

    # 3. Content Performance Intelligence (Posts)
    # Query post-level snapshots
    posts_qs = SocialMetricSnapshot.objects.filter(
        client=client,
        metric_scope__in=["post", "video", "reel"],
        bucket_timestamp__date__range=(start_date, end_date),
    )
    if platform and platform != "all":
        posts_qs = posts_qs.filter(platform=platform)

    post_snapshots = list(posts_qs.order_by("-bucket_timestamp"))

    # Group unique posts by (platform, object_id)
    posts_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for s in post_snapshots:
        pkey = (s.platform, s.object_id)
        if pkey not in posts_by_key:
            media_type = s.metadata.get("media_type") or s.metadata.get("post_type") or "post"
            posts_by_key[pkey] = {
                "platform": s.platform,
                "object_id": s.object_id,
                "media_type": media_type.lower(),
                "bucket_timestamp": s.bucket_timestamp,
                "unified_post_id": s.unified_post_id,
                "publish_log_id": s.publish_log_id,
                "metrics": {},
                "snapshot_ids": [],
            }
        posts_by_key[pkey]["metrics"][s.normalized_metric] = s.metric_value
        posts_by_key[pkey]["snapshot_ids"].append(s.id)

    # Preload UnifiedPosts and PlatformPublishLogs
    obj_ids = [k[1] for k in posts_by_key.keys()]
    pms = {pm.post_id: pm for pm in PostMetric.objects.filter(client=client, post_id__in=obj_ids)}
    pub_logs = {pl.platform_post_id: pl for pl in PlatformPublishLog.objects.filter(unified_post__client=client, platform_post_id__in=obj_ids)}

    for pkey, pdata in posts_by_key.items():
        obj_id = pkey[1]
        pm = pms.get(obj_id)
        pl = pub_logs.get(obj_id)
        is_bop = bool(pdata["unified_post_id"] or pdata["publish_log_id"] or pl or (pm and pm.unified_post_id))
        unified_id = pdata["unified_post_id"] or (pl.unified_post_id if pl else None) or (pm and pm.unified_post_id)
        pdata["is_bop_authored"] = is_bop
        pdata["unified_post_id"] = unified_id

        # Derive canonical ENGAGEMENT_TOTAL only if all required components exist and are available
        if "ENGAGEMENT_TOTAL" not in pdata["metrics"]:
            plat_cap = capabilities_by_plat.get(pdata["platform"])
            cap_mode = plat_cap.overall_support if plat_cap else None
            can_der, _, _ = can_derive_metric(
                platform=pdata["platform"],
                capability_mode=cap_mode,
                metric="ENGAGEMENT_TOTAL",
                available_source_metrics=pdata["metrics"],
            )
            if can_der:
                tot = derive_canonical_engagement_total(
                    source_metrics=pdata["metrics"],
                    platform=pdata["platform"],
                    capability_mode=cap_mode,
                )
                if tot is not None:
                    pdata["metrics"]["ENGAGEMENT_TOTAL"] = tot

    # Group posts into cohorts by (platform, format)
    cohorts: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for pdata in posts_by_key.values():
        ckey = (pdata["platform"], pdata["media_type"])
        cohorts.setdefault(ckey, []).append(pdata)

    # For each cohort, compute baseline and outperforming/underperforming posts
    for (plat, fmt), cohort_posts in cohorts.items():
        cap = capabilities_by_plat.get(plat)
        is_partial = cap.overall_support == SupportLevel.PARTIAL if cap else False
        fresh = freshness_by_plat.get(plat, {})
        is_stale = fresh.get("is_stale", False)

        # Metrics to analyze: REACTIONS, COMMENTS (and ENGAGEMENT_TOTAL only if fully supported and all components exist)
        candidate_metrics = ["REACTIONS", "COMMENTS"]
        can_cohort_eng, _, _ = can_derive_metric(
            platform=plat,
            capability_mode=cap.overall_support if cap else None,
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics=set().union(*(p["metrics"].keys() for p in cohort_posts)) if cohort_posts else set(),
        )
        if can_cohort_eng and not is_partial and any("ENGAGEMENT_TOTAL" in p["metrics"] for p in cohort_posts):
            candidate_metrics.append("ENGAGEMENT_TOTAL")

        # If a specific metric was requested, filter candidate metrics
        if metric:
            target_metric = metric.upper()
            if target_metric in candidate_metrics:
                cohort_eval_metrics = [target_metric]
            else:
                cohort_eval_metrics = []
        else:
            cohort_eval_metrics = candidate_metrics

        for m_name in cohort_eval_metrics:
            values = [p["metrics"].get(m_name, Decimal("0")) for p in cohort_posts if m_name in p["metrics"]]
            sample_size = len(values)
            cohort_hash = f"cohort:{plat}:{fmt}:{m_name}"

            if sample_size < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
                # Small sample protection
                sig = _build_signal_dict(
                    client=client,
                    platform=plat,
                    signal_type=SignalType.INSUFFICIENT_SAMPLE,
                    metric=m_name,
                    scope="post",
                    object_id="",
                    unified_post=None,
                    period_start=start_date,
                    period_end=end_date,
                    observed_value=Decimal(str(sample_size)),
                    baseline_value=Decimal(str(SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"])),
                    absolute_delta=None,
                    relative_delta=None,
                    sample_size=sample_size,
                    confidence_level="NONE",
                    direction="NEUTRAL",
                    severity="INFO",
                    is_actionable=False,
                    evidence={
                        "cohort": {"platform": plat, "format": fmt, "metric": m_name},
                        "sample_size": sample_size,
                        "min_required": SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"],
                    },
                    context={
                        "platform": plat,
                        "format": fmt,
                        "metric": m_name,
                        "sample_size": sample_size,
                        "min_required": SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"],
                    },
                    cohort_hash=cohort_hash,
                )
                signals.append(sig)
                continue

            cohort_median = calculate_median(values)
            if cohort_median is None:
                continue

            confidence = calculate_confidence(sample_size, is_stale=is_stale, is_partial=is_partial)

            # Check individual posts vs cohort median
            for p in cohort_posts:
                if m_name not in p["metrics"]:
                    continue
                obs_val = p["metrics"][m_name]
                abs_delta, rel_delta = calculate_deltas(obs_val, cohort_median)
                tier = classify_performance_tier(rel_delta)

                if tier in (PerformanceTier.STRONG_OUTPERFORMANCE, PerformanceTier.OUTPERFORMANCE):
                    sig_type = SignalType.CONTENT_OUTPERFORMING
                elif tier in (PerformanceTier.STRONG_UNDERPERFORMANCE, PerformanceTier.UNDERPERFORMANCE):
                    sig_type = SignalType.CONTENT_UNDERPERFORMING
                else:
                    continue  # Normal range posts do not produce outlier alert signals

                direction = determine_direction(rel_delta)
                severity = determine_severity(sig_type, tier, direction, is_stale=is_stale)
                actionable = is_signal_actionable(sig_type)

                evidence = {
                    "observed_value": float(obs_val),
                    "baseline_value": float(cohort_median),
                    "baseline_method": "median",
                    "absolute_delta": float(abs_delta),
                    "relative_delta": float(rel_delta) if rel_delta is not None else None,
                    "relative_delta_pct": float((rel_delta * 100).quantize(Decimal("0.1"))) if rel_delta is not None else None,
                    "sample_size": sample_size,
                    "cohort": {
                        "platform": plat,
                        "format": fmt,
                        "metric": m_name,
                        "window_days": window_days,
                    },
                    "is_bop_authored": p["is_bop_authored"],
                    "source_label": "Published by Bop Social" if p["is_bop_authored"] else "Organic / External",
                    "source_snapshot_ids": p["snapshot_ids"],
                    "freshness": fresh.get("freshness_state", "FRESH"),
                }

                up_obj = None
                if p["unified_post_id"]:
                    up_obj = UnifiedPost.objects.filter(id=p["unified_post_id"]).first()

                sig = _build_signal_dict(
                    client=client,
                    platform=plat,
                    signal_type=sig_type,
                    metric=m_name,
                    scope="post",
                    object_id=p["object_id"],
                    unified_post=up_obj,
                    period_start=start_date,
                    period_end=end_date,
                    observed_value=obs_val,
                    baseline_value=cohort_median,
                    absolute_delta=abs_delta,
                    relative_delta=rel_delta,
                    sample_size=sample_size,
                    confidence_level=confidence,
                    direction=direction,
                    severity=severity,
                    is_actionable=actionable,
                    evidence=evidence,
                    context={
                        "platform": plat,
                        "format": fmt,
                        "metric": m_name,
                        "observed_value": obs_val,
                        "baseline_value": cohort_median,
                        "sample_size": sample_size,
                        "relative_delta": rel_delta,
                        "direction": direction,
                        "window_days": window_days,
                    },
                    cohort_hash=cohort_hash,
                )
                signals.append(sig)

    # 4. Format Intelligence (Format vs Platform Overall)
    for plat in set(k[0] for k in cohorts.keys()):
        plat_posts = [p for (p_plat, _), cposts in cohorts.items() if p_plat == plat for p in cposts]
        if len(plat_posts) < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
            continue

        cap = capabilities_by_plat.get(plat)
        is_partial = cap.overall_support == SupportLevel.PARTIAL if cap else False
        fresh = freshness_by_plat.get(plat, {})
        is_stale = fresh.get("is_stale", False)

        metric = "REACTIONS"
        overall_values = [p["metrics"].get(metric, Decimal("0")) for p in plat_posts if metric in p["metrics"]]
        if len(overall_values) < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
            continue

        overall_median = calculate_median(overall_values)
        if overall_median is None:
            continue

        # For each format in this platform
        plat_formats = {fmt for (p_plat, fmt) in cohorts.keys() if p_plat == plat}
        for fmt in plat_formats:
            fmt_posts = cohorts.get((plat, fmt), [])
            fmt_vals = [p["metrics"].get(metric, Decimal("0")) for p in fmt_posts if metric in p["metrics"]]
            fmt_n = len(fmt_vals)
            if fmt_n < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
                continue

            fmt_median = calculate_median(fmt_vals)
            if fmt_median is None:
                continue

            abs_delta, rel_delta = calculate_deltas(fmt_median, overall_median)
            tier = classify_performance_tier(rel_delta)

            if tier in (PerformanceTier.STRONG_OUTPERFORMANCE, PerformanceTier.OUTPERFORMANCE):
                sig_type = SignalType.FORMAT_OUTPERFORMING
            elif tier in (PerformanceTier.STRONG_UNDERPERFORMANCE, PerformanceTier.UNDERPERFORMANCE):
                sig_type = SignalType.FORMAT_UNDERPERFORMING
            else:
                continue

            confidence = calculate_confidence(fmt_n, is_stale=is_stale, is_partial=is_partial)
            direction = determine_direction(rel_delta)
            severity = determine_severity(sig_type, tier, direction, is_stale=is_stale)

            sig = _build_signal_dict(
                client=client,
                platform=plat,
                signal_type=sig_type,
                metric=metric,
                scope="format",
                object_id=fmt,
                unified_post=None,
                period_start=start_date,
                period_end=end_date,
                observed_value=fmt_median,
                baseline_value=overall_median,
                absolute_delta=abs_delta,
                relative_delta=rel_delta,
                sample_size=fmt_n,
                confidence_level=confidence,
                direction=direction,
                severity=severity,
                is_actionable=True,
                evidence={
                    "format": fmt,
                    "platform": plat,
                    "metric": metric,
                    "format_median": float(fmt_median),
                    "overall_comparable_median": float(overall_median),
                    "relative_delta_pct": float((rel_delta * 100).quantize(Decimal("0.1"))) if rel_delta else None,
                    "sample_size": fmt_n,
                    "overall_sample_size": len(overall_values),
                },
                context={
                    "format": fmt,
                    "platform": plat,
                    "metric": metric,
                    "observed_value": fmt_median,
                    "baseline_value": overall_median,
                    "sample_size": fmt_n,
                    "relative_delta": rel_delta,
                    "direction": direction,
                },
                cohort_hash=f"format:{plat}:{fmt}:{metric}",
            )
            signals.append(sig)

    # 5. Posting Time Intelligence (Client Timezone Aware)
    for plat in set(k[0] for k in cohorts.keys()):
        plat_posts = [p for (p_plat, _), cposts in cohorts.items() if p_plat == plat for p in cposts]
        if len(plat_posts) < 5:
            continue

        cap = capabilities_by_plat.get(plat)
        is_partial = cap.overall_support == SupportLevel.PARTIAL if cap else False
        fresh = freshness_by_plat.get(plat, {})
        is_stale = fresh.get("is_stale", False)

        metric = "REACTIONS"
        overall_values = [p["metrics"].get(metric, Decimal("0")) for p in plat_posts if metric in p["metrics"]]
        overall_median = calculate_median(overall_values)
        if overall_median is None:
            continue

        # Group posts by hour bucket in client's timezone
        bucket_posts: Dict[str, List[Decimal]] = {
            "morning": [],
            "afternoon": [],
            "evening": [],
            "late_night": [],
        }

        for p in plat_posts:
            if metric not in p["metrics"]:
                continue
            dt_utc = p["bucket_timestamp"]
            dt_local = dt_utc.astimezone(client_tz)
            bucket = get_hour_bucket(dt_local.hour)
            bucket_posts[bucket].append(p["metrics"][metric])

        # Find best bucket satisfying sample threshold
        for bucket, b_vals in bucket_posts.items():
            b_n = len(b_vals)
            if b_n < SAMPLE_THRESHOLDS["MINIMUM_FOR_SIGNAL"]:
                continue

            b_median = calculate_median(b_vals)
            if b_median is None:
                continue

            abs_delta, rel_delta = calculate_deltas(b_median, overall_median)
            tier = classify_performance_tier(rel_delta)

            if tier in (PerformanceTier.STRONG_OUTPERFORMANCE, PerformanceTier.OUTPERFORMANCE):
                sig_type = SignalType.POSTING_TIME_OUTPERFORMING
            elif tier in (PerformanceTier.STRONG_UNDERPERFORMANCE, PerformanceTier.UNDERPERFORMANCE):
                sig_type = SignalType.POSTING_TIME_UNDERPERFORMING
            else:
                continue

            confidence = calculate_confidence(b_n, is_stale=is_stale, is_partial=is_partial)
            direction = determine_direction(rel_delta)
            severity = determine_severity(sig_type, tier, direction, is_stale=is_stale)

            sig = _build_signal_dict(
                client=client,
                platform=plat,
                signal_type=sig_type,
                metric=metric,
                scope="time",
                object_id=bucket,
                unified_post=None,
                period_start=start_date,
                period_end=end_date,
                observed_value=b_median,
                baseline_value=overall_median,
                absolute_delta=abs_delta,
                relative_delta=rel_delta,
                sample_size=b_n,
                confidence_level=confidence,
                direction=direction,
                severity=severity,
                is_actionable=True,
                evidence={
                    "bucket": bucket,
                    "timezone": client_tz.key,
                    "platform": plat,
                    "metric": metric,
                    "bucket_median": float(b_median),
                    "overall_median": float(overall_median),
                    "relative_delta_pct": float((rel_delta * 100).quantize(Decimal("0.1"))) if rel_delta else None,
                    "sample_size": b_n,
                    "total_posts": len(plat_posts),
                },
                context={
                    "bucket": bucket,
                    "timezone": client_tz.key,
                    "platform": plat,
                    "metric": metric,
                    "observed_value": b_median,
                    "baseline_value": overall_median,
                    "sample_size": b_n,
                    "relative_delta": rel_delta,
                    "direction": direction,
                },
                cohort_hash=f"time:{plat}:{bucket}:{metric}",
            )
            signals.append(sig)

    # 6. Engagement Trends & Momentum (Rollup Based)
    # Load daily rollups for current and baseline windows
    rollups_qs = SocialMetricRollup.objects.filter(
        client=client,
        period="day",
        period_start__range=(baseline_start, end_date),
    )
    if platform and platform != "all":
        rollups_qs = rollups_qs.filter(platform=platform)

    daily_rollups = list(rollups_qs)

    for plat_name in {r.platform for r in daily_rollups}:
        cap = capabilities_by_plat.get(plat_name)
        is_partial = cap.overall_support == SupportLevel.PARTIAL if cap else False
        fresh = freshness_by_plat.get(plat_name, {})
        is_stale = fresh.get("is_stale", False)

        curr_rollups = [r for r in daily_rollups if r.platform == plat_name and start_date <= r.period_start <= end_date]
        prev_rollups = [r for r in daily_rollups if r.platform == plat_name and baseline_start <= r.period_start <= baseline_end]

        # Analyze REACTIONS trend
        curr_reactions = [r.metric_value for r in curr_rollups if r.normalized_metric == "REACTIONS"]
        prev_reactions = [r.metric_value for r in prev_rollups if r.normalized_metric == "REACTIONS"]

        if len(curr_reactions) >= 3 and len(prev_reactions) >= 3:
            curr_med = calculate_median(curr_reactions)
            prev_med = calculate_median(prev_reactions)
            if curr_med is not None and prev_med is not None and prev_med > 0:
                abs_delta, rel_delta = calculate_deltas(curr_med, prev_med)
                direction = determine_direction(rel_delta)
                if direction in ("UP", "DOWN"):
                    sig_type = SignalType.ENGAGEMENT_TREND_UP if direction == "UP" else SignalType.ENGAGEMENT_TREND_DOWN
                    tier = classify_performance_tier(rel_delta)
                    conf = calculate_confidence(len(curr_reactions), is_stale=is_stale, is_partial=is_partial)
                    sev = determine_severity(sig_type, tier, direction, is_stale=is_stale)

                    sig = _build_signal_dict(
                        client=client,
                        platform=plat_name,
                        signal_type=sig_type,
                        metric="REACTIONS",
                        scope="account",
                        object_id="",
                        unified_post=None,
                        period_start=start_date,
                        period_end=end_date,
                        observed_value=curr_med,
                        baseline_value=prev_med,
                        absolute_delta=abs_delta,
                        relative_delta=rel_delta,
                        sample_size=len(curr_reactions),
                        confidence_level=conf,
                        direction=direction,
                        severity=sev,
                        is_actionable=False,
                        evidence={
                            "metric": "REACTIONS",
                            "platform": plat_name,
                            "current_median": float(curr_med),
                            "baseline_median": float(prev_med),
                            "current_sample_count": len(curr_reactions),
                            "baseline_sample_count": len(prev_reactions),
                            "window_days": window_days,
                        },
                        context={
                            "metric": "Reactions",
                            "platform": plat_name,
                            "observed_value": curr_med,
                            "baseline_value": prev_med,
                            "sample_size": len(curr_reactions),
                            "relative_delta": rel_delta,
                            "direction": direction,
                            "window_days": window_days,
                        },
                        cohort_hash=f"trend:{plat_name}:reactions",
                    )
                    signals.append(sig)

        # Momentum: Recent 7 days vs preceding 7 days
        recent_7_start = end_date - timedelta(days=6)
        prev_7_start = end_date - timedelta(days=13)
        prev_7_end = end_date - timedelta(days=7)

        r7_vals = [r.metric_value for r in curr_rollups if r.normalized_metric == "REACTIONS" and recent_7_start <= r.period_start <= end_date]
        p7_vals = [r.metric_value for r in daily_rollups if r.platform == plat_name and r.normalized_metric == "REACTIONS" and prev_7_start <= r.period_start <= prev_7_end]

        if len(r7_vals) >= 3 and len(p7_vals) >= 3:
            r7_med = calculate_median(r7_vals)
            p7_med = calculate_median(p7_vals)
            if r7_med is not None and p7_med is not None and p7_med > 0:
                abs_delta, rel_delta = calculate_deltas(r7_med, p7_med)
                tier = classify_performance_tier(rel_delta)
                if tier in (PerformanceTier.STRONG_OUTPERFORMANCE, PerformanceTier.OUTPERFORMANCE):
                    sig_type = SignalType.MOMENTUM_UP
                elif tier in (PerformanceTier.STRONG_UNDERPERFORMANCE, PerformanceTier.UNDERPERFORMANCE):
                    sig_type = SignalType.MOMENTUM_DOWN
                else:
                    sig_type = None

                if sig_type:
                    direction = determine_direction(rel_delta)
                    conf = calculate_confidence(len(r7_vals), is_stale=is_stale, is_partial=is_partial)
                    sev = determine_severity(sig_type, tier, direction, is_stale=is_stale)

                    sig = _build_signal_dict(
                        client=client,
                        platform=plat_name,
                        signal_type=sig_type,
                        metric="REACTIONS",
                        scope="account",
                        object_id="",
                        unified_post=None,
                        period_start=recent_7_start,
                        period_end=end_date,
                        observed_value=r7_med,
                        baseline_value=p7_med,
                        absolute_delta=abs_delta,
                        relative_delta=rel_delta,
                        sample_size=len(r7_vals),
                        confidence_level=conf,
                        direction=direction,
                        severity=sev,
                        is_actionable=True,
                        evidence={
                            "recent_7d_median": float(r7_med),
                            "previous_7d_median": float(p7_med),
                            "recent_sample_count": len(r7_vals),
                            "previous_sample_count": len(p7_vals),
                        },
                        context={
                            "metric": "Reactions",
                            "platform": plat_name,
                            "observed_value": r7_med,
                            "baseline_value": p7_med,
                            "relative_delta": rel_delta,
                            "direction": direction,
                        },
                        cohort_hash=f"momentum:{plat_name}:reactions",
                    )
                    signals.append(sig)

        # 7. Follower Intelligence (Gauge Semantics: Never Sum Total Followers)
        follower_rollups = [r for r in curr_rollups if r.normalized_metric == "FOLLOWERS_TOTAL"]
        if follower_rollups:
            latest_follower_rollup = max(follower_rollups, key=lambda r: r.period_start)
            latest_total = latest_follower_rollup.metric_value

            # Follower net change across window
            net_change_rollups = [r.metric_value for r in curr_rollups if r.normalized_metric == "FOLLOWERS_NET_CHANGE"]
            prev_net_change_rollups = [r.metric_value for r in prev_rollups if r.normalized_metric == "FOLLOWERS_NET_CHANGE"]

            if net_change_rollups and prev_net_change_rollups:
                curr_net = sum(net_change_rollups, Decimal("0"))
                prev_net = sum(prev_net_change_rollups, Decimal("0"))
                abs_delta, rel_delta = calculate_deltas(curr_net, prev_net)
                direction = determine_direction(rel_delta)

                sig_type = SignalType.FOLLOWER_GROWTH_UP if direction == "UP" else (SignalType.FOLLOWER_GROWTH_DOWN if direction == "DOWN" else None)
                if sig_type:
                    conf = calculate_confidence(len(net_change_rollups), is_stale=is_stale, is_partial=is_partial)
                    tier = classify_performance_tier(rel_delta)
                    sev = determine_severity(sig_type, tier, direction, is_stale=is_stale)

                    sig = _build_signal_dict(
                        client=client,
                        platform=plat_name,
                        signal_type=sig_type,
                        metric="FOLLOWERS_NET_CHANGE",
                        scope="account",
                        object_id="",
                        unified_post=None,
                        period_start=start_date,
                        period_end=end_date,
                        observed_value=curr_net,
                        baseline_value=prev_net,
                        absolute_delta=abs_delta,
                        relative_delta=rel_delta,
                        sample_size=len(net_change_rollups),
                        confidence_level=conf,
                        direction=direction,
                        severity=sev,
                        is_actionable=False,
                        evidence={
                            "followers_total_gauge": float(latest_total),
                            "current_net_growth": float(curr_net),
                            "previous_net_growth": float(prev_net),
                            "sample_days": len(net_change_rollups),
                        },
                        context={
                            "observed_value": curr_net,
                            "baseline_value": prev_net,
                            "followers_total": int(latest_total),
                            "relative_delta": rel_delta,
                            "direction": direction,
                        },
                        cohort_hash=f"followers:{plat_name}:growth",
                    )
                    signals.append(sig)

    # 8. Idempotent Persistence (if requested)
    persisted_signals = []
    for s_dict in signals:
        if persist:
            identity = s_dict["signal_identity"]
            obj, _ = BusinessSignal.objects.update_or_create(
                signal_identity=identity,
                defaults={
                    "client": client,
                    "platform": s_dict["platform"],
                    "signal_type": s_dict["signal_type"],
                    "metric": s_dict["metric"],
                    "scope": s_dict["scope"],
                    "object_id": s_dict["object_id"],
                    "unified_post": s_dict.get("unified_post_obj"),
                    "period_start": s_dict["period_start"],
                    "period_end": s_dict["period_end"],
                    "observed_value": s_dict["observed_value"],
                    "baseline_value": s_dict["baseline_value"],
                    "absolute_delta": s_dict["absolute_delta"],
                    "relative_delta": s_dict["relative_delta"],
                    "sample_size": s_dict["sample_size"],
                    "confidence_level": s_dict["confidence_level"],
                    "direction": s_dict["direction"],
                    "severity": s_dict["severity"],
                    "is_actionable": s_dict["is_actionable"],
                    "evidence": s_dict["evidence"],
                    "explanation_template": s_dict["explanation"],
                    "metadata": s_dict.get("metadata", {}),
                    "cohort_hash": s_dict.get("cohort_hash", ""),
                },
            )
            s_dict["id"] = obj.id
        persisted_signals.append(s_dict)

    return persisted_signals


def _build_signal_dict(
    client: Client,
    platform: str,
    signal_type: str,
    metric: str,
    scope: str,
    object_id: str,
    unified_post: Optional[UnifiedPost],
    period_start: date,
    period_end: date,
    observed_value: Optional[Decimal],
    baseline_value: Optional[Decimal],
    absolute_delta: Optional[Decimal],
    relative_delta: Optional[Decimal],
    sample_size: int,
    confidence_level: str,
    direction: str,
    severity: str,
    is_actionable: bool,
    evidence: Dict[str, Any],
    context: Dict[str, Any],
    cohort_hash: str,
) -> Dict[str, Any]:
    explanation = build_explanation(signal_type, context)
    sig_identity = compute_signal_identity(
        client_id=client.id,
        platform=platform,
        signal_type=signal_type,
        metric=metric,
        scope=scope,
        object_id=object_id,
        period_start=period_start,
        period_end=period_end,
        cohort_hash=cohort_hash,
    )

    return {
        "id": None,
        "signal_identity": sig_identity,
        "client_id": client.id,
        "platform": platform,
        "signal_type": signal_type,
        "metric": metric,
        "scope": scope,
        "object_id": object_id,
        "unified_post_id": unified_post.id if unified_post else None,
        "unified_post_obj": unified_post,
        "period_start": period_start,
        "period_end": period_end,
        "observed_value": observed_value,
        "baseline_value": baseline_value,
        "absolute_delta": absolute_delta,
        "relative_delta": relative_delta,
        "sample_size": sample_size,
        "confidence_level": confidence_level,
        "direction": direction,
        "severity": severity,
        "is_actionable": is_actionable,
        "evidence": evidence,
        "explanation": explanation,
        "cohort_hash": cohort_hash,
        "created_at": timezone.now().isoformat(),
    }


def get_executive_summary(
    client_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates structured executive summary for client.
    Contains best/weakest performers, direction indicators, winning formats,
    posting time recommendations, platform health, and data quality.
    Zero generative AI or LLM hallucinated prose.
    """
    client = Client.objects.filter(id=client_id, is_active=True).first()
    if not client:
        return {}

    today = timezone.now().date()
    end_date = date_to or today
    start_date = date_from or (end_date - timedelta(days=30))

    signals = generate_business_signals(
        client_id=client.id,
        date_from=start_date,
        date_to=end_date,
        platform=platform,
        persist=False,
    )

    # 1. Best & weakest content signals
    content_signals = [s for s in signals if s["scope"] == "post" and s["signal_type"] in (SignalType.CONTENT_OUTPERFORMING, SignalType.CONTENT_UNDERPERFORMING)]
    best_content = [s for s in content_signals if s["signal_type"] == SignalType.CONTENT_OUTPERFORMING]
    best_content.sort(key=lambda s: s["relative_delta"] or Decimal("-999"), reverse=True)

    weakest_content = [s for s in content_signals if s["signal_type"] == SignalType.CONTENT_UNDERPERFORMING]
    weakest_content.sort(key=lambda s: s["relative_delta"] or Decimal("999"))

    # 2. Winning formats
    format_signals = [s for s in signals if s["signal_type"] == SignalType.FORMAT_OUTPERFORMING]
    winning_formats = []
    for fs in format_signals:
        winning_formats.append({
            "format": fs["object_id"],
            "platform": fs["platform"],
            "metric": fs["metric"],
            "observed_median": float(fs["observed_value"]) if fs["observed_value"] else None,
            "baseline_median": float(fs["baseline_value"]) if fs["baseline_value"] else None,
            "relative_delta_pct": float((fs["relative_delta"] * 100).quantize(Decimal("0.1"))) if fs["relative_delta"] else None,
            "sample_size": fs["sample_size"],
            "confidence": fs["confidence_level"],
            "explanation": fs["explanation"],
        })

    # 3. Posting time recommendations
    time_signals = [s for s in signals if s["signal_type"] == SignalType.POSTING_TIME_OUTPERFORMING]
    time_insights = {
        "has_sufficient_data": len(time_signals) > 0,
        "recommendations": [
            {
                "bucket": ts["object_id"],
                "platform": ts["platform"],
                "relative_delta_pct": float((ts["relative_delta"] * 100).quantize(Decimal("0.1"))) if ts["relative_delta"] else None,
                "confidence": ts["confidence_level"],
                "sample_size": ts["sample_size"],
                "explanation": ts["explanation"],
            }
            for ts in time_signals
        ],
    }

    # 4. Overall engagement direction
    eng_signals = [s for s in signals if s["signal_type"] in (SignalType.ENGAGEMENT_TREND_UP, SignalType.ENGAGEMENT_TREND_DOWN)]
    engagement_direction = {
        "direction": eng_signals[0]["direction"] if eng_signals else "NEUTRAL",
        "relative_delta": float(eng_signals[0]["relative_delta"]) if eng_signals and eng_signals[0]["relative_delta"] is not None else 0.0,
        "confidence": eng_signals[0]["confidence_level"] if eng_signals else "NONE",
        "explanation": eng_signals[0]["explanation"] if eng_signals else "Stable engagement across recorded period.",
    }

    # 5. Follower direction
    fol_signals = [s for s in signals if s["signal_type"] in (SignalType.FOLLOWER_GROWTH_UP, SignalType.FOLLOWER_GROWTH_DOWN)]
    follower_direction = {
        "direction": fol_signals[0]["direction"] if fol_signals else "NEUTRAL",
        "net_change": float(fol_signals[0]["observed_value"]) if fol_signals and fol_signals[0]["observed_value"] else 0.0,
        "confidence": fol_signals[0]["confidence_level"] if fol_signals else "NONE",
        "explanation": fol_signals[0]["explanation"] if fol_signals else "Follower counts steady across period.",
    }

    # 6. Platform health & capability registry
    creds = list(PlatformCredential.objects.filter(client=client, is_active=True))
    capabilities_by_plat = {c.platform: get_provider_capability(c.platform, c) for c in creds}
    platform_health = {}
    for c in creds:
        cap = capabilities_by_plat[c.platform]
        fresh = get_client_platform_freshness(client.id, c.platform)
        status_label = "HEALTHY"
        if fresh.get("is_stale"):
            status_label = "STALE"
        elif cap.overall_support == SupportLevel.PARTIAL:
            status_label = "PARTIAL"

        platform_health[c.platform] = {
            "status": status_label,
            "overall_support": "FULL" if cap.overall_support == SupportLevel.SUPPORTED else ("PARTIAL" if cap.overall_support == SupportLevel.PARTIAL else "UNSUPPORTED"),
            "freshness_state": fresh.get("freshness_state", "FRESH"),
            "hours_since_last_sync": fresh.get("hours_since_last_sync"),
        }

    # 7. Data quality summary
    stale_signals = [s for s in signals if s["signal_type"] == SignalType.DATA_STALE]
    partial_signals = [s for s in signals if s["signal_type"] == SignalType.PROVIDER_PARTIAL]
    insufficient_signals = [s for s in signals if s["signal_type"] == SignalType.INSUFFICIENT_SAMPLE]

    data_quality = {
        "is_stale": len(stale_signals) > 0,
        "partial_capability_active": len(partial_signals) > 0,
        "insufficient_samples_count": len(insufficient_signals),
        "notes": [s["explanation"] for s in (stale_signals + partial_signals + insufficient_signals)[:5]],
    }

    # Format key signals for response (excluding internal unpersisted fields)
    formatted_signals = []
    for s in signals:
        formatted_signals.append({
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
        })

    # 8. Engagement Total Availability & Integrity Guard
    target_platform = (platform or "").lower()
    ig_cap = capabilities_by_plat.get("instagram")
    is_ig_partial = ig_cap and ig_cap.overall_support == SupportLevel.PARTIAL

    if target_platform == "instagram" and is_ig_partial:
        has_ig_shares = SocialMetricSnapshot.objects.filter(
            client=client,
            platform="instagram",
            normalized_metric="SHARES",
            bucket_timestamp__date__range=(start_date, end_date),
        ).exists()
        can_derive_ig, reason_ig, missing_ig = can_derive_metric(
            platform="instagram",
            capability_mode=SupportLevel.PARTIAL,
            metric="ENGAGEMENT_TOTAL",
            available_source_metrics={"REACTIONS": 1, "COMMENTS": 1, "SHARES": 1} if has_ig_shares else {"REACTIONS": 1, "COMMENTS": 1},
        )
        engagement_total_meta = {
            "metric": "ENGAGEMENT_TOTAL",
            "is_available": can_derive_ig,
            "value": None,
            "reason": reason_ig if not can_derive_ig else None,
            "missing_components": missing_ig if not can_derive_ig else [],
            "message": "Not available with current Instagram permissions" if not can_derive_ig else None,
        }
    elif target_platform == "facebook":
        engagement_total_meta = {
            "metric": "ENGAGEMENT_TOTAL",
            "is_available": True,
            "value": None,
            "reason": None,
            "missing_components": [],
            "message": None,
        }
    else:
        has_partial_channel = any(c.overall_support == SupportLevel.PARTIAL for c in capabilities_by_plat.values())
        engagement_total_meta = {
            "metric": "ENGAGEMENT_TOTAL",
            "is_available": not has_partial_channel,
            "value": None,
            "reason": "missing_required_components" if has_partial_channel else None,
            "missing_components": ["SHARES"] if has_partial_channel else [],
            "message": "Instagram component metrics (Shares) unavailable under current permissions" if has_partial_channel else None,
        }

    return {
        "client_id": client.id,
        "platform": platform or "all",
        "period": {
            "start": str(start_date),
            "end": str(end_date),
        },
        "engagement_total": engagement_total_meta,
        "key_signals": formatted_signals,
        "best_performing_content": formatted_signals[:5] if best_content else [],
        "weakest_performing_content": [s for s in formatted_signals if s["signal_type"] == SignalType.CONTENT_UNDERPERFORMING][:5],
        "winning_formats": winning_formats,
        "posting_time_insights": time_insights,
        "engagement_direction": engagement_direction,
        "follower_direction": follower_direction,
        "platform_health": platform_health,
        "data_quality": data_quality,
    }
