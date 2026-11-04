"""
Measurable data freshness contract and evaluation engine for BS-6A Intelligence Automation.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    SyncLog,
)
from .constants import FreshnessCode, DEFAULT_FRESHNESS_HOURS


@dataclass
class FreshnessResult:
    code: FreshnessCode
    is_fresh: bool
    latest_sync_at: Optional[datetime]
    data_age_hours: Optional[float]
    threshold_hours: int
    latest_snapshot_date: Optional[date]
    latest_rollup_date: Optional[date]
    active_credential_count: int
    expired_credential_count: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value if isinstance(self.code, FreshnessCode) else str(self.code),
            "is_fresh": self.is_fresh,
            "latest_sync_at": self.latest_sync_at.isoformat() if self.latest_sync_at else None,
            "data_age_hours": round(self.data_age_hours, 2) if self.data_age_hours is not None else None,
            "threshold_hours": self.threshold_hours,
            "latest_snapshot_date": self.latest_snapshot_date.isoformat() if self.latest_snapshot_date else None,
            "latest_rollup_date": self.latest_rollup_date.isoformat() if self.latest_rollup_date else None,
            "active_credential_count": self.active_credential_count,
            "expired_credential_count": self.expired_credential_count,
            "details": self.details,
        }


def evaluate_tenant_freshness(
    client_id: int,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    max_staleness_hours: int = DEFAULT_FRESHNESS_HOURS,
    now: Optional[datetime] = None,
) -> FreshnessResult:
    """
    Evaluates measurable data freshness for a tenant across:
    1. Active provider platform credentials (connected, unexpired)
    2. Latest SyncLog completed
    3. Latest SocialMetricSnapshot date
    4. Latest SocialMetricRollup date
    """
    current_time = now or timezone.now()

    # 1. Credential status
    creds = list(PlatformCredential.objects.filter(client_id=client_id, is_active=True).values("id", "platform", "is_active", "expires_at"))
    active_count = len(creds)
    expired_count = sum(
        1 for c in creds
        if c.get("expires_at") and current_time >= (c["expires_at"] - timedelta(minutes=10))
    )

    if active_count == 0:
        return FreshnessResult(
            code=FreshnessCode.UNKNOWN,
            is_fresh=False,
            latest_sync_at=None,
            data_age_hours=None,
            threshold_hours=max_staleness_hours,
            latest_snapshot_date=None,
            latest_rollup_date=None,
            active_credential_count=0,
            expired_credential_count=0,
            details={"reason": "NO_ACTIVE_CREDENTIALS"},
        )

    # 2. Latest qualifying CURRENT SyncLog (BS-6D.0D Provenance Contract)
    # A historical backfill must NOT qualify as current operational freshness evidence.
    # A qualifying sync MUST:
    #   a) have status in ['success', 'partial']
    #   b) have sync_scope == 'CURRENT'
    #   c) if period_end is specified, it must not be a purely historical period
    qualifying_syncs = (
        SyncLog.objects.filter(
            client_id=client_id,
            status__in=["success", "partial"],
            sync_scope="CURRENT",
        )
        .order_by("-finished_at")
    )

    latest_sync = None
    for s in qualifying_syncs:
        # If period_end is bounded and older than 2 days before finished_at, it's historical regardless of label
        if s.period_end and s.finished_at and s.period_end < (s.finished_at.date() - timedelta(days=2)):
            continue
        latest_sync = s
        break

    latest_sync_at = latest_sync.finished_at if latest_sync else None

    # 3. Latest Snapshot date
    snap_qs = SocialMetricSnapshot.objects.filter(client_id=client_id)
    if period_start and period_end:
        snap_qs = snap_qs.filter(bucket_timestamp__date__gte=period_start, bucket_timestamp__date__lte=period_end)
    latest_snap = snap_qs.order_by("-bucket_timestamp").first()
    latest_snapshot_date = latest_snap.bucket_timestamp.date() if latest_snap else None

    # 4. Latest Rollup date
    rollup_qs = SocialMetricRollup.objects.filter(client_id=client_id)
    if period_start and period_end:
        rollup_qs = rollup_qs.filter(period_start__gte=period_start, period_start__lte=period_end)
    latest_rollup = rollup_qs.order_by("-period_start").first()
    latest_rollup_date = latest_rollup.period_start if latest_rollup else None

    # Determine freshness code
    if not latest_sync_at and not latest_snapshot_date:
        return FreshnessResult(
            code=FreshnessCode.MISSING,
            is_fresh=False,
            latest_sync_at=None,
            data_age_hours=None,
            threshold_hours=max_staleness_hours,
            latest_snapshot_date=None,
            latest_rollup_date=latest_rollup_date,
            active_credential_count=active_count,
            expired_credential_count=expired_count,
            details={"reason": "NO_SYNC_OR_SNAPSHOT_FOUND"},
        )

    # If all credentials are expired
    if expired_count == active_count:
        age_hours = (current_time - latest_sync_at).total_seconds() / 3600.0 if latest_sync_at else None
        return FreshnessResult(
            code=FreshnessCode.UNKNOWN,
            is_fresh=False,
            latest_sync_at=latest_sync_at,
            data_age_hours=age_hours,
            threshold_hours=max_staleness_hours,
            latest_snapshot_date=latest_snapshot_date,
            latest_rollup_date=latest_rollup_date,
            active_credential_count=active_count,
            expired_credential_count=expired_count,
            details={"reason": "ALL_CREDENTIALS_EXPIRED"},
        )

    if latest_sync_at:
        age_hours = max(0.0, (current_time - latest_sync_at).total_seconds() / 3600.0)
    else:
        # Synthesize age from latest snapshot date
        snap_dt = timezone.make_aware(
            datetime.combine(latest_snapshot_date, datetime.min.time()),
            timezone.get_current_timezone(),
        )
        age_hours = max(0.0, (current_time - snap_dt).total_seconds() / 3600.0)

    if age_hours <= max_staleness_hours:
        code = FreshnessCode.FRESH
        is_fresh = True
    else:
        code = FreshnessCode.STALE
        is_fresh = False

    return FreshnessResult(
        code=code,
        is_fresh=is_fresh,
        latest_sync_at=latest_sync_at,
        data_age_hours=age_hours,
        threshold_hours=max_staleness_hours,
        latest_snapshot_date=latest_snapshot_date,
        latest_rollup_date=latest_rollup_date,
        active_credential_count=active_count,
        expired_credential_count=expired_count,
        details={
            "sync_platform": latest_sync.platform if latest_sync else None,
            "sync_status": latest_sync.status if latest_sync else None,
            "qualifying_sync_id": latest_sync.id if latest_sync else None,
            "qualifying_sync_scope": latest_sync.sync_scope if latest_sync else None,
        },
    )
