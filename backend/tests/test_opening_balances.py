"""Opening balances carried over from the spreadsheets (issue #202)."""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.api.billing.payments import get_balance
from app.db.models import AuditLog
from scripts.import_opening_balances import parse_balances
from tests.factories import authenticate, make_household, make_user
from tests.test_payments import _charge, _pay

D = Decimal


def _set(client, household_id: int, amount: str):
    return client.post(
        f"/admin/households/{household_id}/opening-balance",
        json={"amount_uah": amount, "as_of": "2024-12-01", "note": "sheet"},
    )


class TestOpeningBalanceApi:
    def test_debt_counts_in_the_balance_and_payments_settle_it_before_charges(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        _charge(session, household.id, "2025-01", "100.00")
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)

        assert _set(client, household.id, "300.00").status_code == 201
        _pay(client, household.id, "350.00")
        authenticate(client, owner)
        body = client.get("/billing/balance").json()

        assert D(body["total_due_uah"]) == D("400.00")
        assert D(body["balance_uah"]) == D("50.00")
        # 350 clears the 300 opening debt first, leaving 50 for the charge.
        assert [(p["period"], p["status"]) for p in body["periods"]] == [
            ("2025-01", "partial")
        ]

    def test_credit_reduces_what_is_owed(self, client, session: Session) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        _charge(session, household.id, "2025-01", "100.00")
        authenticate(client, make_user(session, is_admin=True))

        _set(client, household.id, "-40.00")
        authenticate(client, owner)
        body = client.get("/billing/balance").json()

        assert D(body["balance_uah"]) == D("60.00")

    def test_second_opening_balance_is_rejected_and_audited_once(
        self, client, session: Session
    ) -> None:
        household = make_household(session)
        authenticate(client, make_user(session, is_admin=True))

        first = _set(client, household.id, "10.00")
        second = _set(client, household.id, "99.00")

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["detail"] == "openingBalanceAlreadySet"
        read = client.get(f"/admin/households/{household.id}/opening-balance").json()
        assert D(read["amount_uah"]) == D("10.00")
        actions = session.exec(
            select(AuditLog.action).where(AuditLog.household_id == household.id)
        ).all()
        assert actions.count("openingBalanceSet") == 1

    def test_unknown_household_is_404(self, client, session: Session) -> None:
        authenticate(client, make_user(session, is_admin=True))

        assert _set(client, 999999, "1.00").status_code == 404

    def test_residents_cannot_set_one(self, client, session: Session) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        authenticate(client, owner)

        assert _set(client, household.id, "1.00").status_code in (401, 403)


def _correct(client, household_id: int, amount: str, reason: str = "sign flipped"):
    return client.post(
        f"/admin/households/{household_id}/opening-balance/corrections",
        json={"amount_uah": amount, "reason": reason},
    )


class TestOpeningBalanceCorrection:
    def test_signed_correction_changes_balance_and_keeps_original(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        admin = make_user(session, is_admin=True)
        authenticate(client, admin)
        _set(client, household.id, "-300.00")

        response = _correct(client, household.id, "600.00")

        assert response.status_code == 201
        body = response.json()
        assert D(body["amount_uah"]) == D("-300.00")
        assert D(body["effective_amount_uah"]) == D("300.00")
        assert [c["reason"] for c in body["corrections"]] == ["sign flipped"]
        authenticate(client, owner)
        assert D(client.get("/billing/balance").json()["balance_uah"]) == D("300.00")
        audit = session.exec(
            select(AuditLog).where(AuditLog.action == "openingBalanceCorrected")
        ).one()
        assert audit.reason == "sign flipped"
        assert audit.actor_user_id == admin.id

    def test_correction_stays_with_the_original_owner(
        self, client, session: Session
    ) -> None:
        old_owner = make_user(session)
        new_owner = make_user(session)
        household = make_household(session, user_id=old_owner.id)
        authenticate(client, make_user(session, is_admin=True))
        _set(client, household.id, "100.00")
        household.user_id = new_owner.id
        session.add(household)
        session.commit()

        _correct(client, household.id, "50.00")

        assert get_balance(
            session=session, household_id=household.id, owner_user_id=old_owner.id
        ).balance_uah == D("150.00")
        assert get_balance(
            session=session, household_id=household.id, owner_user_id=new_owner.id
        ).balance_uah == D("0.00")

    @pytest.mark.parametrize(
        "payload",
        [
            {"amount_uah": "0", "reason": "x"},
            {"amount_uah": "10.00", "reason": "   "},
            {"amount_uah": "10.00"},
        ],
    )
    def test_rejects_zero_amount_or_missing_reason(
        self, client, session: Session, payload
    ) -> None:
        household = make_household(session)
        authenticate(client, make_user(session, is_admin=True))
        _set(client, household.id, "100.00")

        response = client.post(
            f"/admin/households/{household.id}/opening-balance/corrections",
            json=payload,
        )

        assert response.status_code == 422

    def test_without_opening_balance_is_404(self, client, session: Session) -> None:
        household = make_household(session)
        authenticate(client, make_user(session, is_admin=True))

        response = _correct(client, household.id, "10.00")

        assert response.status_code == 404
        assert response.json()["detail"] == "openingBalanceNotFound"

    def test_residents_cannot_correct(self, client, session: Session) -> None:
        owner = make_user(session)
        household = make_household(session, user_id=owner.id)
        authenticate(client, make_user(session, is_admin=True))
        _set(client, household.id, "100.00")
        authenticate(client, owner)

        assert _correct(client, household.id, "-100.00").status_code == 403

    def test_corrections_are_append_only(self, client, session: Session) -> None:
        household = make_household(session)
        authenticate(client, make_user(session, is_admin=True))
        _set(client, household.id, "100.00")
        _correct(client, household.id, "10.00")

        with pytest.raises(Exception, match="append-only"):
            session.exec(text("UPDATE opening_balance_corrections SET amount_uah = 1"))
        session.rollback()


class TestParseBalances:
    def test_flips_sheet_sign_and_accepts_comma_decimals(self, tmp_path) -> None:
        csv_file = tmp_path / "b.csv"
        csv_file.write_text('csv_id,balance\n1,"-120,50"\n2,35\n', encoding="utf-8")

        result = parse_balances(str(csv_file), {"1": 10, "2": 20})

        assert result == {10: D("120.50"), 20: D("-35.00")}

    def test_reports_every_bad_row_without_partial_result(self, tmp_path) -> None:
        csv_file = tmp_path / "b.csv"
        csv_file.write_text("csv_id,balance\n1,abc\n9,5\n", encoding="utf-8")

        with pytest.raises(ValueError) as exc:
            parse_balances(str(csv_file), {"1": 10})

        assert "row 2" in str(exc.value) and "row 3" in str(exc.value)
