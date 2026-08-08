"""Coverage for the meter-readings service and route layer (issue #18).

Household scoping, first-reading usage defaults, duplicate-period conflicts, and
period ordering are the behaviors a resident or the head would actually notice
going wrong, so they're covered at both the service layer (direct DB behavior)
and the route layer (HTTP status + stable error codes).
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlmodel import Session

from app.api.meter_readings.service import (
    HouseholdNotAccessibleError,
    NoHouseholdMembershipError,
    PeriodAlreadySubmittedError,
    get_owned_household_id,
    get_user_household_id,
    list_meter_readings,
    submit_meter_reading,
)
from app.api.meter_readings.service import _previous_period
from app.core.time import utc_now
from tests.factories import (
    authenticate,
    make_household,
    make_meter_reading,
    make_user,
)


class TestGetUserHouseholdId:
    def test_resolves_to_the_only_household(self, session: Session) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)

        assert get_user_household_id(session=session, user=user) == household.id

    def test_resolves_to_the_oldest_household_when_user_has_several(
        self, session: Session
    ) -> None:
        from datetime import datetime, timezone

        user = make_user(session)
        # Insert out of chronological order so a naive "first row" or "last
        # inserted" implementation would pick the wrong one.
        make_household(
            session,
            name="Newest Plot",
            user_id=user.id,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        oldest = make_household(
            session,
            name="Oldest Plot",
            user_id=user.id,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        make_household(
            session,
            name="Middle Plot",
            user_id=user.id,
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )

        assert get_user_household_id(session=session, user=user) == oldest.id

    def test_raises_when_user_has_no_household(self, session: Session) -> None:
        user = make_user(session)

        with pytest.raises(NoHouseholdMembershipError):
            get_user_household_id(session=session, user=user)


class TestGetOwnedHouseholdId:
    def test_returns_id_when_caller_owns_it(self, session: Session) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)

        assert (
            get_owned_household_id(session=session, user=user, household_id=household.id)
            == household.id
        )

    def test_raises_when_caller_does_not_own_it(self, session: Session) -> None:
        owner = make_user(session, email="owner@example.com")
        intruder = make_user(session, email="intruder@example.com")
        household = make_household(session, user_id=owner.id)

        with pytest.raises(HouseholdNotAccessibleError):
            get_owned_household_id(
                session=session, user=intruder, household_id=household.id
            )

    def test_raises_for_a_nonexistent_household_id(self, session: Session) -> None:
        user = make_user(session)

        with pytest.raises(HouseholdNotAccessibleError):
            get_owned_household_id(session=session, user=user, household_id=999999)


class TestSubmitMeterReading:
    def test_first_ever_reading_has_zero_usage(self, session: Session) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)

        reading = submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-07",
            day_meter_value=Decimal("3205.00"),
            night_meter_value=Decimal("1820.00"),
        )

        assert reading.day_usage_kwh == Decimal("0")
        assert reading.night_usage_kwh == Decimal("0")

    def test_usage_is_diffed_against_the_most_recent_prior_reading(
        self, session: Session
    ) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-06",
            day_meter_value="3000.00",
            night_meter_value="1700.00",
        )

        reading = submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-07",
            day_meter_value=Decimal("3205.50"),
            night_meter_value=Decimal("1820.25"),
        )

        assert reading.day_usage_kwh == Decimal("205.50")
        assert reading.night_usage_kwh == Decimal("120.25")

    def test_usage_diffs_against_the_latest_period_not_the_lowest_value(
        self, session: Session
    ) -> None:
        # Three unsorted prior readings: if the service picked "first row
        # inserted" or "smallest meter value" instead of "latest period", this
        # would diff against the wrong baseline and silently corrupt usage.
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-03",
            day_meter_value="2000.00",
            night_meter_value="1000.00",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-05",
            day_meter_value="2900.00",
            night_meter_value="1600.00",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-04",
            day_meter_value="2500.00",
            night_meter_value="1300.00",
        )

        reading = submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-06",
            day_meter_value=Decimal("3000.00"),
            night_meter_value=Decimal("1700.00"),
        )

        # Baseline must be period "2026-05" (lexicographically-latest YYYY-MM),
        # not "2026-04" (highest meter value) or "2026-03" (first inserted).
        assert reading.day_usage_kwh == Decimal("100.00")
        assert reading.night_usage_kwh == Decimal("100.00")

    def test_backfilling_an_older_period_diffs_against_the_immediately_prior_one(
        self, session: Session
    ) -> None:
        # A household already has readings for 2026-05 and 2026-07; backfilling
        # 2026-06 must diff against 2026-05 (immediately prior), not 2026-07
        # (globally latest) which would produce a nonsensical negative usage.
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-05",
            day_meter_value="2000.00",
            night_meter_value="1000.00",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-07",
            day_meter_value="3000.00",
            night_meter_value="1700.00",
        )

        reading = submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-06",
            day_meter_value=Decimal("2500.00"),
            night_meter_value=Decimal("1300.00"),
        )

        assert reading.day_usage_kwh == Decimal("500.00")
        assert reading.night_usage_kwh == Decimal("300.00")

    def test_a_reading_lower_than_the_prior_one_clamps_usage_to_zero(
        self, session: Session
    ) -> None:
        # Meter replacement, typo, or rollover: usage is clamped to zero,
        # matching both recalculation scripts (GREATEST/max(..., 0)).
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2026-06",
            day_meter_value="5000.00",
            night_meter_value="3000.00",
        )

        reading = submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-07",
            day_meter_value=Decimal("100.00"),
            night_meter_value=Decimal("50.00"),
        )

        assert reading.day_usage_kwh == Decimal("0")
        assert reading.night_usage_kwh == Decimal("0")

    def test_duplicate_period_for_the_same_household_is_rejected(
        self, session: Session
    ) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        submit_meter_reading(
            session=session,
            user=user,
            household_id=household.id,
            period="2026-07",
            day_meter_value=Decimal("100.00"),
            night_meter_value=Decimal("50.00"),
        )

        with pytest.raises(PeriodAlreadySubmittedError):
            submit_meter_reading(
                session=session,
                user=user,
                household_id=household.id,
                period="2026-07",
                day_meter_value=Decimal("110.00"),
                night_meter_value=Decimal("55.00"),
            )

    def test_same_period_is_allowed_for_different_households(
        self, session: Session
    ) -> None:
        user = make_user(session)
        household_a = make_household(session, name="Plot A", user_id=user.id)
        household_b = make_household(session, name="Plot B", user_id=user.id)
        submit_meter_reading(
            session=session,
            user=user,
            household_id=household_a.id,
            period="2026-07",
            day_meter_value=Decimal("100.00"),
            night_meter_value=Decimal("50.00"),
        )

        # Must not raise: the unique constraint is scoped to (household_id, period).
        reading_b = submit_meter_reading(
            session=session,
            user=user,
            household_id=household_b.id,
            period="2026-07",
            day_meter_value=Decimal("200.00"),
            night_meter_value=Decimal("90.00"),
        )

        assert reading_b.household_id == household_b.id


class TestListMeterReadings:
    def test_orders_by_period_descending_regardless_of_insertion_order(
        self, session: Session
    ) -> None:
        user = make_user(session)
        # Household created exactly at the earliest submitted period, so the
        # gap-fill range is limited to periods on/after 2025-11 and the
        # asserted list isn't polluted by unrelated synthetic entries.
        household = make_household(
            session,
            user_id=user.id,
            created_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
        )
        # Deliberately unsorted insertion, spanning a year boundary, so a bug
        # that orders by id/insertion-order instead of period sorts wrong.
        make_meter_reading(session, household_id=household.id, period="2025-11")
        make_meter_reading(session, household_id=household.id, period="2026-01")
        make_meter_reading(session, household_id=household.id, period="2025-12")

        readings = list_meter_readings(session=session, household_id=household.id)
        submitted = [r for r in readings if r.id is not None]

        assert [r.period for r in submitted] == ["2026-01", "2025-12", "2025-11"]
        # The whole list (real + synthetic gap entries) must still be sorted
        # descending by period, with no duplicates or out-of-range periods.
        periods = [r.period for r in readings]
        assert periods == sorted(periods, reverse=True)
        # The synthetic gap-fill walk starts at last month (the current
        # calendar month's submission window hasn't opened yet), so the
        # newest period present is whichever is greater: the newest real
        # submission or last month.
        last_month = _previous_period(utc_now().strftime("%Y-%m"))
        assert periods[0] == max("2026-01", last_month)
        assert periods[-1] == "2025-11"

    def test_returns_only_synthetic_gap_entries_for_a_household_with_none_submitted(
        self, session: Session
    ) -> None:
        # Household created two months before "now": with nothing submitted,
        # every period whose submission window has already opened must still
        # appear as a synthetic not-submitted entry rather than the household
        # vanishing from history entirely. The current calendar month's
        # window hasn't opened yet, so it must NOT appear as a gap entry.
        now = utc_now()
        created_month = (now.month - 2) if now.month > 2 else (now.month + 10)
        created_year = now.year if now.month > 2 else now.year - 1
        user = make_user(session)
        household = make_household(
            session,
            user_id=user.id,
            created_at=datetime(created_year, created_month, 1, tzinfo=timezone.utc),
        )

        readings = list_meter_readings(session=session, household_id=household.id)

        last_month = _previous_period(now.strftime("%Y-%m"))
        assert len(readings) == 2
        assert all(r.id is None for r in readings)
        assert all(r.day_meter_value is None for r in readings)
        assert all(r.night_meter_value is None for r in readings)
        assert all(r.submitted_at is None for r in readings)
        assert all(r.day_usage_kwh == Decimal("0") for r in readings)
        assert all(r.night_usage_kwh == Decimal("0") for r in readings)
        assert all(r.amount_charged_uah == Decimal("0") for r in readings)
        assert readings[0].period == last_month
        assert now.strftime("%Y-%m") not in [r.period for r in readings]

    def test_a_missed_month_appears_as_a_not_submitted_entry_alongside_real_ones(
        self, session: Session
    ) -> None:
        # Household created three months back; the resident submitted the
        # oldest and newest periods but skipped the middle one. The gap must
        # surface as a synthetic entry, not silently disappear from history.
        # "Newest" here is last calendar month, since a period for the
        # current calendar month can't legitimately be submitted yet (its
        # submission window only opens next month) and the synthetic
        # gap-fill walk no longer considers it.
        now = utc_now()

        def shift(period_offset: int) -> str:
            year, month = now.year, now.month - period_offset
            while month <= 0:
                month += 12
                year -= 1
            return f"{year}-{month:02d}"

        oldest_period = shift(3)
        gap_period = shift(2)
        newest_period = shift(1)
        oldest_year, oldest_month = (int(p) for p in oldest_period.split("-"))

        user = make_user(session)
        household = make_household(
            session,
            user_id=user.id,
            created_at=datetime(oldest_year, oldest_month, 1, tzinfo=timezone.utc),
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period=oldest_period,
            day_meter_value="1000.00",
            night_meter_value="500.00",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period=newest_period,
            day_meter_value="1200.00",
            night_meter_value="620.00",
            day_usage_kwh="200.00",
            night_usage_kwh="120.00",
        )

        readings = list_meter_readings(session=session, household_id=household.id)

        assert [r.period for r in readings] == [
            newest_period,
            gap_period,
            oldest_period,
        ]

        newest, gap, oldest = readings

        assert newest.id is not None
        assert newest.day_meter_value == Decimal("1200.00")
        assert newest.night_meter_value == Decimal("620.00")
        assert newest.day_usage_kwh == Decimal("200.00")
        assert newest.night_usage_kwh == Decimal("120.00")
        assert newest.submitted_at is not None

        assert gap.id is None
        assert gap.day_meter_value is None
        assert gap.night_meter_value is None
        assert gap.submitted_at is None
        assert gap.day_usage_kwh == Decimal("0")
        assert gap.night_usage_kwh == Decimal("0")
        assert gap.amount_charged_uah == Decimal("0")

        assert oldest.id is not None
        assert oldest.day_meter_value == Decimal("1000.00")
        assert oldest.night_meter_value == Decimal("500.00")
        assert oldest.submitted_at is not None


class TestRequireHouseholdIdRoute:
    """Exercises the `require_household_id` dependency through real HTTP calls."""

    def test_explicit_household_id_owned_by_caller_succeeds(
        self, client, session: Session
    ) -> None:
        user = make_user(session, email="owner-route@example.com")
        household = make_household(session, name="Owned Plot", user_id=user.id)
        authenticate(client, user)

        response = client.get(
            "/meter-readings", params={"household_id": household.id}
        )

        assert response.status_code == 200, response.text

    def test_explicit_household_id_not_owned_by_caller_is_forbidden(
        self, client, session: Session
    ) -> None:
        owner = make_user(session, email="owner2@example.com")
        intruder = make_user(session, email="intruder2@example.com")
        household = make_household(session, user_id=owner.id)
        authenticate(client, intruder)

        response = client.get(
            "/meter-readings", params={"household_id": household.id}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "householdNotAccessible"

    def test_no_household_id_param_and_user_has_no_households_is_not_found(
        self, client, session: Session
    ) -> None:
        user = make_user(session, email="homeless@example.com")
        authenticate(client, user)

        response = client.get("/meter-readings")

        assert response.status_code == 404
        assert response.json()["detail"] == "noHouseholdMembership"

    def test_no_household_id_param_resolves_via_get_user_household_id(
        self, client, session: Session
    ) -> None:
        now = utc_now()
        last_month = _previous_period(now.strftime("%Y-%m"))
        last_month_year, last_month_month = (int(p) for p in last_month.split("-"))
        user = make_user(session, email="resolver@example.com")
        # Household created in the same month as the sole submitted reading
        # (last month, the newest period a resident could actually have
        # submitted), so there are no gap periods to fill and the response
        # contains exactly that one real entry.
        household = make_household(
            session,
            name="Resolved Plot",
            user_id=user.id,
            created_at=datetime(
                last_month_year, last_month_month, 1, tzinfo=timezone.utc
            ),
        )
        period = last_month
        make_meter_reading(session, household_id=household.id, period=period)
        authenticate(client, user)

        response = client.get("/meter-readings")

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 1
        assert body[0]["household_id"] == household.id
        assert body[0]["period"] == period
        assert body[0]["id"] is not None


class TestMeterReadingRoutesHappyPath:
    def test_post_creates_a_reading_with_the_expected_response_shape(
        self, client, session: Session
    ) -> None:
        user = make_user(session, email="submitter@example.com")
        household = make_household(session, user_id=user.id)
        authenticate(client, user)

        response = client.post(
            "/meter-readings",
            params={"household_id": household.id},
            json={
                "period": "2026-07",
                "day_meter_value": "3205.00",
                "night_meter_value": "1820.00",
            },
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["period"] == "2026-07"
        assert body["household_id"] == household.id
        assert body["day_meter_value"] == "3205.00"
        assert body["night_meter_value"] == "1820.00"
        assert body["day_usage_kwh"] == "0.00"
        assert body["night_usage_kwh"] == "0.00"
        assert "id" in body
        assert "submitted_at" in body

    def test_post_duplicate_period_returns_409_with_stable_code(
        self, client, session: Session
    ) -> None:
        user = make_user(session, email="dup@example.com")
        household = make_household(session, user_id=user.id)
        authenticate(client, user)
        payload = {
            "period": "2026-07",
            "day_meter_value": "100.00",
            "night_meter_value": "50.00",
        }

        first = client.post(
            "/meter-readings", params={"household_id": household.id}, json=payload
        )
        assert first.status_code == 201, first.text

        second = client.post(
            "/meter-readings", params={"household_id": household.id}, json=payload
        )

        assert second.status_code == 409
        assert second.json()["detail"] == "periodAlreadySubmitted"

    def test_get_lists_readings_for_the_caller_household_only(
        self, client, session: Session
    ) -> None:
        now = utc_now()
        period = _previous_period(now.strftime("%Y-%m"))
        period_year, period_month = (int(p) for p in period.split("-"))
        created_at = datetime(period_year, period_month, 1, tzinfo=timezone.utc)
        user = make_user(session, email="lister@example.com")
        other_user = make_user(session, email="other@example.com")
        # Both households created in the same month as their reading (last
        # month, the newest period actually submittable) so each has exactly
        # one real entry and no gap-filled periods, keeping the "only mine"
        # assertion unambiguous.
        household = make_household(
            session, name="Mine", user_id=user.id, created_at=created_at
        )
        other_household = make_household(
            session, name="Not mine", user_id=other_user.id, created_at=created_at
        )
        make_meter_reading(session, household_id=household.id, period=period)
        make_meter_reading(session, household_id=other_household.id, period=period)
        authenticate(client, user)

        response = client.get(
            "/meter-readings", params={"household_id": household.id}
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 1
        assert body[0]["household_id"] == household.id
        assert body[0]["id"] is not None
