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


def calculate_next_due_datetime(
    config: "IntelligenceAutomationConfig",
    reference_datetime: Optional[datetime] = None,
) -> datetime:
    """
    Computes the upcoming due datetime for a tenant configuration in its local timezone.
    Handles MONTHLY (reporting_day 1-28, reporting_hour 0-23) and WEEKLY (0=Mon..6=Sun).
    Safely resolves DST transitions (ambiguous and non-existent hours) deterministically.
    """
    tz_name = getattr(config, "timezone", "America/New_York") or "America/New_York"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")

    local_now = get_tenant_local_datetime(reference_datetime, tz_name=tz_name)
    rep_day = getattr(config, "reporting_day", 1) or 1
    rep_hour = getattr(config, "reporting_hour", 2) or 0
    freq = getattr(config, "reporting_frequency", "MONTHLY") or "MONTHLY"

    if freq.upper() == "MONTHLY":
        # Candidate 1: this month
        try:
            cand = datetime(local_now.year, local_now.month, rep_day, rep_hour, 0, 0, fold=0, tzinfo=tz)
        except ValueError:
            # e.g. Feb 30 -> fallback to last day of month
            first_next = (datetime(local_now.year, local_now.month, 1, tzinfo=tz) + timedelta(days=32)).replace(day=1)
            last_day = (first_next - timedelta(days=1)).day
            cand = datetime(local_now.year, local_now.month, min(rep_day, last_day), rep_hour, 0, 0, fold=0, tzinfo=tz)

        if cand > local_now:
            return cand

        # Candidate 2: next month
        year = local_now.year + (1 if local_now.month == 12 else 0)
        month = 1 if local_now.month == 12 else (local_now.month + 1)
        try:
            cand_next = datetime(year, month, rep_day, rep_hour, 0, 0, fold=0, tzinfo=tz)
        except ValueError:
            first_after = (datetime(year, month, 1, tzinfo=tz) + timedelta(days=32)).replace(day=1)
            last_day = (first_after - timedelta(days=1)).day
            cand_next = datetime(year, month, min(rep_day, last_day), rep_hour, 0, 0, fold=0, tzinfo=tz)

        return cand_next

    elif freq.upper() == "WEEKLY":
        # rep_day: 0=Mon .. 6=Sun
        days_ahead = (rep_day - local_now.weekday()) % 7
        cand = (local_now + timedelta(days=days_ahead)).replace(hour=rep_hour, minute=0, second=0, microsecond=0)
        if cand <= local_now:
            cand += timedelta(days=7)
        return cand

    # Default fallback
    return local_now + timedelta(days=30)


def is_tenant_due(
    config: "IntelligenceAutomationConfig",
    reference_datetime: Optional[datetime] = None,
) -> Tuple[bool, date, date, str]:
    """
    Evaluates whether a tenant is currently due for automated pipeline execution.
    Deterministic and immune to exact-hour polling gaps (supports missed-tick recovery).
    
    Returns:
        (is_due, target_period_start, target_period_end, reason)
    """
    if not config.enabled:
        return False, date.today(), date.today(), "AUTOMATION_CONFIG_DISABLED"

    client = config.client
    if not client.is_active:
        return False, date.today(), date.today(), "CLIENT_INACTIVE"

    tz_name = config.timezone or "America/New_York"
    local_now = get_tenant_local_datetime(reference_datetime, tz_name=tz_name)
    rep_day = config.reporting_day or 1
    rep_hour = config.reporting_hour or 2
    freq = (config.reporting_frequency or "MONTHLY").upper()

    if freq == "MONTHLY":
        # A scheduled monthly run evaluates the calendar month immediately preceding the execution month.
        # Specifically, for reporting period M-1, the execution becomes due once local time reaches
        # month M, reporting_day at reporting_hour.
        # Example: to evaluate October (2026-10-01 to 2026-10-31), the trigger threshold is:
        # 2026-11-01 02:00:00 local time.
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = zoneinfo.ZoneInfo("America/New_York")

        # Threshold for evaluating previous calendar month (relative to local_now.date()):
        try:
            current_threshold = datetime(local_now.year, local_now.month, rep_day, rep_hour, 0, 0, fold=0, tzinfo=tz)
        except ValueError:
            first_next = (datetime(local_now.year, local_now.month, 1, tzinfo=tz) + timedelta(days=32)).replace(day=1)
            last_day = (first_next - timedelta(days=1)).day
            current_threshold = datetime(local_now.year, local_now.month, min(rep_day, last_day), rep_hour, 0, 0, fold=0, tzinfo=tz)

        if local_now < current_threshold:
            # We have not yet reached the reporting window for this month
            return False, date.today(), date.today(), f"NOT_DUE (threshold: {current_threshold.isoformat()})"

        p_start, p_end = calculate_reporting_period(
            tz_name=tz_name,
            frequency=freq,
            reference_datetime=current_threshold,
            lookback_days=config.lookback_days,
            period_type="CALENDAR_MONTH",
        )

        return True, p_start, p_end, "DUE"

    elif freq == "WEEKLY":
        days_since_monday = local_now.weekday()
        if days_since_monday < rep_day or (days_since_monday == rep_day and local_now.hour < rep_hour):
            return False, date.today(), date.today(), "NOT_DUE_WEEKLY"

        p_start, p_end = get_calendar_week_bounds(local_now.date())
        return True, p_start, p_end, "DUE"

    return False, date.today(), date.today(), "UNKNOWN_FREQUENCY"

