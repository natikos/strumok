"""Meter replacements and a household's opening baseline reading."""

from decimal import Decimal

from sqlmodel import Session, select

from app.core.domain import current_billing_period, previous_period
from app.db.models import AuditLog, HouseholdCharge, MeterReading, MeterSegment
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal
PAST = "2024-02"
CURRENT = current_billing_period()
PREVIOUS = previous_period(CURRENT)


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _change(client, household_id: int, **overrides):
    body = {
        "period": PAST,
        "old_final_day": "130",
        "old_final_night": "60",
        "new_start_day": "0",
        "new_start_night": "0",
        "reason": "meter swapped by the utility",
    }
    body.update(overrides)
    return client.post(f"/admin/households/{household_id}/meter-change", json=body)


def _household_with_replaced_meter(session: Session):
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
    # The new meter read 20/5 by the end of the period.
    make_meter_reading(
        session,
        household_id=household.id,
        period=PAST,
        day_meter_value="20",
        night_meter_value="5",
    )
    return household


class TestMeterChange:
    def test_usage_is_old_meter_remainder_plus_new_meter_reading(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = _household_with_replaced_meter(session)

        response = _change(client, household.id)

        assert response.status_code == 201, response.text
        body = response.json()
        # (130 - 100) + (20 - 0) day, (60 - 50) + (5 - 0) night
        assert (D(body["day_usage_kwh"]), D(body["night_usage_kwh"])) == (D(50), D(15))

    def test_the_period_is_billed_across_both_meters(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = _household_with_replaced_meter(session)
        assert _change(client, household.id).status_code == 201
        client.put(
            f"/admin/periods/{PAST}/bill",
            json={
                "day_kwh": "50",
                "night_kwh": "15",
                "total_uah": "115.00",
                "confirm": True,
            },
        )

        response = client.post(
            f"/admin/periods/{PAST}/close",
            json={"confirm": True, "acknowledge_flags": False},
        )

        assert response.status_code == 200, response.text
        charge = session.exec(
            select(HouseholdCharge).where(HouseholdCharge.period == PAST)
        ).one()
        assert (charge.day_usage_kwh, charge.night_usage_kwh) == (D(50), D(15))
        assert charge.total_uah == D("115.00")  # 50 × 2 + 15 × 1

    def test_a_decrease_flag_the_swap_explains_is_cleared(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = _household_with_replaced_meter(session)
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == PAST)
        ).one()
        reading.needs_review, reading.review_reason = True, "decrease"
        session.add(reading)
        session.commit()

        assert _change(client, household.id).status_code == 201

        session.refresh(reading)
        assert (reading.needs_review, reading.review_reason) == (False, None)
        assert (reading.day_usage_kwh, reading.night_usage_kwh) == (D(50), D(15))

    def test_a_recorded_swap_means_a_lower_resident_value_is_not_flagged(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        make_electricity_rate(session)
        make_meter_reading(
            session,
            household_id=household.id,
            period=PREVIOUS,
            day_meter_value="500",
            night_meter_value="300",
        )
        assert (
            _change(
                client,
                household.id,
                period=CURRENT,
                old_final_day="520",
                old_final_night="310",
            ).status_code
            == 201
        )
        authenticate(client, owner)

        response = client.post(
            "/meter-readings",
            json={
                "household_id": household.id,
                "period": CURRENT,
                "day_meter_value": "10",
                "night_meter_value": "4",
            },
        )

        assert response.status_code == 201, response.text
        reading = session.exec(
            select(MeterReading).where(MeterReading.period == CURRENT)
        ).one()
        assert reading.needs_review is False
        assert (reading.day_usage_kwh, reading.night_usage_kwh) == (D(30), D(14))

    def test_it_is_audited_and_shown_in_the_residents_history(
        self, client, session: Session
    ) -> None:
        admin = _admin(client, session)
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        make_meter_reading(session, household_id=household.id, period=CURRENT)
        assert _change(client, household.id, period=CURRENT).status_code == 201

        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "meterReplaced")
        ).one()
        assert (entry.actor_user_id, entry.household_id, entry.period) == (
            admin.id,
            household.id,
            CURRENT,
        )
        assert entry.reason == "meter swapped by the utility"
        authenticate(client, owner)
        history = client.get(
            "/meter-readings", params={"household_id": household.id}
        ).json()
        assert {r["period"]: r["meter_replaced"] for r in history}[CURRENT] is True

    def test_a_second_change_for_the_same_period_is_a_conflict(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        assert _change(client, household.id).status_code == 201

        response = _change(client, household.id)

        assert response.status_code == 409
        assert response.json()["detail"] == "meterChangeAlreadyRecorded"
        assert len(session.exec(select(MeterSegment)).all()) == 1

    def test_future_and_closed_periods_are_refused(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = _household_with_replaced_meter(session)

        assert _change(client, household.id, period="2999-01").json()["detail"] == (
            "periodInFuture"
        )
        client.put(
            f"/admin/periods/{PAST}/bill",
            json={
                "day_kwh": "30",
                "night_kwh": "10",
                "total_uah": "70.00",
                "confirm": True,
            },
        )
        client.post(
            f"/admin/periods/{PAST}/close",
            json={"confirm": True, "acknowledge_flags": False},
        )
        assert _change(client, household.id).json()["detail"] == "periodClosed"

    def test_unknown_household_and_non_admins(self, client, session: Session) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        authenticate(client, user)
        assert _change(client, household.id).status_code == 403

        _admin(client, session)
        assert _change(client, 99999).status_code == 404


class TestBaseline:
    def test_the_first_month_is_billed_from_the_baseline_not_zero(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)

        response = client.post(
            f"/admin/households/{household.id}/readings",
            json={
                "period": PREVIOUS,
                "day_meter_value": "1000",
                "night_meter_value": "400",
                "reason": "opening values",
                "kind": "baseline",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["source"] == "baseline"
        authenticate(client, owner)
        submit = client.post(
            "/meter-readings",
            json={
                "household_id": household.id,
                "period": CURRENT,
                "day_meter_value": "1040",
                "night_meter_value": "410",
            },
        )

        assert submit.status_code == 201, submit.text
        assert (
            D(submit.json()["day_usage_kwh"]),
            D(submit.json()["night_usage_kwh"]),
        ) == (
            D(40),
            D(10),
        )
        assert session.exec(
            select(AuditLog).where(AuditLog.action == "baselineSet")
        ).one()

    def test_a_baseline_is_refused_once_the_household_has_a_reading(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        make_meter_reading(session, household_id=household.id, period=PREVIOUS)

        response = client.post(
            f"/admin/households/{household.id}/readings",
            json={
                "period": previous_period(PREVIOUS),
                "day_meter_value": "1",
                "night_meter_value": "1",
                "reason": "opening values",
                "kind": "baseline",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "baselineNotFirst"

    def test_creating_a_household_can_store_the_starting_values(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        owner = make_user(session)

        response = client.post(
            "/admin/households",
            json={
                "name": "Plot 7",
                "user_id": owner.id,
                "starting_day_meter_value": "250.50",
                "starting_night_meter_value": "120",
            },
        )

        assert response.status_code == 201, response.text
        baseline = session.exec(select(MeterReading)).one()
        assert (baseline.source, baseline.period) == ("baseline", PREVIOUS)
        assert (baseline.day_meter_value, baseline.night_meter_value) == (
            D("250.50"),
            D(120),
        )

    def test_starting_values_come_as_a_pair(self, client, session: Session) -> None:
        _admin(client, session)
        owner = make_user(session)

        response = client.post(
            "/admin/households",
            json={
                "name": "Plot 8",
                "user_id": owner.id,
                "starting_day_meter_value": "250",
            },
        )

        assert response.status_code == 422
