"""Restating a closed period: closed charges never change, deltas become
signed adjustments in the current open period."""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.db.models import (
    AuditLog,
    ChargeAdjustment,
    ElectricityRate,
    HouseholdCharge,
    MeterReading,
    PeriodRestatement,
)
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


def _closed_period(client, session: Session, *, bill: str = "500.00"):
    """Two households (100 and 300 kWh) closed with a bill of 500."""
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    rate = make_electricity_rate(session, day_rate_uah="1", night_rate_uah="1")
    a = make_household(session, name="A", user_id=make_user(session).id)
    b = make_household(session, name="B", user_id=make_user(session).id)
    for household, now in ((a, "100"), (b, "300")):
        make_meter_reading(
            session, household_id=household.id, period="2024-01", day_meter_value="0"
        )
        make_meter_reading(
            session, household_id=household.id, period=PAST, day_meter_value=now
        )
    client.put(
        f"/admin/periods/{PAST}/bill",
        json={"day_kwh": "400", "night_kwh": "0", "total_uah": bill, "confirm": True},
    )
    assert client.post(f"/admin/periods/{PAST}/close", json=BODY).status_code == 200
    return admin, rate, a, b


def _restate(
    client, corrections: dict, *, reason: str | None = "fix", dry_run: bool = False
):
    return client.post(
        f"/admin/periods/{PAST}/restate",
        json={
            "corrections": corrections,
            "reason": reason,
            "dry_run": dry_run,
            "confirm": True,
        },
    )


class TestRestatement:
    def test_bill_correction_posts_adjustments_and_never_touches_closed_rows(
        self, client, session: Session
    ) -> None:
        admin, _, a, b = _closed_period(client, session)  # bill 500 -> 125 / 375
        closed_before = {
            c.household_id: c.total_uah for c in session.exec(select(HouseholdCharge))
        }

        response = _restate(client, {"bill_total_uah": "600.00"})

        assert response.status_code == 200, response.text
        body = response.json()
        deltas = {line["household_id"]: D(line["delta_uah"]) for line in body["lines"]}
        assert deltas == {a.id: D("25.00"), b.id: D("75.00")}
        assert D(body["total_delta_uah"]) == D("100.00")
        assert body["is_zero_sum"] is False
        closed_after = {
            c.household_id: c.total_uah for c in session.exec(select(HouseholdCharge))
        }
        assert closed_after == closed_before
        adjustments = session.exec(select(ChargeAdjustment)).all()
        assert {x.household_id: x.amount_uah for x in adjustments} == deltas
        assert all(
            x.applies_to_period == PAST and x.reason == "fix" for x in adjustments
        )
        assert all(x.reason_code == "billCorrection" for x in adjustments)
        assert all(x.posted_in_period == body["posted_in_period"] for x in adjustments)
        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "restatementPosted")
        ).one()
        assert entry.entity_id == body["restatement_id"]

    def test_a_pure_rate_correction_nets_to_zero(
        self, client, session: Session
    ) -> None:
        _, rate, a, b = _closed_period(client, session)

        response = _restate(
            client, {"rate": {"day_rate_uah": "1.50", "night_rate_uah": "1"}}
        )

        body = response.json()
        assert D(body["total_delta_uah"]) == D("0.00")
        assert body["is_zero_sum"] is True
        # Day-only usage and a fixed bill: each household's tariff rises but its
        # loss share falls by the same amount, so nobody's total moves.
        assert body["lines"] == []

    def test_dry_run_writes_nothing(self, client, session: Session) -> None:
        _closed_period(client, session)

        response = _restate(
            client, {"bill_total_uah": "600.00"}, reason=None, dry_run=True
        )

        assert response.status_code == 200
        assert len(response.json()["lines"]) == 2
        assert response.json()["restatement_id"] is None
        assert session.exec(select(ChargeAdjustment)).all() == []
        assert session.exec(select(PeriodRestatement)).all() == []

    @pytest.mark.parametrize("reason", [None, "", "   "])
    def test_posting_without_a_reason_is_rejected(
        self, client, session: Session, reason
    ) -> None:
        _closed_period(client, session)

        assert (
            _restate(client, {"bill_total_uah": "600.00"}, reason=reason).status_code
            == 422
        )
        assert session.exec(select(ChargeAdjustment)).all() == []

    def test_a_second_correction_diffs_against_earlier_adjustments(
        self, client, session: Session
    ) -> None:
        _, _, a, b = _closed_period(client, session)
        _restate(client, {"bill_total_uah": "600.00"})

        again = _restate(client, {"bill_total_uah": "600.00"})  # already applied

        assert again.json()["lines"] == []
        assert D(
            sum(x.amount_uah for x in session.exec(select(ChargeAdjustment)))
        ) == D("100.00")

    def test_reading_correction_updates_the_reading_and_the_next_closed_period(
        self, client, session: Session
    ) -> None:
        _, _, a, b = _closed_period(client, session)
        # Next period (2024-03): a's reading 140, b's 340 -> usage 40 each.
        for household, value in ((a, "140"), (b, "340")):
            make_meter_reading(
                session,
                household_id=household.id,
                period="2024-03",
                day_meter_value=value,
            )
        client.put(
            "/admin/periods/2024-03/bill",
            json={
                "day_kwh": "80",
                "night_kwh": "0",
                "total_uah": "80.00",
                "confirm": True,
            },
        )
        assert client.post("/admin/periods/2024-03/close", json=BODY).status_code == 200

        # a actually read 110 in 2024-02, not 100: its 2024-03 usage shrinks by 10.
        response = _restate(
            client,
            {
                "readings": [
                    {
                        "household_id": a.id,
                        "day_meter_value": "110",
                        "night_meter_value": "0",
                    }
                ]
            },
        )

        body = response.json()
        assert body["affected_periods"] == [PAST, "2024-03"]
        assert {line["period"] for line in body["lines"]} == {PAST, "2024-03"}
        reading = session.exec(
            select(MeterReading).where(
                MeterReading.household_id == a.id, MeterReading.period == PAST
            )
        ).one()
        assert reading.day_meter_value == D("110")
        assert (
            session.exec(select(AuditLog).where(AuditLog.action == "readingCorrected"))
            .one()
            .reason
            == "fix"
        )

    def test_open_period_and_empty_corrections_are_refused(
        self, client, session: Session
    ) -> None:
        _closed_period(client, session)

        open_period = client.post(
            "/admin/periods/2099-01/restate",
            json={
                "corrections": {"bill_total_uah": "1"},
                "reason": "x",
                "confirm": True,
            },
        )
        empty = _restate(client, {})

        assert open_period.status_code == 409
        assert open_period.json()["detail"] == "periodNotClosed"
        assert empty.status_code == 409
        assert empty.json()["detail"] == "nothingToCorrect"

    def test_non_admin_is_forbidden(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert _restate(client, {"bill_total_uah": "1"}).status_code == 403


class TestAdjustmentsAreAppendOnly:
    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE charge_adjustments SET amount_uah = 1",
            "DELETE FROM charge_adjustments",
        ],
    )
    def test_update_and_delete_fail_in_the_database(
        self, client, session: Session, statement
    ) -> None:
        _closed_period(client, session)
        _restate(client, {"bill_total_uah": "600.00"})

        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


