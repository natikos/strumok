"""Coverage for `get_effective_rate`: picking the rate in force for a period.

Admins add a new row whenever the rate changes and never edit old ones, so the
correct row for a period is "the greatest `effective_from` that is still `<=
period`" -- never the most recently created row, and never simply the first or
last row in the table.
"""

from decimal import Decimal

import pytest
from sqlmodel import Session

from app.api.electricity_rates.service import NoRateConfiguredError, get_effective_rate
from tests.factories import make_electricity_rate


class TestGetEffectiveRate:
    def test_a_rate_effective_in_the_future_is_not_picked_even_if_newest_row(
        self, session: Session
    ) -> None:
        # Inserted after the applicable rate, so a bug that ordered by
        # insertion/id instead of effective_from would wrongly pick this one.
        make_electricity_rate(
            session,
            day_rate_uah="4.00",
            night_rate_uah="2.00",
            effective_from="2026-01",
        )
        make_electricity_rate(
            session,
            day_rate_uah="9.00",
            night_rate_uah="7.00",
            effective_from="2026-12",
        )

        rate = get_effective_rate(session=session, period="2026-06")

        assert rate.day_rate_uah == Decimal("4.00")
        assert rate.night_rate_uah == Decimal("2.00")

    def test_picks_the_most_recent_applicable_rate_among_several(
        self, session: Session
    ) -> None:
        # Three unsorted rates spanning a year boundary: the correct answer is
        # the latest one still <= the period, not the first or last created.
        make_electricity_rate(
            session,
            day_rate_uah="5.00",
            night_rate_uah="2.50",
            effective_from="2025-09",
        )
        make_electricity_rate(
            session,
            day_rate_uah="3.00",
            night_rate_uah="1.50",
            effective_from="2025-01",
        )
        make_electricity_rate(
            session,
            day_rate_uah="6.00",
            night_rate_uah="3.00",
            effective_from="2026-02",
        )

        rate = get_effective_rate(session=session, period="2026-01")

        assert rate.effective_from == "2025-09"
        assert rate.day_rate_uah == Decimal("5.00")
        assert rate.night_rate_uah == Decimal("2.50")

    def test_a_rate_effective_exactly_in_the_period_is_picked(
        self, session: Session
    ) -> None:
        make_electricity_rate(
            session,
            day_rate_uah="4.00",
            night_rate_uah="2.00",
            effective_from="2025-01",
        )
        make_electricity_rate(
            session,
            day_rate_uah="6.50",
            night_rate_uah="3.25",
            effective_from="2026-03",
        )

        rate = get_effective_rate(session=session, period="2026-03")

        assert rate.effective_from == "2026-03"
        assert rate.day_rate_uah == Decimal("6.50")

    def test_raises_when_no_rate_exists_at_all(self, session: Session) -> None:
        with pytest.raises(NoRateConfiguredError):
            get_effective_rate(session=session, period="2026-06")

    def test_raises_when_every_configured_rate_is_in_the_future(
        self, session: Session
    ) -> None:
        make_electricity_rate(session, effective_from="2027-01")
        make_electricity_rate(session, effective_from="2027-06")

        with pytest.raises(NoRateConfiguredError):
            get_effective_rate(session=session, period="2026-12")
