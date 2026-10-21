"""
Error classifications and exception hierarchy for Bop Social Analytics.
Provides deterministic error mapping from Meta Graph API responses.
"""
from typing import Dict, Optional, Tuple


class AnalyticsError(Exception):
    """Base exception for social analytics errors."""
    def __init__(self, message: str, classification: str = "UNKNOWN_ERROR", status_code: Optional[int] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.classification = classification
        self.status_code = status_code
        self.details = details or {}


class AnalyticsAuthExpiredError(AnalyticsError):
    """Token has expired, been invalidated, or session logged out. Requires operator re-authentication."""
    def __init__(self, message: str, status_code: Optional[int] = 401, details: Optional[Dict] = None):
        super().__init__(message, classification="AUTH_EXPIRED", status_code=status_code, details=details)


class AnalyticsPermissionError(AnalyticsError):
    """Missing permission / OAuth scope required to access insights or media."""
    def __init__(self, message: str, status_code: Optional[int] = 403, details: Optional[Dict] = None):
        super().__init__(message, classification="PERMISSION_ERROR", status_code=status_code, details=details)


class AnalyticsRateLimitedError(AnalyticsError):
    """Provider API quota exceeded (HTTP 429 or Meta code 4/17/32/613). Requires backoff."""
    def __init__(self, message: str, status_code: Optional[int] = 429, retry_after: int = 300, details: Optional[Dict] = None):
        super().__init__(message, classification="RATE_LIMITED", status_code=status_code, details=details)
        self.retry_after = retry_after


class AnalyticsObjectUnavailableError(AnalyticsError):
    """Provider object (page, post, media, story) no longer exists or has expired."""
    def __init__(self, message: str, status_code: Optional[int] = 404, details: Optional[Dict] = None):
        super().__init__(message, classification="OBJECT_UNAVAILABLE", status_code=status_code, details=details)


class AnalyticsMetricUnsupportedError(AnalyticsError):
    """Requested metric is deprecated or unsupported for the given media type/surface."""
    def __init__(self, message: str, status_code: Optional[int] = 400, details: Optional[Dict] = None):
        super().__init__(message, classification="METRIC_UNSUPPORTED", status_code=status_code, details=details)


class AnalyticsTemporaryProviderError(AnalyticsError):
    """Transient server-side provider downtime (HTTP 500, 502, 503, 504). Retryable."""
    def __init__(self, message: str, status_code: Optional[int] = 500, details: Optional[Dict] = None):
        super().__init__(message, classification="TEMPORARY_PROVIDER_ERROR", status_code=status_code, details=details)


def classify_provider_error(status_code: int, error_body: Optional[Dict] = None, platform: str = "facebook") -> Tuple[str, str]:
    """
    Classifies HTTP status and Meta Graph API error payload into a standardized category.
    Returns (classification_name, human_message).
    """
    err = (error_body or {}).get("error", {}) if isinstance(error_body, dict) else {}
    code = err.get("code")
    subcode = err.get("error_subcode")
    raw_msg = err.get("message") or f"HTTP {status_code}"

    # 1. Auth Expired
    # Meta code 190 (Invalid OAuth access token), subcode 463 (expired), 467 (invalidated)
    if status_code == 401 or code == 190 or subcode in (463, 467):
        return "AUTH_EXPIRED", f"Authentication token expired or revoked (code {code}, subcode {subcode}): {raw_msg}"

    # 2. Rate Limits
    # Meta code 4 (Application request limit reached), 17 (User request limit), 32 (Page request limit), 613 (Calls to stream have exceeded the rate of 600 calls per 600 seconds)
    if status_code == 429 or code in (4, 17, 32, 613):
        return "RATE_LIMITED", f"Provider rate limit reached (code {code}): {raw_msg}"

    # 3. Permissions
    # Meta code 10 (Permission denied / application does not have permission), 200-299 (permission error)
    if status_code == 403 or code == 10 or (isinstance(code, int) and 200 <= code <= 299):
        return "PERMISSION_ERROR", f"Missing permissions (code {code}): {raw_msg}"

    # 4. Object Unavailable / Deleted
    # Meta code 100 with subcode 33 (Unsupported get request. Object with ID does not exist) or HTTP 404
    if status_code == 404 or (code == 100 and subcode == 33):
        return "OBJECT_UNAVAILABLE", f"Provider object does not exist or has expired (code {code}, subcode {subcode}): {raw_msg}"

    # 5. Metric Unsupported
    # Meta code 100 without subcode 33, e.g. "The value must be a valid insights metric"
    if status_code == 400 and ("metric" in raw_msg.lower() or "invalid parameter" in raw_msg.lower()):
        return "METRIC_UNSUPPORTED", f"Metric not supported for this object (code {code}): {raw_msg}"

    # 6. Temporary Provider Error
    if status_code in (500, 502, 503, 504) or code in (1, 2):
        return "TEMPORARY_PROVIDER_ERROR", f"Transient provider failure (status {status_code}, code {code}): {raw_msg}"

    return "UNKNOWN_ERROR", f"Unhandled provider error (status {status_code}, code {code}): {raw_msg}"
