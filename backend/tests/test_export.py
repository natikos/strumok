"""CSV export for the head."""

from decimal import Decimal

from sqlmodel import Session

from tests.factories import authenticate, make_household, make_user

D = Decimal


def _admin_with_payment(client, session: Session):
    owner = make_user(session)
    household = make_household(session, user_id=owner.id, name="Сад")
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    client.post(
        f"/admin/households/{household.id}/payments",
        json={"amount_uah": "12.50", "paid_on": "2024-05-10", "method": "cash"},
    )
    return owner, household


class TestExport:
    def test_payments_csv_has_bom_cyrillic_and_exact_decimals(
        self, client, session: Session
    ) -> None:
        _admin_with_payment(client, session)

        response = client.get("/admin/export/payments")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        text = response.content.decode("utf-8")
        assert text.startswith("﻿")
        assert "Сад" in text
        assert ",12.50," in text

    def test_ua_format_uses_semicolons_and_decimal_commas(
        self, client, session: Session
    ) -> None:
        _admin_with_payment(client, session)

        text = client.get("/admin/export/payments?format=ua").content.decode()

        assert ";12,50;" in text

    def test_payments_date_range_filters(self, client, session: Session) -> None:
        _admin_with_payment(client, session)

        text = client.get("/admin/export/payments?from=2024-06-01").content.decode()

        assert "Сад" not in text

    def test_balances_and_audit_log_export(self, client, session: Session) -> None:
        _admin_with_payment(client, session)

        balances = client.get("/admin/export/balances")
        audit = client.get("/admin/export/audit-log")

        assert balances.status_code == 200
        assert "balance_uah" in balances.text
        assert audit.status_code == 200
        assert "payment" in audit.text.lower()

    def test_residents_are_forbidden(self, client, session: Session) -> None:
        owner, _ = _admin_with_payment(client, session)
        authenticate(client, owner)

        for path in ("balances", "payments", "audit-log", "period/2024-05"):
            assert client.get(f"/admin/export/{path}").status_code == 403
