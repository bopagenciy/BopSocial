"""
Rate limit quota tracking and throttling policies for Meta Graph API.
Parses X-App-Usage and X-Business-Use-Case-Usage headers and updates PlatformCredential safely.
"""
import json
import logging
from datetime import timedelta
from typing import Dict, Optional, Tuple
from django.utils import timezone

logger = logging.getLogger(__name__)


def parse_meta_rate_limit_headers(headers: Dict) -> Dict:
    """
    Parses Meta Graph API rate-limit headers:
      - X-App-Usage: {"call_count": int, "total_cputime": int, "total_time": int}
      - X-Business-Use-Case-Usage: {"<id>": [{"type": str, "call_count": int, "total_cputime": int, "total_time": int, "estimated_time_to_regain_access": int}]}
    Returns a normalized, secret-free dictionary of usage percentages.
    """
    normalized = {
        "app_usage_percent": 0,
        "business_usage_percent": 0,
        "last_updated_at": timezone.now().isoformat(),
    }

    if not headers or not isinstance(headers, dict):
        return normalized

    # 1. Parse X-App-Usage
    raw_app = headers.get("X-App-Usage") or headers.get("x-app-usage")
    if raw_app:
        try:
            data = json.loads(raw_app) if isinstance(raw_app, str) else raw_app
            call_count = data.get("call_count", 0)
            cpu = data.get("total_cputime", 0)
            total_time = data.get("total_time", 0)
            normalized["app_usage_percent"] = max(call_count, cpu, total_time)
        except Exception as e:
            logger.debug(f"Could not parse X-App-Usage header: {e}")

    # 2. Parse X-Business-Use-Case-Usage
    raw_buc = headers.get("X-Business-Use-Case-Usage") or headers.get("x-business-use-case-usage")
    if raw_buc:
        try:
            data = json.loads(raw_buc) if isinstance(raw_buc, str) else raw_buc
            max_buc = 0
            # Format can be dict of lists
            for _obj_id, entries in data.items():
                if isinstance(entries, list):
                    for entry in entries:
                        call_count = entry.get("call_count", 0)
                        cpu = entry.get("total_cputime", 0)
                        total_time = entry.get("total_time", 0)
                        max_buc = max(max_buc, call_count, cpu, total_time)
            normalized["business_usage_percent"] = max_buc
        except Exception as e:
            logger.debug(f"Could not parse X-Business-Use-Case-Usage header: {e}")

    return normalized


def update_credential_rate_limit_state(credential, headers: Dict, is_429: bool = False, cooldown_seconds: int = 900) -> Dict:
    """
    Updates the rate_limit_state on PlatformCredential with quota info.
    Guarantees no tokens or secret headers are stored.
    """
    if not credential:
        return {}

    parsed = parse_meta_rate_limit_headers(headers)
    current_state = dict(getattr(credential, "rate_limit_state", {}) or {})

    current_state["app_usage_percent"] = parsed["app_usage_percent"]
    current_state["business_usage_percent"] = parsed["business_usage_percent"]
    current_state["last_checked_at"] = parsed["last_updated_at"]

    now = timezone.now()
    if is_429 or parsed["app_usage_percent"] >= 90 or parsed["business_usage_percent"] >= 90:
        current_state["last_rate_limit_at"] = now.isoformat()
        current_state["cooldown_until"] = (now + timedelta(seconds=cooldown_seconds)).isoformat()
    elif "cooldown_until" in current_state:
        # Check if cooldown has expired
        try:
            cooldown_dt = timezone.datetime.fromisoformat(current_state["cooldown_until"])
            if now >= cooldown_dt:
                current_state["cooldown_until"] = None
        except Exception:
            current_state["cooldown_until"] = None

    # Sanity check: Ensure no secret fields ever leak into state
    for forbidden_key in ("access_token", "refresh_token", "Authorization", "secret"):
        current_state.pop(forbidden_key, None)

    credential.rate_limit_state = current_state
    credential.save(update_fields=["rate_limit_state"])
    return current_state


def evaluate_throttling(rate_limit_state: Optional[Dict]) -> Tuple[str, int]:
    """
    Evaluates current rate limit state and returns (policy_decision, wait_seconds).
    Decisions:
      - 'COOLDOWN': Quota >= 90% or active cooldown; pause sync calls.
      - 'DEFER_HISTORICAL': Quota >= 80%; only sync recent active posts, defer deep history.
      - 'NORMAL': Quota < 80%; full execution permitted.
    """
    if not rate_limit_state or not isinstance(rate_limit_state, dict):
        return "NORMAL", 0

    now = timezone.now()

    # 1. Active cooldown check
    cooldown_str = rate_limit_state.get("cooldown_until")
    if cooldown_str:
        try:
            cooldown_dt = timezone.datetime.fromisoformat(cooldown_str)
            if cooldown_dt > now:
                remaining = int((cooldown_dt - now).total_seconds())
                return "COOLDOWN", max(1, remaining)
        except Exception:
            pass

    app_pct = rate_limit_state.get("app_usage_percent", 0)
    buc_pct = rate_limit_state.get("business_usage_percent", 0)
    max_pct = max(app_pct, buc_pct)

    # 2. Critical threshold (>= 90%)
    if max_pct >= 90:
        return "COOLDOWN", 900

    # 3. Warning threshold (>= 80%)
    if max_pct >= 80:
        return "DEFER_HISTORICAL", 0

    return "NORMAL", 0
