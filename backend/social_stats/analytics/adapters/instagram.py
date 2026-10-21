"""
Instagram Graph API Analytics Adapter for Bop Social.
Communicates with Meta Graph API v21.0 to extract Professional Account and Media metrics,
supporting both FULL mode (with instagram_manage_insights) and PARTIAL mode (basic media counters).
"""
import logging
import requests
from typing import Dict, List, Optional
from datetime import date, timedelta

from .base import BaseAnalyticsAdapter, ProviderPayload
from ..exceptions import (
    AnalyticsAuthExpiredError,
    AnalyticsRateLimitedError,
    AnalyticsPermissionError,
    classify_provider_error,
)
from ..rate_limits import update_credential_rate_limit_state

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def has_instagram_insights_capability(credential) -> bool:
    """Checks whether the credential has scope for advanced insights (instagram_manage_insights)."""
    if not credential or not getattr(credential, "scope", ""):
        return False
    scopes = [s.strip().lower() for s in credential.scope.replace(",", " ").split() if s.strip()]
    return "instagram_manage_insights" in scopes


class InstagramAnalyticsAdapter(BaseAnalyticsAdapter):
    """
    Adapter for Instagram Graph API v21.0 analytics queries.
    Differentiates between FULL capability and PARTIAL capability degradation.
    """

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 15):
        self.session = session or requests.Session()
        self.timeout = timeout

    def _handle_response_errors(self, resp: requests.Response, credential=None) -> Dict:
        """Inspects status code, captures rate limit headers, and raises categorized exceptions if critical."""
        headers = dict(resp.headers)
        if credential:
            update_credential_rate_limit_state(credential, headers, is_429=(resp.status_code == 429))

        if resp.status_code == 200:
            return headers

        try:
            body = resp.json()
        except Exception:
            body = {"error": {"message": resp.text}}

        classification, msg = classify_provider_error(resp.status_code, body, platform="instagram")

        if classification == "AUTH_EXPIRED":
            raise AnalyticsAuthExpiredError(msg, status_code=resp.status_code, details=body)
        elif classification == "RATE_LIMITED":
            raise AnalyticsRateLimitedError(msg, status_code=resp.status_code, details=body)
        elif classification == "PERMISSION_ERROR":
            raise AnalyticsPermissionError(msg, status_code=resp.status_code, details=body)

        return headers

    def fetch_account_metrics(
        self,
        credential,
        since=None,
        until=None,
    ) -> ProviderPayload:
        """
        Fetches Instagram Account metrics.
        In FULL mode: fetches direct node + daily reach/follower counts + total_value interactions.
        In PARTIAL mode: fetches direct node only; skips insights safely without failing.
        """
        payload = ProviderPayload()
        ig_user_id = getattr(credential, "instagram_account_id", "")
        access_token = getattr(credential, "access_token", "")

        if not ig_user_id or not access_token:
            payload.errors.append("Missing instagram_account_id or access_token in Instagram credential")
            return payload

        has_cap = has_instagram_insights_capability(credential)
        mode = "FULL" if has_cap else "PARTIAL"
        payload.metadata["capability_mode"] = mode

        # 1. Fetch direct account node (followers_count, follows_count, media_count) — Available in both modes
        try:
            r = self.session.get(
                f"{BASE_URL}/{ig_user_id}",
                params={"fields": "followers_count,follows_count,media_count,name,username", "access_token": access_token},
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r, credential)
            payload.rate_limit_headers.update(hdrs)
            if r.status_code == 200:
                payload.raw_data["account_node"] = r.json()
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.warnings.append(f"Failed to fetch Instagram account direct counters: {str(e)[:120]}")

        # If PARTIAL mode, do not call advanced insights
        if not has_cap:
            payload.warnings.append(
                "Advanced account insights skipped: 'instagram_manage_insights' scope missing. Mode: PARTIAL."
            )
            return payload

        if not since:
            since = date.today() - timedelta(days=30)
        if not until:
            until = date.today()

        since_str = since.isoformat()
        until_str = (until + timedelta(days=1)).isoformat()

        # 2. Fetch standard daily insights (reach, follower_count)
        try:
            r_std = self.session.get(
                f"{BASE_URL}/{ig_user_id}/insights",
                params={
                    "metric": "reach,follower_count",
                    "period": "day",
                    "since": since_str,
                    "until": until_str,
                    "access_token": access_token,
                },
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r_std, credential)
            payload.rate_limit_headers.update(hdrs)
            if r_std.status_code == 200 and "data" in r_std.json():
                payload.raw_data["day_insights"] = r_std.json().get("data", [])
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.warnings.append(f"Standard account insights error: {str(e)[:100]}")

        # 3. Fetch total_value daily insights (profile_views, website_clicks, total_interactions, etc.)
        try:
            r_tot = self.session.get(
                f"{BASE_URL}/{ig_user_id}/insights",
                params={
                    "metric": ",".join([
                        "profile_views", "website_clicks", "accounts_engaged",
                        "total_interactions", "likes", "comments", "shares", "saves",
                        "follows_and_unfollows",
                    ]),
                    "period": "day",
                    "metric_type": "total_value",
                    "since": since_str,
                    "until": until_str,
                    "access_token": access_token,
                },
                timeout=self.timeout,
            )
            if r_tot.status_code == 200 and "data" in r_tot.json():
                payload.raw_data["total_insights"] = r_tot.json().get("data", [])
        except Exception as e:
            payload.warnings.append(f"Total value insights error: {str(e)[:100]}")

        return payload

    def fetch_post_metrics(
        self,
        credential,
        limit: int = 25,
        since=None,
        until=None,
    ) -> ProviderPayload:
        """
        Fetches Instagram Media list and retrieves direct counters + media insights per object.
        """
        payload = ProviderPayload()
        ig_user_id = getattr(credential, "instagram_account_id", "")
        access_token = getattr(credential, "access_token", "")

        if not ig_user_id or not access_token:
            payload.errors.append("Missing instagram_account_id or access_token in Instagram credential")
            return payload

        has_cap = has_instagram_insights_capability(credential)
        mode = "FULL" if has_cap else "PARTIAL"
        payload.metadata["capability_mode"] = mode

        # 1. Fetch recent media list
        media_list = []
        try:
            r = self.session.get(
                f"{BASE_URL}/{ig_user_id}/media",
                params={
                    "fields": "id,caption,media_type,permalink,timestamp,media_url,thumbnail_url",
                    "limit": limit,
                    "access_token": access_token,
                },
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r, credential)
            payload.rate_limit_headers.update(hdrs)
            if r.status_code == 200 and "data" in r.json():
                media_list = r.json().get("data", [])
            else:
                payload.warnings.append(f"Media listing returned status {r.status_code}")
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.errors.append(f"Failed to fetch media list: {str(e)[:120]}")
            return payload

        payload.raw_data["media"] = []

        # 2. For each media object, fetch direct engagement counters + media insights (if FULL)
        for m in media_list:
            media_id = m.get("id")
            if not media_id:
                continue

            media_type = (m.get("media_type") or "").upper()
            media_entry = {
                "media_info": m,
                "direct_counters": {},
                "insights": [],
            }

            # Direct engagement node (like_count, comments_count) — Always queryable
            try:
                r_direct = self.session.get(
                    f"{BASE_URL}/{media_id}",
                    params={"fields": "like_count,comments_count", "access_token": access_token},
                    timeout=10,
                )
                if r_direct.status_code == 200:
                    media_entry["direct_counters"] = r_direct.json()
            except Exception as e:
                payload.warnings.append(f"Media {media_id} direct counters error: {str(e)[:100]}")

            # Media Insights (only if FULL mode)
            if has_cap:
                if media_type in ("REEL", "IG_REEL"):
                    metrics = "reach,saved,shares,plays,ig_reels_video_view_total_time,ig_reels_avg_watch_time"
                elif media_type == "VIDEO":
                    metrics = "reach,saved,shares,video_views"
                else:
                    metrics = "reach,saved,shares,total_interactions"

                try:
                    r_ins = self.session.get(
                        f"{BASE_URL}/{media_id}/insights",
                        params={"metric": metrics, "access_token": access_token},
                        timeout=10,
                    )
                    if r_ins.status_code == 200 and "data" in r_ins.json():
                        media_entry["insights"] = r_ins.json().get("data", [])
                except Exception as e:
                    payload.warnings.append(f"Media {media_id} insights error: {str(e)[:100]}")

            payload.raw_data["media"].append(media_entry)

        payload.metadata["media_count"] = len(payload.raw_data["media"])
        return payload

    def fetch_story_metrics(self, credential) -> ProviderPayload:
        """
        Fetches active ephemeral stories and their metrics.
        Handles expired stories safely without failing.
        """
        payload = ProviderPayload()
        ig_user_id = getattr(credential, "instagram_account_id", "")
        access_token = getattr(credential, "access_token", "")

        if not ig_user_id or not access_token:
            payload.errors.append("Missing credentials for stories fetch")
            return payload

        has_cap = has_instagram_insights_capability(credential)
        if not has_cap:
            payload.warnings.append("Story insights require instagram_manage_insights scope. Skipped.")
            return payload

        stories = []
        try:
            r = self.session.get(
                f"{BASE_URL}/{ig_user_id}/stories",
                params={"fields": "id,media_type,timestamp,media_url", "access_token": access_token},
                timeout=self.timeout,
            )
            self._handle_response_errors(r, credential)
            if r.status_code == 200 and "data" in r.json():
                stories = r.json().get("data", [])
        except Exception as e:
            payload.warnings.append(f"Story listing query: {str(e)[:100]}")
            return payload

        payload.raw_data["stories"] = []
        for s in stories:
            story_id = s.get("id")
            if not story_id:
                continue

            entry = {"story_info": s, "insights": []}
            try:
                r_ins = self.session.get(
                    f"{BASE_URL}/{story_id}/insights",
                    params={"metric": "reach,impressions,replies,exits,taps_forward,taps_back", "access_token": access_token},
                    timeout=10,
                )
                if r_ins.status_code == 200 and "data" in r_ins.json():
                    entry["insights"] = r_ins.json().get("data", [])
                elif r_ins.status_code in (400, 404):
                    # Story expired or not found
                    entry["expired"] = True
            except Exception as e:
                payload.warnings.append(f"Story {story_id} insights: {str(e)[:100]}")

            payload.raw_data["stories"].append(entry)

        return payload
