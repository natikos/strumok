"""The head can enter, correct and void readings on a household's behalf."""

from decimal import Decimal

from sqlmodel import Session, select

from app.core.domain import current_billing_period, previous_period
from app.db.models import AuditLog, BillingPeriod, MeterReading
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal
CURRENT = current_billing_period()
PREVIOUS = previous_period(CURRENT)
EARLIER = previous_period(PREVIOUS)


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _post(client, household_id: int, **overrides):
    body = {
        "period": PREVIOUS,
        "day_meter_value": "120",
        "night_meter_value": "0",
        "reason": "phoned in",
    }
    body.update(overrides)
    return client.post(f"/admin/households/{household_id}/readings", json=body)


class TestSubmitOnBehalf:
    def test_an_unowned_household_gets_a_reading_with_a_visible_note(
        self, client, session: Session
    ) -> None:
        admin = _admin(client, session)
        make_electricity_rate(session)
        household = make_household(session)  # nobody owns it

        response = _post(client, household.id)

        assert response.status_code == 201, response.text
        reading = session.exec(select(MeterReading)).one()
        assert (reading.source, reading.submitted_by_user_id) == ("admin", admin.id)
        assert reading.correction_reason == "phoned in"
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "readingSubmittedOnBehalf")
        ).one()
        assert entry.reason == "phoned in"
        assert (entry.household_id, entry.period) == (household.id, PREVIOUS)

    def test_a_resident_sees_the_correction_note_in_their_history(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        make_electricity_rate(session)
        _admin(client, session)
        _post(client, household.id)
        authenticate(client, owner)

        rows = client.get("/meter-readings").json()

        row = next(r for r in rows if r["period"] == PREVIOUS)
        assert row["source"] == "admin"
        assert row["correction_reason"] == "phoned in"
        assert row["corrected_at"] is not None

    def test_inserting_an_earlier_period_changes_the_next_periods_derived_usage(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        make_electricity_rate(session, day_rate_uah="1", night_rate_uah="1")
        make_meter_reading(
            session, household_id=household.id, period=EARLIER, day_meter_value="100"
        )
        make_meter_reading(
            session, household_id=household.id, period=CURRENT, day_meter_value="150"
        )
        authenticate(client, owner)
        before = client.get("/billing/statements").json()[0]

        authenticate(client, make_user(session, is_admin=True))
        assert _post(client, household.id, day_meter_value="120").status_code == 201
        authenticate(client, owner)
        after = client.get("/billing/statements").json()[0]

        assert (D(before["day_usage_kwh"]), D(after["day_usage_kwh"])) == (
            D("50"),
            D("30"),
        )

    def test_validation_and_conflicts(self, client, session: Session) -> None:
        _admin(client, session)
        household = make_household(session)

        assert _post(client, household.id, reason="").status_code == 422
        assert _post(client, household.id, reason="   ").status_code == 422
        assert _post(client, 999999).status_code == 404
        assert (
            _post(client, household.id, period="2999-01").json()["detail"]
            == "periodInFuture"
        )
        assert _post(client, household.id).status_code == 201
        assert _post(client, household.id).json()["detail"] == "periodAlreadySubmitted"

    def test_closed_periods_must_go_through_restatement(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        session.add(BillingPeriod(period=PREVIOUS, status="closed"))
        session.flush()

        response = _post(client, household.id)

        assert response.status_code == 409
        assert response.json()["detail"] == "periodClosed"

    def test_non_admin_is_forbidden(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert _post(client, 1).status_code == 403


class TestCorrectAndVoid:
    def test_correcting_an_open_reading_updates_it_in_place_and_audits(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period=PREVIOUS, day_meter_value="1234"
        )
        reading.needs_review = True
        session.flush()

        response = client.patch(
            f"/admin/readings/{reading.id}",
            json={"day_meter_value": "1284", "reason": "typo"},
        )

        assert response.status_code == 200, response.text
        session.refresh(reading)
        assert reading.day_meter_value == D("1284")
        assert reading.night_meter_value == D("0")
        assert reading.needs_review is False
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "readingCorrected")
        ).one()
        assert D(entry.before["day"]) == D("1234") and D(entry.after["day"]) == D(
            "1284"
        )
        assert entry.reason == "typo"

    def test_void_removes_the_reading_and_keeps_the_trail(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period=PREVIOUS, day_meter_value="500"
        )

        response = client.post(
            f"/admin/readings/{reading.id}/void", json={"reason": "wrong plot"}
        )

        assert response.status_code == 204
        assert session.exec(select(MeterReading)).all() == []
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "readingVoided")
        ).one()
        assert entry.reason == "wrong plot"
        assert D(entry.before["day"]) == D("500")

    def test_empty_reason_and_missing_reading(self, client, session: Session) -> None:
        _admin(client, session)
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period=PREVIOUS
        )

        assert (
            client.patch(
                f"/admin/readings/{reading.id}", json={"reason": ""}
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/admin/readings/{reading.id}/void", json={"reason": ""}
            ).status_code
            == 422
        )
        assert (
            client.patch("/admin/readings/999999", json={"reason": "x"}).status_code
            == 404
        )

    def test_closed_period_readings_are_not_editable_directly(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        reading = make_meter_reading(
            session, household_id=household.id, period=PREVIOUS
        )
        session.add(BillingPeriod(period=PREVIOUS, status="closed"))
        session.flush()

        patch = client.patch(
            f"/admin/readings/{reading.id}",
            json={"day_meter_value": "9", "reason": "x"},
        )
        void = client.post(f"/admin/readings/{reading.id}/void", json={"reason": "x"})

        assert patch.status_code == void.status_code == 409
        assert patch.json()["detail"] == "periodClosed"
