"""
Timezone-aware reporting period calculator for BS-6A Intelligence Automation.
Derives deterministic period boundaries respecting tenant timezone, frequency,
calendar month boundaries, leap years, and DST transitions.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
import zoneinfo


def get_tenant_local_datetime(
    reference_dt: Optional[datetime],
    tz_name: str = "America/New_York",
) -> datetime:
    """
    Normalizes a datetime into the tenant's local timezone.
    If no datetime provided, returns current time in tenant timezone.
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")

    if reference_dt is None:
        return datetime.now(tz)

    if reference_dt.tzinfo is None:
        # Naive datetime: assume tenant local time
        return reference_dt.replace(tzinfo=tz)

    # Timezone-aware: convert to tenant timezone
    return reference_dt.astimezone(tz)


def get_calendar_month_bounds(ref_date: date) -> Tuple[date, date]:
    """
    Returns (period_start, period_end) for the previous complete calendar month
    relative to ref_date.
    Example: 2026-11-01 -> (2026-10-01, 2026-10-31)
    Example: 2024-03-01 -> (2024-02-01, 2024-02-29) (Leap Year)
    Example: 2025-01-15 -> (2024-12-01, 2024-12-31) (Year Boundary)
    """
    first_of_this_month = ref_date.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return first_of_prev_month, last_of_prev_month


def get_rolling_window_bounds(ref_date: date, lookback_days: int = 30) -> Tuple[date, date]:
    """
    Returns (period_start, period_end) for a rolling window of lookback_days ending at ref_date.
    Example: ref_date=2026-10-22, lookback=30 -> (2026-09-22, 2026-10-22)
    """
    period_end = ref_date
    period_start = period_end - timedelta(days=lookback_days)
    return period_start, period_end


def get_calendar_week_bounds(ref_date: date) -> Tuple[date, date]:
    """
    Returns (period_start, period_end) for the previous full calendar week (Monday to Sunday).
    """
    # weekday: 0=Monday, 6=Sunday
    days_since_monday = ref_date.weekday()
    this_monday = ref_date - timedelta(days=days_since_monday)
    prev_sunday = this_monday - timedelta(days=1)
    prev_monday = prev_sunday - timedelta(days=6)
    return prev_monday, prev_sunday


def calculate_reporting_period(
    tz_name: str = "America/New_York",
    frequency: str = "MONTHLY",
    reference_datetime: Optional[datetime] = None,
    lookback_days: int = 30,
    period_type: str = "CALENDAR_MONTH",
) -> Tuple[date, date]:
    """
    Derives deterministic period_start and period_end based on:
    - tenant timezone
    - frequency (MONTHLY, WEEKLY)
    - reference timestamp (converted to tenant timezone)
    - period_type ('CALENDAR_MONTH' or 'ROLLING')
    """
    local_dt = get_tenant_local_datetime(reference_datetime, tz_name=tz_name)
    local_date = local_dt.date()

    if frequency.upper() == "WEEKLY":
        return get_calendar_week_bounds(local_date)

    # Frequency MONTHLY
    if period_type.upper() == "ROLLING":
        return get_rolling_window_bounds(local_date, lookback_days=lookback_days)

    # Default: CALENDAR_MONTH
    return get_calendar_month_bounds(local_date)
