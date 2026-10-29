"""Implausible readings are accepted but flagged for the head."""

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.core.domain import (
    current_billing_period,
    detect_review_reason,
    previous_period,
)
from app.db.models import AuditLog, MeterReading
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal


class TestDetectReviewReason:
    def _detect(self, *, previous, usages, day, night):
        return detect_review_reason(
            previous=(D(previous[0]), D(previous[1])) if previous else None,
            recent_usages_kwh=[D(u) for u in usages],
            day_meter_value=D(day),
            night_meter_value=D(night),
        )

    def test_no_history_never_flags(self) -> None:
        assert (
            self._detect(previous=None, usages=[], day="99999", night="99999") is None
        )

    @pytest.mark.parametrize("day,night", [("99", "50"), ("100", "49")])
    def test_a_lower_value_on_either_meter_is_a_decrease(self, day, night) -> None:
        assert (
            self._detect(previous=("100", "50"), usages=[10], day=day, night=night)
            == "decrease"
        )

    def test_spike_needs_both_3x_the_median_and_the_50_kwh_floor(self) -> None:
        # Median 20 -> 3x is 60. 61 kWh used: a spike.
        assert (
            self._detect(previous=("0", "0"), usages=[10, 20, 30], day="61", night="0")
            == "spike"
        )
        # Exactly 3x the median is not over it.
        assert (
            self._detect(previous=("0", "0"), usages=[10, 20, 30], day="60", night="0")
            is None
        )
        # 40 kWh is over 3x a 10 kWh median but under the 50 kWh floor.
        assert (
            self._detect(previous=("0", "0"), usages=[10, 10, 10], day="40", night="0")
            is None
        )

    def test_works_with_fewer_than_three_months_of_history(self) -> None:
        assert (
            self._detect(previous=("0", "0"), usages=[10], day="200", night="0")
            == "spike"
        )
        assert (
            self._detect(previous=("0", "0"), usages=[], day="200", night="0") is None
        )

    def test_usage_sums_day_and_night(self) -> None:
        assert (
            self._detect(previous=("0", "0"), usages=[10], day="40", night="40")
            == "spike"
        )


def _household_with_history(session: Session, usages: list[int]):
    """Readings ending the period before the current one, each `usage` apart."""
    user = make_user(session)
    household = make_household(session, user_id=user.id)
    make_electricity_rate(session)
    period = previous_period(current_billing_period())
    periods = []
    for _ in range(len(usages) + 1):
        periods.append(period)
        period = previous_period(period)
    periods.reverse()
    total = 1000
    make_meter_reading(
        session,
        household_id=household.id,
        period=periods[0],
        day_meter_value=str(total),
    )
    for p, usage in zip(periods[1:], usages):
        total += usage
        make_meter_reading(
            session, household_id=household.id, period=p, day_meter_value=str(total)
        )
    return user, household, total


