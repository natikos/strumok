"""Payments ledger and balances."""

from decimal import Decimal

from sqlmodel import Session, select

from app.db.models import (
    AuditLog,
    BillingPeriod,
    ChargeAdjustment,
    HouseholdCharge,
    PeriodRestatement,
)
from tests.factories import authenticate, make_household, make_user

D = Decimal


def _charge(session: Session, household_id: int, period: str, total: str) -> None:
    if session.get(BillingPeriod, period) is None:
        session.add(BillingPeriod(period=period, status="closed"))
        session.flush()
    session.add(
        HouseholdCharge(
            period=period,
            household_id=household_id,
            day_usage_kwh=D("0"),
            night_usage_kwh=D("0"),
            tariff_uah=D(total),
            total_uah=D(total),
        )
    )
    session.flush()


def _pay(client, household_id: int, amount: str, **extra):
    return client.post(
        f"/admin/households/{household_id}/payments",
        json={"amount_uah": amount, "paid_on": "2024-05-10", "method": "cash", **extra},
    )


class TestBalance:
    def test_partial_payment_leaves_the_remainder_and_overpayment_is_a_credit(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        _charge(session, household.id, "2024-01", "100.00")
        _charge(session, household.id, "2024-02", "200.00")
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)

        _pay(client, household.id, "150.00")
        authenticate(client, owner)
        partial = client.get("/billing/balance").json()
        authenticate(client, admin)
        _pay(client, household.id, "250.00")
        authenticate(client, owner)
        over = client.get("/billing/balance").json()

        assert D(partial["balance_uah"]) == D("150.00")
        assert [(p["period"], p["status"]) for p in partial["periods"]] == [
            ("2024-01", "paid"),
            ("2024-02", "partial"),
        ]
        assert partial["unpaid_months"] == 1
        assert D(over["balance_uah"]) == D("-100.00")  # a credit
        assert over["unpaid_months"] == 0

    def test_an_adjustment_posted_after_a_payment_changes_the_balance(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        _charge(session, household.id, "2024-01", "100.00")
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)
        _pay(client, household.id, "100.00")
        restatement = PeriodRestatement(period="2024-01", reason="x", inputs={})
        session.add(restatement)
        session.flush()
        session.add(
            ChargeAdjustment(
                household_id=household.id,
                applies_to_period="2024-01",
                posted_in_period="2024-02",
                amount_uah=D("25.00"),
                reason_code="manual",
                reason="late fix",
                restatement_id=restatement.id,
            )
        )
        session.add(BillingPeriod(period="2024-02", status="open"))
        session.flush()
        authenticate(client, owner)

        body = client.get("/billing/balance").json()

        assert D(body["balance_uah"]) == D("25.00")
        assert body["periods"][0]["status"] == "partial"

    def test_voided_payments_are_excluded_but_stay_listed_with_the_reason(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        _charge(session, household.id, "2024-01", "100.00")
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)
        payment_id = _pay(client, household.id, "100.00", note="envelope").json()["id"]

        voided = client.post(
            f"/admin/payments/{payment_id}/void", json={"reason": "bounced"}
        )
        listing = client.get(f"/admin/households/{household.id}/payments").json()
        authenticate(client, owner)
        body = client.get("/billing/balance").json()

        assert voided.status_code == 200
        assert D(body["balance_uah"]) == D("100.00")
        assert (
            listing[0]["void_reason"] == "bounced"
            and listing[0]["voided_at"] is not None
        )
        actions = [
            e.action for e in session.exec(select(AuditLog).order_by(AuditLog.id))
        ]
        assert actions == ["paymentRecorded", "paymentVoided"]

    def test_void_needs_a_reason_and_works_once(self, client, session: Session) -> None:
        household = make_household(session)
        authenticate(client, make_user(session, is_admin=True))
        payment_id = _pay(client, household.id, "10.00").json()["id"]

        assert (
            client.post(
                f"/admin/payments/{payment_id}/void", json={"reason": " "}
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/admin/payments/{payment_id}/void", json={"reason": "x"}
            ).status_code
            == 200
        )
        again = client.post(f"/admin/payments/{payment_id}/void", json={"reason": "x"})
        assert (
            again.status_code == 409
            and again.json()["detail"] == "paymentAlreadyVoided"
        )
        assert (
            client.post("/admin/payments/999999/void", json={"reason": "x"}).status_code
            == 404
        )

    def test_payment_validation_and_permissions(self, client, session: Session) -> None:
        household = make_household(session)
        authenticate(client, make_user(session))
        assert _pay(client, household.id, "10.00").status_code == 403
        authenticate(client, make_user(session, is_admin=True))
        assert _pay(client, household.id, "0").status_code == 422
        assert _pay(client, household.id, "-5").status_code == 422
        assert _pay(client, household.id, "5", method="bitcoin").status_code == 422
        assert _pay(client, 999999, "5").status_code == 404

    def test_balances_are_per_household_and_scoped_for_residents(
        self, client, session: Session
    ) -> None:
        mine = make_user(session)
        first = make_household(session, name="First", user_id=mine.id)
        second = make_household(session, name="Second", user_id=mine.id)
        other = make_household(session, name="Other", user_id=make_user(session).id)
        for household, total in (
            (first, "100.00"),
            (second, "40.00"),
            (other, "70.00"),
        ):
            _charge(session, household.id, "2024-01", total)
        authenticate(client, mine)

        a = client.get(f"/billing/balance?household_id={first.id}").json()
        b = client.get(f"/billing/balance?household_id={second.id}").json()
        forbidden = client.get(f"/billing/balance?household_id={other.id}")

        assert (D(a["balance_uah"]), D(b["balance_uah"])) == (D("100.00"), D("40.00"))
        assert forbidden.status_code == 403

    def test_admin_balances_sorted_by_amount_owed_with_a_total(
        self, client, session: Session
    ) -> None:
        small = make_household(session, name="Small", user_id=make_user(session).id)
        big = make_household(session, name="Big")
        credit = make_household(session, name="Credit")
        _charge(session, small.id, "2024-01", "10.00")
        _charge(session, big.id, "2024-01", "500.00")
        authenticate(client, make_user(session, is_admin=True))
        _pay(client, credit.id, "30.00")

        body = client.get("/admin/balances").json()

        assert [h["household_name"] for h in body["households"]] == [
            "Big",
            "Small",
            "Credit",
        ]
        assert D(body["total_outstanding_uah"]) == D(
            "510.00"
        )  # credits don't offset it
        assert D(body["households"][2]["balance_uah"]) == D("-30.00")
