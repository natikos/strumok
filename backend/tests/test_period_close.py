"""Closing a billing period: atomic ledger writes, one-way status, and the
submission lock."""

from decimal import Decimal

from sqlmodel import Session, select

from app.core.domain import current_billing_period
from app.db.models import AuditLog, BillingPeriod, HouseholdCharge
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal
PAST = "2024-02"
BODY = {"confirm": True, "acknowledge_flags": False}


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


class TestClosePeriod:
    def test_close_writes_one_charge_per_reading_and_audits(
        self, client, session: Session
    ) -> None:
        admin = _admin(client, session)
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2024-01",
            day_meter_value="100",
            night_meter_value="50",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period=PAST,
            day_meter_value="130",
            night_meter_value="60",
        )

        response = client.post(f"/admin/periods/{PAST}/close", json=BODY)

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "closed"
        (charge,) = session.exec(
            select(HouseholdCharge).where(HouseholdCharge.period == PAST)
        ).all()
        assert charge.total_uah == D("70.00")  # 30 kWh × 2 + 10 kWh × 1
        assert charge.owner_user_id == owner.id
        row = session.get(BillingPeriod, PAST)
        assert (row.status, row.closed_by_user_id) == ("closed", admin.id)
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "periodClosed")
        ).one()
        assert entry.period == PAST
        assert entry.after["households_charged"] == 1

    def test_closing_twice_is_a_conflict_and_adds_no_charges(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        make_electricity_rate(session)
        household = make_household(session)
        make_meter_reading(session, household_id=household.id, period=PAST)

        first = client.post(f"/admin/periods/{PAST}/close", json=BODY)
        second = client.post(f"/admin/periods/{PAST}/close", json=BODY)

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["detail"] == "periodAlreadyClosed"
        assert len(session.exec(select(HouseholdCharge)).all()) == 1

    def test_without_a_rate_nothing_is_written_and_the_period_stays_open(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        make_meter_reading(session, household_id=household.id, period=PAST)

        response = client.post(f"/admin/periods/{PAST}/close", json=BODY)

        assert response.status_code == 409
        assert response.json()["detail"] == "noRateConfigured"
        assert session.exec(select(HouseholdCharge)).all() == []
        assert (
            session.exec(
                select(AuditLog).where(AuditLog.action == "periodClosed")
            ).all()
            == []
        )

    def test_cannot_close_a_period_whose_window_is_still_open(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        make_electricity_rate(session)

        response = client.post("/admin/periods/2999-01/close", json=BODY)

        assert response.status_code == 409
        assert response.json()["detail"] == "periodNotEnded"

    def test_requires_confirm_and_admin(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert client.post(f"/admin/periods/{PAST}/close", json=BODY).status_code == 403
        authenticate(client, make_user(session, is_admin=True))
        assert (
            client.post(
                f"/admin/periods/{PAST}/close", json={"confirm": False}
            ).status_code
            == 422
        )


class TestSubmissionAgainstClosedPeriod:
    def test_submitting_for_a_closed_period_returns_period_closed(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_electricity_rate(session)
        period = current_billing_period()
        session.add(BillingPeriod(period=period, status="closed"))
        session.flush()
        authenticate(client, user)

        response = client.post(
            "/meter-readings",
            json={"period": period, "day_meter_value": "10", "night_meter_value": "5"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "periodClosed"
        assert household.id  # unused otherwise; the household exists for scoping

    def test_open_period_still_accepts_a_submission(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        make_household(session, user_id=user.id)
        make_electricity_rate(session)
        authenticate(client, user)

        response = client.post(
            "/meter-readings",
            json={
                "period": current_billing_period(),
                "day_meter_value": "10",
                "night_meter_value": "5",
            },
        )

        assert response.status_code == 201


class TestPeriodOverview:
    def test_lists_current_and_closed_periods_with_blockers(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        session.add(BillingPeriod(period=PAST, status="closed"))
        session.flush()

        body = client.get("/admin/periods").json()

        by_period = {row["period"]: row for row in body}
        assert by_period[PAST]["status"] == "closed"
        current = by_period[current_billing_period()]
        assert current["status"] == "open"
        assert "noRateConfigured" in current["blockers"]
        assert body[0]["period"] == max(by_period)