class TestSubmissionFlags:
    def _submit(self, client, day: int):
        return client.post(
            "/meter-readings",
            json={
                "period": current_billing_period(),
                "day_meter_value": str(day),
                "night_meter_value": "0",
            },
        )

    def test_a_decrease_is_accepted_and_flagged(self, client, session: Session) -> None:
        user, household, total = _household_with_history(session, [10, 10, 10])
        authenticate(client, user)

        response = self._submit(client, total - 5)

        assert response.status_code == 201
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == current_billing_period())
        ).one()
        assert (reading.needs_review, reading.review_reason) == (True, "decrease")

    def test_a_spike_is_accepted_and_flagged(self, client, session: Session) -> None:
        user, household, total = _household_with_history(session, [10, 10, 10])
        authenticate(client, user)

        response = self._submit(client, total + 500)

        assert response.status_code == 201
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == current_billing_period())
        ).one()
        assert (reading.needs_review, reading.review_reason) == (True, "spike")

    def _household_with_baseline(self, session: Session, day: str, night: str):
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_electricity_rate(session)
        make_meter_reading(
            session,
            household_id=household.id,
            period=previous_period(current_billing_period()),
            day_meter_value=day,
            night_meter_value=night,
            source="baseline",
        )
        return user

    def test_a_first_reading_against_a_zero_baseline_is_flagged(
        self, client, session: Session
    ) -> None:
        authenticate(client, self._household_with_baseline(session, "0", "0"))

        assert self._submit(client, 12345).status_code == 201
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == current_billing_period())
        ).one()
        assert (reading.needs_review, reading.review_reason) == (True, "zeroBaseline")

    def test_a_first_reading_against_a_real_baseline_is_not_flagged(
        self, client, session: Session
    ) -> None:
        authenticate(client, self._household_with_baseline(session, "1000", "0"))

        assert self._submit(client, 1012).status_code == 201
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == current_billing_period())
        ).one()
        assert reading.needs_review is False

    def test_a_normal_reading_is_not_flagged(self, client, session: Session) -> None:
        user, household, total = _household_with_history(session, [10, 10, 10])
        authenticate(client, user)

        assert self._submit(client, total + 12).status_code == 201
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == current_billing_period())
        ).one()
        assert reading.needs_review is False


class TestReviewEndpoint:
    def _flagged(self, session: Session):
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period="2024-01"
        )
        reading.needs_review = True
        reading.review_reason = "spike"
        session.flush()
        return reading

    def test_clearing_the_flag_is_audited(self, client, session: Session) -> None:
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)
        reading = self._flagged(session)

        response = client.post(
            f"/admin/readings/{reading.id}/review", json={"confirm": True}
        )

        assert response.status_code == 204
        session.refresh(reading)
        assert reading.needs_review is False
        assert reading.reviewed_by_user_id == admin.id
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "readingReviewed")
        ).one()
        assert (entry.entity_id, entry.period) == (reading.id, "2024-01")

    def test_unknown_reading_and_non_admin(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert (
            client.post("/admin/readings/1/review", json={"confirm": True}).status_code
            == 403
        )
        authenticate(client, make_user(session, is_admin=True))
        assert (
            client.post(
                "/admin/readings/999999/review", json={"confirm": True}
            ).status_code
            == 404
        )

    def test_dashboard_exposes_flag_and_previous_values(
        self, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        household = make_household(session, user_id=make_user(session).id)
        make_meter_reading(
            session,
            household_id=household.id,
            period=previous_period(current_billing_period()),
            day_meter_value="100",
        )
        current = make_meter_reading(
            session,
            household_id=household.id,
            period=current_billing_period(),
            day_meter_value="999",
        )
        current.needs_review = True
        current.review_reason = "spike"
        session.flush()

        body = client.get("/admin/dashboard").json()

        reading = next(h for h in body["households"] if h["id"] == household.id)[
            "reading"
        ]
        assert reading["needs_review"] is True
        assert D(reading["previous_day_meter_value"]) == D("100")
        assert D(reading["day_meter_value"]) == D("999")


class TestCloseWithFlags:
    def test_unreviewed_readings_block_close_unless_acknowledged(
        self, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        make_electricity_rate(session)
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period="2024-02"
        )
        reading.needs_review = True
        reading.review_reason = "decrease"
        session.flush()
        client.put(
            "/admin/periods/2024-02/bill",
            json={"day_kwh": "1", "night_kwh": "1", "total_uah": "0", "confirm": True},
        )

        overview = next(
            r for r in client.get("/admin/periods").json() if r["period"] == "2024-02"
        )
        blocked = client.post(
            "/admin/periods/2024-02/close",
            json={"confirm": True, "acknowledge_flags": False},
        )
        allowed = client.post(
            "/admin/periods/2024-02/close",
            json={"confirm": True, "acknowledge_flags": True},
        )

        assert overview["unreviewed_count"] == 1
        assert "periodHasUnreviewedReadings" in overview["blockers"]
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "periodHasUnreviewedReadings"
        assert allowed.status_code == 200
