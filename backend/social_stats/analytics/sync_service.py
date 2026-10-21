"""
Analytics Synchronization Service for Bop Social.
Orchestrates capability-aware fetching, normalization, idempotent snapshot ingestion,
rate-limit evaluation, dual-writing to legacy models, and SyncLog auditing.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    DailyMetric,
    PostMetric,
    SyncLog,
)
from .adapters import (
    FacebookAnalyticsAdapter,
    InstagramAnalyticsAdapter,
    has_instagram_insights_capability,
)
from .exceptions import (
    AnalyticsAuthExpiredError,
    AnalyticsRateLimitedError,
    AnalyticsPermissionError,
    classify_provider_error,
)
from .ingestion import ingest_metric_snapshot
from .normalizers import normalize_facebook_metric, normalize_instagram_metric
from .rate_limits import evaluate_throttling

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    status: str  # 'success', 'partial', 'failed'
    records_seen: int = 0
    records_ingested: int = 0
    records_updated: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    capability_mode: str = "FULL"
    rate_limit_state: Dict = field(default_factory=dict)
    error_classification: Optional[str] = None


# ── Facebook Sync Flow ─────────────────────────────────────────────────────────

def sync_facebook_analytics(
    client_id: int,
    days: int = 30,
    cred: Optional[PlatformCredential] = None,
    adapter: Optional[FacebookAnalyticsAdapter] = None,
    dual_write: bool = True,
) -> SyncResult:
    """
    Executes controlled analytics sync for Facebook.
    Extracts raw payloads via FacebookAnalyticsAdapter, normalizes, and ingests.
    """
    result = SyncResult(status="success", capability_mode="FULL")
    sync_log = SyncLog.objects.create(platform="facebook", client_id=client_id, status="running")

    if not cred:
        cred = PlatformCredential.objects.filter(client_id=client_id, platform="facebook", is_active=True).first()

    if not cred:
        result.status = "failed"
        result.errors.append(f"No active Facebook credential for client {client_id}")
        sync_log.status = "failed"
        sync_log.error_message = result.errors[0]
        sync_log.finished_at = timezone.now()
        sync_log.save()
        return result

    # Check throttling policy
    decision, wait_secs = evaluate_throttling(cred.rate_limit_state)
    if decision == "COOLDOWN":
        result.status = "partial"
        result.warnings.append(f"Sync paused due to active rate-limit cooldown ({wait_secs}s remaining).")
        sync_log.status = "partial"
        sync_log.error_message = result.warnings[0]
        sync_log.finished_at = timezone.now()
        sync_log.save()
        return result

    fb_adapter = adapter or FacebookAnalyticsAdapter()

    try:
        # 1. Fetch Account / Page Metrics
        acct_payload = fb_adapter.fetch_account_metrics(cred)
        result.warnings.extend(acct_payload.warnings)
        result.errors.extend(acct_payload.errors)
        result.rate_limit_state = cred.rate_limit_state or {}

        page_id = cred.page_id
        page_node = acct_payload.raw_data.get("page_node", {})
        insights = acct_payload.raw_data.get("insights", [])
        reactions_breakdown = acct_payload.raw_data.get("reactions_breakdown", [])

        # Ingest direct Page node counters (followers_count, fan_count)
        now_bucket = timezone.now().replace(minute=0, second=0, microsecond=0)
        # Prefer modern followers_count; fallback to fan_count if absent
        fol_key = "followers_count" if "followers_count" in page_node else ("fan_count" if "fan_count" in page_node else None)
        if fol_key:
            result.records_seen += 1
            obs_list = normalize_facebook_metric(fol_key, page_node[fol_key], metric_scope="account")
            for obs in obs_list:
                _, created = ingest_metric_snapshot(
                    client=cred.client,
                    platform="facebook",
                    metric_scope="account",
                    object_id=page_id,
                    normalized_metric=obs.normalized_metric,
                    metric_value=obs.metric_value,
                    raw_metric_name=obs.raw_metric_name,
                    account_id=page_id,
                    bucket_period="day",
                    bucket_timestamp=now_bucket,
                    extra_dimensions=obs.extra_dimensions,
                    metadata=obs.metadata,
                )
                if created:
                    result.records_ingested += 1
                else:
                    result.records_updated += 1

        # Ingest daily Page insights
        daily_rollups: Dict[str, Dict] = {}
        for m in insights:
            m_name = m.get("name")
            for v in m.get("values", []):
                day_str = (v.get("end_time") or "")[:10]
                if not day_str:
                    continue
                val = v.get("value", 0)
                try:
                    bucket_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)
                except Exception:
                    bucket_dt = now_bucket

                result.records_seen += 1
                obs_list = normalize_facebook_metric(m_name, val, metric_scope="account")
                for obs in obs_list:
                    _, created = ingest_metric_snapshot(
                        client=cred.client,
                        platform="facebook",
                        metric_scope="account",
                        object_id=page_id,
                        normalized_metric=obs.normalized_metric,
                        metric_value=obs.metric_value,
                        raw_metric_name=obs.raw_metric_name,
                        account_id=page_id,
                        bucket_period="day",
                        bucket_timestamp=bucket_dt,
                        extra_dimensions=obs.extra_dimensions,
                    )
                    if created:
                        result.records_ingested += 1
                    else:
                        result.records_updated += 1

                # Legacy map accumulation
                daily_rollups.setdefault(day_str, {})
                if m_name == "page_post_engagements":
                    daily_rollups[day_str]["likes"] = val
                elif m_name == "page_views_total":
                    daily_rollups[day_str]["profile_views"] = val
                elif m_name == "page_daily_follows":
                    daily_rollups[day_str]["followers"] = val
                elif m_name == "page_daily_unfollows":
                    daily_rollups[day_str]["followers_lost"] = val
                elif m_name == "page_video_views":
                    daily_rollups[day_str]["fb_video_views"] = val
                elif m_name == "page_total_actions":
                    daily_rollups[day_str]["clicks"] = val
                elif m_name == "page_impressions_unique":
                    daily_rollups[day_str]["reach"] = val
                elif m_name == "page_impressions":
                    daily_rollups[day_str]["impressions"] = val

        # Ingest reactions breakdown
        for m in reactions_breakdown:
            for v in m.get("values", []):
                day_str = (v.get("end_time") or "")[:10]
                val = v.get("value", {})
                if day_str and isinstance(val, dict):
                    try:
                        bucket_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)
                    except Exception:
                        bucket_dt = now_bucket

                    obs_list = normalize_facebook_metric("page_actions_post_reactions_total", val, metric_scope="account")
                    for obs in obs_list:
                        ingest_metric_snapshot(
                            client=cred.client,
                            platform="facebook",
                            metric_scope="account",
                            object_id=page_id,
                            normalized_metric=obs.normalized_metric,
                            metric_value=obs.metric_value,
                            raw_metric_name=obs.raw_metric_name,
                            account_id=page_id,
                            bucket_period="day",
                            bucket_timestamp=bucket_dt,
                            extra_dimensions=obs.extra_dimensions,
                        )
                    if day_str in daily_rollups:
                        daily_rollups[day_str]["reactions"] = val

        # Dual-write: DailyMetric
        if dual_write:
            for d_str, vals in daily_rollups.items():
                DailyMetric.objects.update_or_create(
                    client=cred.client,
                    platform="facebook",
                    date=d_str,
                    defaults=vals,
                )

        # 2. Fetch Posts Metrics
        post_payload = fb_adapter.fetch_post_metrics(cred)
        result.warnings.extend(post_payload.warnings)
        result.errors.extend(post_payload.errors)

        for p_entry in post_payload.raw_data.get("posts", []):
            p_info = p_entry.get("post_info", {})
            post_id = p_info.get("id")
            if not post_id:
                continue

            created_time_str = p_info.get("created_time")
            try:
                p_dt = datetime.fromisoformat(created_time_str.replace("Z", "+00:00"))
            except Exception:
                p_dt = timezone.now()

            p_bucket = p_dt.replace(minute=0, second=0, microsecond=0)

            # Direct counters
            dc = p_entry.get("direct_counters", {})
            likes = dc.get("reactions", {}).get("summary", {}).get("total_count", 0)
            comments = dc.get("comments", {}).get("summary", {}).get("total_count", 0)
            shares = dc.get("shares", {}).get("count", 0)

            direct_map = {"reactions": likes, "comments": comments, "shares": shares}
            for raw_k, raw_v in direct_map.items():
                result.records_seen += 1
                obs_list = normalize_facebook_metric(raw_k, raw_v, metric_scope="post")
                for obs in obs_list:
                    _, created = ingest_metric_snapshot(
                        client=cred.client,
                        platform="facebook",
                        metric_scope="post",
                        object_id=post_id,
                        normalized_metric=obs.normalized_metric,
                        metric_value=obs.metric_value,
                        raw_metric_name=obs.raw_metric_name,
                        account_id=page_id,
                        bucket_period="day",
                        bucket_timestamp=p_bucket,
                        provider_timestamp=p_dt,
                        extra_dimensions=obs.extra_dimensions,
                    )
                    if created:
                        result.records_ingested += 1
                    else:
                        result.records_updated += 1

            # Post Insights
            post_imp = 0
            post_reach = 0
            post_clicks = 0
            for m in p_entry.get("insights", []):
                m_name = m.get("name")
                vals = m.get("values", [])
                val = vals[0].get("value", 0) if vals else 0

                if m_name == "post_impressions_unique":
                    post_reach = val
                elif m_name == "post_impressions":
                    post_imp = val
                elif m_name == "post_clicks":
                    post_clicks = val

                result.records_seen += 1
                obs_list = normalize_facebook_metric(m_name, val, metric_scope="post")
                for obs in obs_list:
                    _, created = ingest_metric_snapshot(
                        client=cred.client,
                        platform="facebook",
                        metric_scope="post",
                        object_id=post_id,
                        normalized_metric=obs.normalized_metric,
                        metric_value=obs.metric_value,
                        raw_metric_name=obs.raw_metric_name,
                        account_id=page_id,
                        bucket_period="day",
                        bucket_timestamp=p_bucket,
                        provider_timestamp=p_dt,
                        extra_dimensions=obs.extra_dimensions,
                    )
                    if created:
                        result.records_ingested += 1
                    else:
                        result.records_updated += 1

            # Dual-write: PostMetric
            if dual_write:
                caption = (p_info.get("message") or p_info.get("story") or "")[:500]
                PostMetric.objects.update_or_create(
                    client=cred.client,
                    platform="facebook",
                    post_id=post_id,
                    defaults={
                        "post_url": p_info.get("permalink_url", ""),
                        "post_type": "post",
                        "caption": caption,
                        "published_at": p_dt,
                        "thumbnail_url": p_info.get("full_picture", ""),
                        "impressions": post_imp or post_reach,
                        "reach": post_reach,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "clicks": post_clicks,
                    }
                )

        # Final status calculation
        has_any_records = (result.records_ingested > 0 or result.records_updated > 0)
        if result.errors:
            result.status = "partial" if has_any_records else "failed"
        elif result.warnings:
            result.status = "partial" if has_any_records else "failed"

        sync_log.status = result.status
        sync_log.records_synced = result.records_ingested + result.records_updated
        sync_log.error_message = "; ".join(result.warnings + result.errors)[:500]

    except AnalyticsAuthExpiredError as e:
        result.status = "failed"
        result.error_classification = "AUTH_EXPIRED"
        result.errors.append(str(e))
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    except AnalyticsRateLimitedError as e:
        result.status = "failed"
        result.error_classification = "RATE_LIMITED"
        result.errors.append(str(e))
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    except Exception as e:
        result.status = "failed"
        result.errors.append(f"Unexpected sync failure: {str(e)}")
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    finally:
        sync_log.finished_at = timezone.now()
        sync_log.save()

    return result


# ── Instagram Sync Flow ────────────────────────────────────────────────────────

def sync_instagram_analytics(
    client_id: int,
    days: int = 30,
    cred: Optional[PlatformCredential] = None,
    adapter: Optional[InstagramAnalyticsAdapter] = None,
    dual_write: bool = True,
) -> SyncResult:
    """
    Executes controlled analytics sync for Instagram.
    Supports FULL capability mode or PARTIAL degradation (basic media counters).
    """
    result = SyncResult(status="success")
    sync_log = SyncLog.objects.create(platform="instagram", client_id=client_id, status="running")

    if not cred:
        cred = PlatformCredential.objects.filter(client_id=client_id, platform="instagram", is_active=True).first()

    if not cred:
        result.status = "failed"
        result.errors.append(f"No active Instagram credential for client {client_id}")
        sync_log.status = "failed"
        sync_log.error_message = result.errors[0]
        sync_log.finished_at = timezone.now()
        sync_log.save()
        return result

    # Capability mode
    has_cap = has_instagram_insights_capability(cred)
    result.capability_mode = "FULL" if has_cap else "PARTIAL"

    # Throttling
    decision, wait_secs = evaluate_throttling(cred.rate_limit_state)
    if decision == "COOLDOWN":
        result.status = "partial"
        result.warnings.append(f"Sync paused due to active rate-limit cooldown ({wait_secs}s remaining).")
        sync_log.status = "partial"
        sync_log.error_message = result.warnings[0]
        sync_log.finished_at = timezone.now()
        sync_log.save()
        return result

    ig_adapter = adapter or InstagramAnalyticsAdapter()

    try:
        # 1. Fetch Account Metrics
        acct_payload = ig_adapter.fetch_account_metrics(cred)
        result.warnings.extend(acct_payload.warnings)
        result.errors.extend(acct_payload.errors)
        result.rate_limit_state = cred.rate_limit_state or {}

        ig_user_id = cred.instagram_account_id
        acct_node = acct_payload.raw_data.get("account_node", {})
        day_insights = acct_payload.raw_data.get("day_insights", [])
        total_insights = acct_payload.raw_data.get("total_insights", [])

        # Ingest direct Account node counters (followers_count)
        now_bucket = timezone.now().replace(minute=0, second=0, microsecond=0)
        if "followers_count" in acct_node:
            result.records_seen += 1
            obs_list = normalize_instagram_metric("followers_count", acct_node["followers_count"], metric_scope="account")
            for obs in obs_list:
                _, created = ingest_metric_snapshot(
                    client=cred.client,
                    platform="instagram",
                    metric_scope="account",
                    object_id=ig_user_id,
                    normalized_metric=obs.normalized_metric,
                    metric_value=obs.metric_value,
                    raw_metric_name=obs.raw_metric_name,
                    account_id=ig_user_id,
                    bucket_period="day",
                    bucket_timestamp=now_bucket,
                )
                if created:
                    result.records_ingested += 1
                else:
                    result.records_updated += 1

        daily_rollups: Dict[str, Dict] = {}

        # If in FULL mode, ingest daily insights
        if has_cap:
            for m in day_insights:
                m_name = m.get("name")
                for v in m.get("values", []):
                    day_str = (v.get("end_time") or "")[:10]
                    if not day_str:
                        continue
                    val = v.get("value", 0)
                    try:
                        bucket_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)
                    except Exception:
                        bucket_dt = now_bucket

                    result.records_seen += 1
                    obs_list = normalize_instagram_metric(m_name, val, metric_scope="account")
                    for obs in obs_list:
                        _, created = ingest_metric_snapshot(
                            client=cred.client,
                            platform="instagram",
                            metric_scope="account",
                            object_id=ig_user_id,
                            normalized_metric=obs.normalized_metric,
                            metric_value=obs.metric_value,
                            raw_metric_name=obs.raw_metric_name,
                            account_id=ig_user_id,
                            bucket_period="day",
                            bucket_timestamp=bucket_dt,
                        )
                        if created:
                            result.records_ingested += 1
                        else:
                            result.records_updated += 1

                    daily_rollups.setdefault(day_str, {})
                    if m_name == "reach":
                        daily_rollups[day_str]["reach"] = val
                    elif m_name == "follower_count":
                        daily_rollups[day_str]["followers"] = val

            # Total value metrics
            for m in total_insights:
                m_name = m.get("name")
                for v in m.get("values", []):
                    day_str = (v.get("end_time") or "")[:10]
                    val = v.get("value", 0)
                    if not day_str:
                        continue
                    try:
                        bucket_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)
                    except Exception:
                        bucket_dt = now_bucket

                    result.records_seen += 1
                    obs_list = normalize_instagram_metric(m_name, val, metric_scope="account")
                    for obs in obs_list:
                        _, created = ingest_metric_snapshot(
                            client=cred.client,
                            platform="instagram",
                            metric_scope="account",
                            object_id=ig_user_id,
                            normalized_metric=obs.normalized_metric,
                            metric_value=obs.metric_value,
                            raw_metric_name=obs.raw_metric_name,
                            account_id=ig_user_id,
                            bucket_period="day",
                            bucket_timestamp=bucket_dt,
                            extra_dimensions=obs.extra_dimensions,
                        )
                        if created:
                            result.records_ingested += 1
                        else:
                            result.records_updated += 1

                    daily_rollups.setdefault(day_str, {})
                    if m_name == "total_interactions":
                        daily_rollups[day_str]["total_interactions"] = val
                    elif m_name == "profile_views":
                        daily_rollups[day_str]["profile_views"] = val
                    elif m_name == "website_clicks":
                        daily_rollups[day_str]["website_clicks"] = val
                    elif m_name == "likes":
                        daily_rollups[day_str]["likes"] = val
                    elif m_name == "comments":
                        daily_rollups[day_str]["comments"] = val
                    elif m_name == "shares":
                        daily_rollups[day_str]["shares"] = val
                    elif m_name == "saves":
                        daily_rollups[day_str]["saves"] = val
        else:
            result.warnings.append("Account timeseries skipped (partial capability mode).")

        # Dual-write: DailyMetric
        if dual_write and daily_rollups:
            for d_str, vals in daily_rollups.items():
                DailyMetric.objects.update_or_create(
                    client=cred.client,
                    platform="instagram",
                    date=d_str,
                    defaults=vals,
                )

        # 2. Fetch Media Metrics
        media_payload = ig_adapter.fetch_post_metrics(cred)
        result.warnings.extend(media_payload.warnings)
        result.errors.extend(media_payload.errors)

        for m_entry in media_payload.raw_data.get("media", []):
            m_info = m_entry.get("media_info", {})
            media_id = m_info.get("id")
            if not media_id:
                continue

            media_type = (m_info.get("media_type") or "").upper()
            scope = "reel" if media_type in ("REEL", "IG_REEL") else ("video" if media_type == "VIDEO" else "post")

            ts_str = m_info.get("timestamp")
            try:
                m_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                m_dt = timezone.now()

            m_bucket = m_dt.replace(minute=0, second=0, microsecond=0)

            # Direct engagement node (like_count, comments_count)
            dc = m_entry.get("direct_counters", {})
            likes = dc.get("like_count", 0)
            comments = dc.get("comments_count", 0)

            for raw_k, raw_v in (("like_count", likes), ("comments_count", comments)):
                result.records_seen += 1
                obs_list = normalize_instagram_metric(raw_k, raw_v, metric_scope=scope, context={"media_type": media_type})
                for obs in obs_list:
                    _, created = ingest_metric_snapshot(
                        client=cred.client,
                        platform="instagram",
                        metric_scope=scope,
                        object_id=media_id,
                        normalized_metric=obs.normalized_metric,
                        metric_value=obs.metric_value,
                        raw_metric_name=obs.raw_metric_name,
                        account_id=ig_user_id,
                        bucket_period="day",
                        bucket_timestamp=m_bucket,
                        provider_timestamp=m_dt,
                        metadata={"media_type": media_type},
                    )
                    if created:
                        result.records_ingested += 1
                    else:
                        result.records_updated += 1

            # Media Insights (if available in FULL mode)
            m_reach = 0
            m_saves = 0
            m_shares = 0
            m_views = 0
            for ins_item in m_entry.get("insights", []):
                ins_name = ins_item.get("name")
                vals = ins_item.get("values", [])
                val = vals[0].get("value", 0) if vals else 0

                if ins_name == "reach":
                    m_reach = val
                elif ins_name in ("saved", "saves"):
                    m_saves = val
                elif ins_name == "shares":
                    m_shares = val
                elif ins_name in ("plays", "video_views"):
                    m_views = val

                result.records_seen += 1
                obs_list = normalize_instagram_metric(ins_name, val, metric_scope=scope, context={"media_type": media_type})
                for obs in obs_list:
                    _, created = ingest_metric_snapshot(
                        client=cred.client,
                        platform="instagram",
                        metric_scope=scope,
                        object_id=media_id,
                        normalized_metric=obs.normalized_metric,
                        metric_value=obs.metric_value,
                        raw_metric_name=obs.raw_metric_name,
                        account_id=ig_user_id,
                        bucket_period="day",
                        bucket_timestamp=m_bucket,
                        provider_timestamp=m_dt,
                        metadata=obs.metadata,
                    )
                    if created:
                        result.records_ingested += 1
                    else:
                        result.records_updated += 1

            # Dual-write: PostMetric
            if dual_write:
                thumb = m_info.get("thumbnail_url") or m_info.get("media_url", "")
                PostMetric.objects.update_or_create(
                    client=cred.client,
                    platform="instagram",
                    post_id=media_id,
                    defaults={
                        "post_url": m_info.get("permalink", ""),
                        "post_type": media_type.lower(),
                        "caption": (m_info.get("caption") or "")[:500],
                        "published_at": m_dt,
                        "thumbnail_url": thumb,
                        "reach": m_reach,
                        "impressions": m_views if m_views else m_reach,
                        "likes": likes,
                        "comments": comments,
                        "saves": m_saves,
                        "shares": m_shares,
                        "video_views": m_views,
                    }
                )

        # Status
        has_any_records = (result.records_ingested > 0 or result.records_updated > 0)
        if not has_cap:
            result.status = "partial"
        elif result.errors:
            result.status = "partial" if has_any_records else "failed"
        elif result.warnings:
            result.status = "partial" if has_any_records else "failed"

        sync_log.status = result.status
        sync_log.records_synced = result.records_ingested + result.records_updated
        sync_log.error_message = "; ".join(result.warnings + result.errors)[:500]

    except AnalyticsAuthExpiredError as e:
        result.status = "failed"
        result.error_classification = "AUTH_EXPIRED"
        result.errors.append(str(e))
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    except AnalyticsRateLimitedError as e:
        result.status = "failed"
        result.error_classification = "RATE_LIMITED"
        result.errors.append(str(e))
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    except Exception as e:
        result.status = "failed"
        result.errors.append(f"Unexpected sync failure: {str(e)}")
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:500]
    finally:
        sync_log.finished_at = timezone.now()
        sync_log.save()

    return result
