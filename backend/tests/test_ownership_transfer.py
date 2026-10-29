"""Plots change hands: each owner keeps their own bills, and a new owner sees
nothing from before they took over."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.core.time import utc_now
from app.db.models import (
    AuditLog,
    BillingPeriod,
    ChargeAdjustment,
    Household,
    HouseholdCharge,
    HouseholdOwnership,
    PeriodRestatement,
    Payment,
)
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal
HANDOVER = {"handover_day_meter_value": "500", "handover_night_meter_value": "200"}


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _transfer(client, household_id: int, new_owner_id: int, **extra):
    return client.patch(
        f"/admin/households/{household_id}/owner",
        json={
            "user_id": new_owner_id,
            "confirm_reassignment": True,
            **HANDOVER,
            **extra,
        },
    )


def _charge(
    session: Session, household_id: int, owner_id: int, period: str, total: str
):
    if session.get(BillingPeriod, period) is None:
        session.add(BillingPeriod(period=period, status="closed"))
        session.flush()
    session.add(
        HouseholdCharge(
            period=period,
            household_id=household_id,
            owner_user_id=owner_id,
            day_usage_kwh=D("0"),
            night_usage_kwh=D("0"),
            tariff_uah=D(total),
            total_uah=D(total),
        )
    )
    session.flush()


class TestTransferRules:
    def test_a_handover_reading_is_required_to_change_owners(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={"user_id": new.id, "confirm_reassignment": True},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "handoverReadingRequired"
        session.refresh(household)
        assert household.user_id == old.id

    def test_handing_values_over_one_at_a_time_is_invalid(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)

        response = client.patch(
            f"/admin/households/{household.id}/owner",
            json={
                "user_id": new.id,
                "confirm_reassignment": True,
                "handover_day_meter_value": "5",
            },
        )

        assert response.status_code == 422

    def test_first_assignment_of_an_unowned_plot_needs_no_handover(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        new = make_user(session)
        household = make_household(session)

        response = client.patch(
            f"/admin/households/{household.id}/owner", json={"user_id": new.id}
        )

        assert response.status_code == 200, response.text

    def test_an_outstanding_balance_needs_explicit_acknowledgement(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)
        _charge(session, household.id, old.id, "2024-01", "300.00")

        refused = _transfer(client, household.id, new.id)
        assert refused.status_code == 409
        assert refused.json()["detail"] == "householdHasOutstandingBalance"
        session.refresh(household)
        assert household.user_id == old.id

        accepted = _transfer(client, household.id, new.id, acknowledge_balance=True)
        assert accepted.status_code == 200, accepted.text

    def test_a_settled_balance_transfers_without_acknowledgement(
        self, client, session: Session
    ) -> None:
        admin = _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)
        _charge(session, household.id, old.id, "2024-01", "300.00")
        session.add(
            Payment(
                household_id=household.id,
                owner_user_id=old.id,
                amount_uah=D("300.00"),
                paid_on=utc_now().date(),
                method="cash",
                recorded_by_user_id=admin.id,
            )
        )
        session.flush()

        assert _transfer(client, household.id, new.id).status_code == 200

    def test_the_transfer_is_audited_and_the_history_kept(
        self, client, session: Session
    ) -> None:
        admin = _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)

        assert _transfer(client, household.id, new.id).status_code == 200

        entry = session.exec(
            select(AuditLog).where(AuditLog.action == "householdTransferred")
        ).one()
        assert (entry.actor_user_id, entry.household_id) == (admin.id, household.id)
        rows = session.exec(
            select(HouseholdOwnership)
            .where(HouseholdOwnership.household_id == household.id)
            .order_by(HouseholdOwnership.id)
        ).all()
        assert [(r.user_id, r.valid_to is None) for r in rows] == [
            (old.id, False),
            (new.id, True),
        ]
        assert rows[0].handover_day_meter_value == D("500")
        assert rows[0].handover_night_meter_value == D("200")
        session.refresh(household)
        assert household.user_id == new.id


class TestNewOwnerSeesNothingEarlier:
    def _transferred(self, client, session: Session):
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)
        make_meter_reading(
            session,
            household_id=household.id,
            period="2024-01",
            day_meter_value="100",
            night_meter_value="50",
        )
        _charge(session, household.id, old.id, "2024-01", "300.00")
        restatement = PeriodRestatement(period="2024-01", reason="x", inputs={})
        session.add(restatement)
        session.flush()
        session.add(
            ChargeAdjustment(
                restatement_id=restatement.id,
                household_id=household.id,
                owner_user_id=old.id,
                applies_to_period="2024-01",
                posted_in_period="2024-01",
                amount_uah=D("12.00"),
                reason_code="rateCorrection",
                reason="rate fixed",
            )
        )
        session.add(
            Payment(
                household_id=household.id,
                owner_user_id=old.id,
                amount_uah=D("100.00"),
                paid_on=utc_now().date(),
                method="cash",
            )
        )
        session.flush()
        _admin(client, session)
        assert (
            _transfer(
                client, household.id, new.id, acknowledge_balance=True
            ).status_code
            == 200
        )
        return old, new, household

    def test_readings_charges_adjustments_and_balance_start_fresh(
        self, client, session: Session
    ) -> None:
        old, new, household = self._transferred(client, session)
        authenticate(client, new)
        params = {"household_id": household.id}

        readings = client.get("/meter-readings", params=params).json()
        assert all(r["period"] < "2024-01" or r["id"] is None for r in readings)
        assert not [r for r in readings if r["period"] == "2024-01"]
        assert client.get("/billing/statements", params=params).json() == []
        assert client.get("/billing/adjustments", params=params).json() == []
        balance = client.get("/billing/balance", params=params).json()
        assert (D(balance["total_due_uah"]), D(balance["balance_uah"])) == (D(0), D(0))
        (entry,) = client.get("/me/statements").json()
        assert entry["statements"] == []
        assert entry["is_current_owner"] is True
        assert entry["has_previous_owner"] is True

    def test_the_old_owner_keeps_their_bills_and_debt_in_me_statements(
        self, client, session: Session
    ) -> None:
        old, new, household = self._transferred(client, session)
        authenticate(client, old)

        response = client.get("/me/statements")

        assert response.status_code == 200, response.text
        (entry,) = response.json()
        assert entry["household_id"] == household.id
        assert entry["is_current_owner"] is False
        assert entry["has_previous_owner"] is False
        assert entry["owned_until"] is not None
        assert [s["period"] for s in entry["statements"]] == ["2024-01"]
        # 300 charged + 12 adjustment - 100 paid
        assert D(entry["balance"]["balance_uah"]) == D("212.00")

    def test_the_old_owner_can_no_longer_use_the_household_endpoints(
        self, client, session: Session
    ) -> None:
        old, new, household = self._transferred(client, session)
        authenticate(client, old)

        response = client.get("/billing/balance", params={"household_id": household.id})

        assert response.status_code == 403

    def test_a_new_owners_future_bills_are_theirs_alone(
        self, client, session: Session
    ) -> None:
        old, new, household = self._transferred(client, session)
        _charge(session, household.id, new.id, "2024-03", "50.00")
        authenticate(client, new)

        statements = client.get(
            "/billing/statements", params={"household_id": household.id}
        ).json()
        balance = client.get(
            "/billing/balance", params={"household_id": household.id}
        ).json()

        assert [s["period"] for s in statements] == ["2024-03"]
        assert D(balance["balance_uah"]) == D("50.00")


class TestBilledOwnerIsTheOwnerAtPeriodEnd:
    def test_close_snapshots_whoever_held_the_plot_when_the_period_ended(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=new.id)
        # Old owner until mid-February 2024, new owner after.
        cutoff = datetime(2024, 2, 15)
        session.add(
            HouseholdOwnership(
                household_id=household.id,
                user_id=old.id,
                valid_from=datetime(2023, 1, 1),
                valid_to=cutoff,
            )
        )
        session.add(
            HouseholdOwnership(
                household_id=household.id, user_id=new.id, valid_from=cutoff
            )
        )
        for period, day in (("2023-12", "0"), ("2024-01", "10"), ("2024-02", "30")):
            make_meter_reading(
                session,
                household_id=household.id,
                period=period,
                day_meter_value=day,
                night_meter_value="0",
            )
        session.flush()

        for period in ("2024-01", "2024-02"):
            bill = client.put(
                f"/admin/periods/{period}/bill",
                json={
                    "day_kwh": "10" if period == "2024-01" else "20",
                    "night_kwh": "0",
                    "total_uah": "20.00" if period == "2024-01" else "40.00",
                    "confirm": True,
                },
            )
            assert bill.status_code == 200, bill.text
            closed = client.post(
                f"/admin/periods/{period}/close",
                json={"confirm": True, "acknowledge_flags": False},
            )
            assert closed.status_code == 200, closed.text

        owners = {
            c.period: c.owner_user_id for c in session.exec(select(HouseholdCharge))
        }
        # January ended before the cutoff, February after it.
        assert owners == {"2024-01": old.id, "2024-02": new.id}


class TestOwnershipStaysInSync:
    def test_creating_and_unassigning_keep_the_history_in_step(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        owner = make_user(session)
        created = client.post(
            "/admin/households", json={"name": "Plot 9", "user_id": owner.id}
        ).json()

        (row,) = session.exec(
            select(HouseholdOwnership).where(
                HouseholdOwnership.household_id == created["id"]
            )
        ).all()
        assert (row.user_id, row.valid_to) == (owner.id, None)

        response = client.patch(
            f"/admin/households/{created['id']}/owner",
            json={"user_id": None, "confirm_reassignment": True},
        )
        assert response.status_code == 200, response.text
        session.refresh(row)
        assert row.valid_to is not None
        assert session.get(Household, created["id"]).user_id is None

    def test_a_plot_owned_before_history_existed_is_healed_on_change(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)  # no ownership row

        assert _transfer(client, household.id, new.id).status_code == 200

        users = session.exec(
            select(HouseholdOwnership.user_id)
            .where(HouseholdOwnership.household_id == household.id)
            .order_by(HouseholdOwnership.id)
        ).all()
        assert users == [old.id, new.id]


class TestUnassignThenAssign:
    def _unassign(self, client, household_id: int):
        response = client.patch(
            f"/admin/households/{household_id}/owner",
            json={"user_id": None, "confirm_reassignment": True},
        )
        assert response.status_code == 200, response.text

    def test_a_new_owner_after_unassigning_needs_a_handover_reading(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)
        self._unassign(client, household.id)

        response = client.patch(
            f"/admin/households/{household.id}/owner", json={"user_id": new.id}
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "handoverReadingRequired"
        session.refresh(household)
        assert household.user_id is None

    def test_the_outgoing_owners_debt_needs_acknowledgement(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old, new = make_user(session), make_user(session)
        household = make_household(session, user_id=old.id)
        _charge(session, household.id, old.id, "2024-01", "300.00")
        self._unassign(client, household.id)

        refused = _transfer(client, household.id, new.id)
        assert refused.status_code == 409
        assert refused.json()["detail"] == "householdHasOutstandingBalance"

        accepted = _transfer(client, household.id, new.id, acknowledge_balance=True)
        assert accepted.status_code == 200, accepted.text
        rows = session.exec(
            select(HouseholdOwnership)
            .where(HouseholdOwnership.household_id == household.id)
            .order_by(HouseholdOwnership.valid_from)
        ).all()
        assert [row.user_id for row in rows] == [old.id, new.id]
        assert rows[0].handover_day_meter_value == D("500")
        audit = session.exec(
            select(AuditLog).where(AuditLog.action == "householdTransferred")
        ).one()
        assert audit.before == {"user_id": None, "outgoing_user_id": old.id}

    def test_returning_the_plot_to_its_last_owner_needs_no_handover(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        old = make_user(session)
        household = make_household(session, user_id=old.id)
        self._unassign(client, household.id)

        response = client.patch(
            f"/admin/households/{household.id}/owner", json={"user_id": old.id}
        )

        assert response.status_code == 200, response.text
