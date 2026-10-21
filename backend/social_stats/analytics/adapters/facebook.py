"""
Facebook Graph API Analytics Adapter for Bop Social.
Communicates with Meta Graph API v21.0 to extract Page and Post level metrics.
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

FACEBOOK_PAGE_METRICS = [
    "page_post_engagements",
    "page_daily_follows",
    "page_daily_unfollows",
    "page_views_total",
    "page_video_views",
    "page_video_view_time",
    "page_total_actions",
    "page_impressions",
    "page_impressions_unique",
]


class FacebookAnalyticsAdapter(BaseAnalyticsAdapter):
    """
    Adapter for Facebook Graph API v21.0 analytics queries.
    Pure transport layer; does not normalize observations.
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

        classification, msg = classify_provider_error(resp.status_code, body, platform="facebook")

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
        Fetches Page direct counters (followers, fans) and historical daily insights.
        """
        payload = ProviderPayload()
        page_id = getattr(credential, "page_id", "")
        access_token = getattr(credential, "access_token", "")

        if not page_id or not access_token:
            payload.errors.append("Missing page_id or access_token in Facebook credential")
            return payload

        if not since:
            since = date.today() - timedelta(days=30)
        if not until:
            until = date.today()

        since_str = since.isoformat()
        until_str = (until + timedelta(days=1)).isoformat()

        # 1. Fetch direct Page node fields (followers_count, fan_count)
        try:
            r = self.session.get(
                f"{BASE_URL}/{page_id}",
                params={"fields": "followers_count,fan_count,name", "access_token": access_token},
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r, credential)
            payload.rate_limit_headers.update(hdrs)
            if r.status_code == 200:
                payload.raw_data["page_node"] = r.json()
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.warnings.append(f"Failed to fetch Page direct counters: {str(e)[:120]}")

        # 2. Fetch page insights (batch with fallback)
        insights_data = []
        try:
            r = self.session.get(
                f"{BASE_URL}/{page_id}/insights",
                params={
                    "metric": ",".join(FACEBOOK_PAGE_METRICS),
                    "period": "day",
                    "since": since_str,
                    "until": until_str,
                    "access_token": access_token,
                },
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r, credential)
            payload.rate_limit_headers.update(hdrs)
            if r.status_code == 200 and "data" in r.json():
                insights_data = r.json().get("data", [])
            else:
                # Fallback to individual metric fetch
                payload.warnings.append("Page insights batch failed; falling back to individual metrics.")
                for m in FACEBOOK_PAGE_METRICS:
                    try:
                        r_single = self.session.get(
                            f"{BASE_URL}/{page_id}/insights",
                            params={"metric": m, "period": "day", "since": since_str, "until": until_str, "access_token": access_token},
                            timeout=10,
                        )
                        if r_single.status_code == 200 and "data" in r_single.json():
                            insights_data.extend(r_single.json().get("data", []))
                    except Exception:
                        pass
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.warnings.append(f"Page insights query failed: {str(e)[:120]}")

        payload.raw_data["insights"] = insights_data

        # 3. Reactions breakdown query
        try:
            r_rx = self.session.get(
                f"{BASE_URL}/{page_id}/insights",
                params={"metric": "page_actions_post_reactions_total", "period": "day", "since": since_str, "until": until_str, "access_token": access_token},
                timeout=self.timeout,
            )
            if r_rx.status_code == 200 and "data" in r_rx.json():
                payload.raw_data["reactions_breakdown"] = r_rx.json().get("data", [])
        except Exception as e:
            payload.warnings.append(f"Page reactions breakdown query warning: {str(e)[:100]}")

        payload.metadata = {"page_id": page_id, "since": since_str, "until": until_str}
        return payload

    def fetch_post_metrics(
        self,
        credential,
        limit: int = 25,
        since=None,
        until=None,
    ) -> ProviderPayload:
        """
        Fetches Page posts list and retrieves direct counters + post insights for each post.
        """
        payload = ProviderPayload()
        page_id = getattr(credential, "page_id", "")
        access_token = getattr(credential, "access_token", "")

        if not page_id or not access_token:
            payload.errors.append("Missing page_id or access_token in Facebook credential")
            return payload

        # 1. Fetch recent posts list
        posts_list = []
        try:
            r = self.session.get(
                f"{BASE_URL}/{page_id}/posts",
                params={
                    "fields": "id,message,story,created_time,permalink_url,full_picture",
                    "limit": limit,
                    "access_token": access_token,
                },
                timeout=self.timeout,
            )
            hdrs = self._handle_response_errors(r, credential)
            payload.rate_limit_headers.update(hdrs)
            if r.status_code == 200 and "data" in r.json():
                posts_list = r.json().get("data", [])
            else:
                payload.warnings.append(f"Post listing returned status {r.status_code}")
        except (AnalyticsAuthExpiredError, AnalyticsRateLimitedError, AnalyticsPermissionError):
            raise
        except Exception as e:
            payload.errors.append(f"Failed to fetch posts list: {str(e)[:120]}")
            return payload

        payload.raw_data["posts"] = []

        # 2. For each post, fetch direct engagement node + post insights
        for p in posts_list:
            post_id = p.get("id")
            if not post_id:
                continue

            post_entry = {
                "post_info": p,
                "direct_counters": {},
                "insights": [],
            }

            # Direct engagement counters (reactions.summary, comments.summary, shares)
            try:
                r_detail = self.session.get(
                    f"{BASE_URL}/{post_id}",
                    params={"fields": "shares,reactions.summary(true),comments.summary(true)", "access_token": access_token},
                    timeout=10,
                )
                if r_detail.status_code == 200:
                    post_entry["direct_counters"] = r_detail.json()
            except Exception as e:
                payload.warnings.append(f"Post {post_id} detail query error: {str(e)[:100]}")

            # Post Insights
            try:
                r_ins = self.session.get(
                    f"{BASE_URL}/{post_id}/insights",
                    params={
                        "metric": "post_impressions,post_impressions_unique,post_clicks,post_reactions_by_type_total,post_video_views",
                        "access_token": access_token,
                    },
                    timeout=10,
                )
                if r_ins.status_code == 200 and "data" in r_ins.json():
                    post_entry["insights"] = r_ins.json().get("data", [])
            except Exception as e:
                payload.warnings.append(f"Post {post_id} insights query error: {str(e)[:100]}")

            payload.raw_data["posts"].append(post_entry)

        payload.metadata = {"page_id": page_id, "posts_count": len(payload.raw_data["posts"])}
        return payload
