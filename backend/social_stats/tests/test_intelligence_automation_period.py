"""
Unit Tests for BS-6A Reporting Period Calculator (Test Matrix AP).
Tests calendar months, rolling windows, weekly periods, month boundaries,
leap years, year transitions, and DST boundaries.
"""
from datetime import date, datetime, timezone
import zoneinfo
from django.test import SimpleTestCase

from social_stats.analytics.automation.period import (
    calculate_reporting_period,
    get_calendar_month_bounds,
    get_calendar_week_bounds,
    get_rolling_window_bounds,
    get_tenant_local_datetime,
)


class IntelligenceAutomationPeriodTests(SimpleTestCase):
    def test_calendar_month_standard(self):
        """Reference on 1st of month returns entire previous month."""
        # Reference: 2026-11-01 -> October 2026
        ref = date(2026, 11, 1)
        p_start, p_end = get_calendar_month_bounds(ref)
        self.assertEqual(p_start, date(2026, 10, 1))
        self.assertEqual(p_end, date(2026, 10, 31))

    def test_calendar_month_year_boundary(self):
        """Reference in January returns full December of previous year."""
        ref = date(2025, 1, 15)
        p_start, p_end = get_calendar_month_bounds(ref)
        self.assertEqual(p_start, date(2024, 12, 1))
        self.assertEqual(p_end, date(2024, 12, 31))

    def test_calendar_month_leap_year(self):
        """February in leap year (2024) ends on 29th; in non-leap year (2025) ends on 28th."""
        # Leap year 2024
        ref_leap = date(2024, 3, 1)
        p_start_leap, p_end_leap = get_calendar_month_bounds(ref_leap)
        self.assertEqual(p_start_leap, date(2024, 2, 1))
        self.assertEqual(p_end_leap, date(2024, 2, 29))

        # Non-leap year 2025
        ref_non_leap = date(2025, 3, 1)
        p_start_nl, p_end_nl = get_calendar_month_bounds(ref_non_leap)
        self.assertEqual(p_start_nl, date(2025, 2, 1))
        self.assertEqual(p_end_nl, date(2025, 2, 28))

    def test_rolling_window_bounds(self):
        """Rolling window of 30 days ending on reference date."""
        ref = date(2026, 10, 22)
        p_start, p_end = get_rolling_window_bounds(ref, lookback_days=30)
        self.assertEqual(p_end, date(2026, 10, 22))
        self.assertEqual(p_start, date(2026, 9, 22))

    def test_calendar_week_bounds(self):
        """Weekly frequency returns previous full calendar week (Monday to Sunday)."""
        # 2026-10-28 is Wednesday. Previous full week was 2026-10-19 (Mon) to 2026-10-25 (Sun).
        ref = date(2026, 10, 28)
        p_start, p_end = get_calendar_week_bounds(ref)
        self.assertEqual(p_start, date(2026, 10, 19))
        self.assertEqual(p_end, date(2026, 10, 25))
        self.assertEqual(p_start.weekday(), 0)  # Monday
        self.assertEqual(p_end.weekday(), 6)    # Sunday

    def test_tenant_timezone_awareness_and_dst(self):
        """UTC timestamp converts to tenant local date correctly across DST boundary."""
        # In America/New_York, EDT is UTC-4, EST is UTC-5
        # Nov 1, 2026 03:30 UTC is Oct 31, 2026 23:30 EDT
        utc_dt = datetime(2026, 11, 1, 3, 30, tzinfo=timezone.utc)
        ny_dt = get_tenant_local_datetime(utc_dt, tz_name="America/New_York")
        self.assertEqual(ny_dt.date(), date(2026, 10, 31))

        # Nov 1, 2026 05:00 UTC is Nov 1, 2026 01:00 EDT (prior to 2am fallback)
        utc_dt2 = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
        ny_dt2 = get_tenant_local_datetime(utc_dt2, tz_name="America/New_York")
        self.assertEqual(ny_dt2.date(), date(2026, 11, 1))

    def test_calculate_reporting_period_monthly_integration(self):
        """calculate_reporting_period integrates timezone and monthly defaults."""
        utc_dt = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        p_start, p_end = calculate_reporting_period(
            tz_name="America/New_York",
            frequency="MONTHLY",
            reference_datetime=utc_dt,
            period_type="CALENDAR_MONTH",
        )
        self.assertEqual(p_start, date(2026, 10, 1))
        self.assertEqual(p_end, date(2026, 10, 31))
