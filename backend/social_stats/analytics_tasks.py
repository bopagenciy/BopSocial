"""
Celery background tasks for BS-4C Provider Analytics Sync.
Operates on non-critical analytics queue, fully isolated from publishing critical path.
"""
import logging
from celery import shared_task
from django.utils import timezone

from .analytics.sync_service import sync_facebook_analytics, sync_instagram_analytics
from .analytics.exceptions import AnalyticsRateLimitedError, AnalyticsAuthExpiredError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, queue="analytics")
def sync_client_facebook_analytics_v2(self, client_id: int, days: int = 30):
    """
    Celery task to execute controlled Facebook analytics sync.
    Handles rate-limit retries gracefully without blocking publishing workflows.
    """
    logger.info(f"Starting Facebook analytics sync v2 for client_id={client_id}")
    try:
        result = sync_facebook_analytics(client_id=client_id, days=days)
        logger.info(
            f"Facebook analytics sync v2 completed for client_id={client_id}: "
            f"status={result.status}, ingested={result.records_ingested}, updated={result.records_updated}"
        )
        return {
            "status": result.status,
            "records_ingested": result.records_ingested,
            "records_updated": result.records_updated,
            "warnings": result.warnings,
            "errors": result.errors,
            "capability_mode": result.capability_mode,
        }
    except AnalyticsRateLimitedError as exc:
        logger.warning(f"Facebook analytics sync rate limited for client_id={client_id}. Backing off: {exc}")
        countdown = 300 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    except AnalyticsAuthExpiredError as exc:
        logger.error(f"Facebook token expired for client_id={client_id}. Ceasing sync: {exc}")
        return {"status": "failed", "error": "AUTH_EXPIRED", "detail": str(exc)}
    except Exception as exc:
        logger.error(f"Facebook analytics sync unexpected error for client_id={client_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, queue="analytics")
def sync_client_instagram_analytics_v2(self, client_id: int, days: int = 30):
    """
    Celery task to execute controlled Instagram analytics sync.
    Supports both FULL and PARTIAL capability modes without worker blocking.
    """
    logger.info(f"Starting Instagram analytics sync v2 for client_id={client_id}")
    try:
        result = sync_instagram_analytics(client_id=client_id, days=days)
        logger.info(
            f"Instagram analytics sync v2 completed for client_id={client_id}: "
            f"status={result.status}, mode={result.capability_mode}, ingested={result.records_ingested}, updated={result.records_updated}"
        )
        return {
            "status": result.status,
            "records_ingested": result.records_ingested,
            "records_updated": result.records_updated,
            "warnings": result.warnings,
            "errors": result.errors,
            "capability_mode": result.capability_mode,
        }
    except AnalyticsRateLimitedError as exc:
        logger.warning(f"Instagram analytics sync rate limited for client_id={client_id}. Backing off: {exc}")
        countdown = 300 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    except AnalyticsAuthExpiredError as exc:
        logger.error(f"Instagram token expired for client_id={client_id}. Ceasing sync: {exc}")
        return {"status": "failed", "error": "AUTH_EXPIRED", "detail": str(exc)}
    except Exception as exc:
        logger.error(f"Instagram analytics sync unexpected error for client_id={client_id}: {exc}")
        raise self.retry(exc=exc)