class TestResidentSeesAdjustments:
    def test_adjustments_endpoint_is_scoped_to_the_household(
        self, client, session: Session
    ) -> None:
        admin, _, a, b = _closed_period(client, session)
        _restate(client, {"bill_total_uah": "600.00"})
        owner = session.get(type(admin), a.user_id)
        authenticate(client, owner)

        rows = client.get("/billing/adjustments").json()

        assert [
            (r["amount_uah"], r["applies_to_period"], r["reason"]) for r in rows
        ] == [("25.00", PAST, "fix")]


class TestRateCorrection:
    def test_correct_updates_the_rate_and_restates_the_closed_periods(
        self, client, session: Session
    ) -> None:
        _, rate, a, b = _closed_period(client, session)

        preview = client.post(
            f"/electricity-rates/{rate.id}/correct",
            json={
                "day_rate_uah": "2",
                "night_rate_uah": "1",
                "dry_run": True,
                "confirm": True,
            },
        )
        posted = client.post(
            f"/electricity-rates/{rate.id}/correct",
            json={
                "day_rate_uah": "2",
                "night_rate_uah": "1",
                "reason": "typo",
                "confirm": True,
            },
        )

        assert preview.status_code == 200
        assert posted.status_code == 200, posted.text
        assert D(posted.json()["total_delta_uah"]) == D("0.00")
        assert session.get(ElectricityRate, rate.id).day_rate_uah == D("2")
        assert (
            session.exec(select(AuditLog).where(AuditLog.action == "rateUpdated"))
            .one()
            .reason
            == "typo"
        )
        assert all(
            x.reason_code == "rateCorrection"
            for x in session.exec(select(ChargeAdjustment))
        )

    def test_reason_is_required_to_post(self, client, session: Session) -> None:
        _, rate, *_ = _closed_period(client, session)
        response = client.post(
            f"/electricity-rates/{rate.id}/correct",
            json={"day_rate_uah": "2", "night_rate_uah": "1", "confirm": True},
        )
        assert response.status_code == 422
