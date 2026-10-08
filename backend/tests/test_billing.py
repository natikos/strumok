"""Coverage for Kyiv-local billing period computation (issue #141).

`current_billing_period` used to derive the "current month" from server UTC.
Around midnight Kyiv time on the 1st that disagrees with the Kyiv calendar
date a resident is actually looking at -- the tests below construct explicit
tz-aware instants (including ones whose UTC calendar day differs from their
Kyiv calendar day) to pin the Kyiv-based behavior at exactly those boundaries.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.domain import current_billing_period

KYIV = ZoneInfo("Europe/Kyiv")


class TestCurrentBillingPeriodBoundaries:
    def test_first_instant_of_day_1_kyiv_reports_the_prior_month(self) -> None:
        now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=KYIV)

        assert current_billing_period(now) == "2026-06"

    def test_last_instant_of_the_prior_month_kyiv_still_reports_two_months_back(
        self,
    ) -> None:
        now = datetime(2026, 6, 30, 23, 59, 59, tzinfo=KYIV)

        assert current_billing_period(now) == "2026-05"

    def test_a_utc_instant_already_on_day_1_kyiv_uses_the_kyiv_date(self) -> None:
        # 2026-06-30 22:00 UTC is 2026-07-01 01:00 in Kyiv (EEST, +3). Code
        # using the UTC calendar date would still report "2026-05"; this is
        # the actual bug behind issue #141.
        now = datetime(2026, 6, 30, 22, 0, 0, tzinfo=timezone.utc)

        assert now.astimezone(KYIV).day == 1
        assert current_billing_period(now) == "2026-06"

    def test_a_utc_instant_already_in_the_next_kyiv_year_rolls_the_period_back_a_year(
        self,
    ) -> None:
        # 2025-12-31 22:30 UTC is 2026-01-01 00:30 in Kyiv (EET, +2).
        now = datetime(2025, 12, 31, 22, 30, 0, tzinfo=timezone.utc)

        assert current_billing_period(now) == "2025-12"


class TestKyivTimezoneDatabase:
    def test_kyiv_utcoffset_is_plus_2_in_winter_and_plus_3_in_summer(self) -> None:
        # Pins that zoneinfo applies the seasonal offset the tests above rely on.
        winter = datetime(2026, 1, 15, tzinfo=KYIV)
        summer = datetime(2026, 7, 15, tzinfo=KYIV)

        assert winter.utcoffset() == timedelta(hours=2)
        assert summer.utcoffset() == timedelta(hours=3)
