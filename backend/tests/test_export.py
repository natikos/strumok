"""CSV export for the head."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session

from app.db.models import AuditLog, Payment
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

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


# --- acceptance-criteria coverage (#180) ---------------------------------


PERIOD = "2024-02"
ALL_PATHS = ("balances", "payments", "audit-log", f"period/{PERIOD}")


def _parse(response, delimiter: str = ",") -> list[list[str]]:
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=delimiter))


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _add_payment(session, household, *, amount="1.00", paid_on, note=None, **kw):
    payment = Payment(
        household_id=household.id,
        amount_uah=D(amount),
        paid_on=paid_on,
        method="cash",
        note=note,
        **kw,
    )
    session.add(payment)
    session.flush()
    return payment


def _closed_period(client, session: Session, bill: str) -> None:
    make_electricity_rate(session, day_rate_uah="1.37", night_rate_uah="0.71")
    for name, now in (("Сад А", "101"), ("Сад Б", "233"), ("Сад В", "17")):
        household = make_household(session, name=name)
        make_meter_reading(
            session, household_id=household.id, period="2024-01", day_meter_value="0"
        )
        make_meter_reading(
            session, household_id=household.id, period=PERIOD, day_meter_value=now
        )
    response = client.put(
        f"/admin/periods/{PERIOD}/bill",
        json={"day_kwh": "351", "night_kwh": "0", "total_uah": bill, "confirm": True},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"/admin/periods/{PERIOD}/close",
        json={"confirm": True, "acknowledge_flags": False},
    )
    assert response.status_code == 200, response.text


class TestAccess:
    @pytest.mark.parametrize("path", ALL_PATHS)
    def test_unauthenticated_is_401(self, client, path: str) -> None:
        assert client.get(f"/admin/export/{path}").status_code == 401

    @pytest.mark.parametrize("path", ALL_PATHS)
    def test_resident_is_403(self, client, session: Session, path: str) -> None:
        authenticate(client, make_user(session))
        assert client.get(f"/admin/export/{path}").status_code == 403


class TestReconciliation:
    def test_total_column_sums_to_the_bill_exactly(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        _closed_period(client, session, bill="1000.01")

        rows = _parse(client.get(f"/admin/export/period/{PERIOD}"))

        header, body = rows[0], rows[1:]
        assert len(body) == 3
        total = sum(D(r[header.index("total_uah")]) for r in body)
        assert total == D("1000.01")

    def test_ua_format_totals_parse_back_to_the_bill(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        _closed_period(client, session, bill="1000.01")

        rows = _parse(client.get(f"/admin/export/period/{PERIOD}?format=ua"), ";")

        idx = rows[0].index("total_uah")
        assert sum(D(r[idx].replace(",", ".")) for r in rows[1:]) == D("1000.01")
        assert {r[1] for r in rows[1:]} == {"Сад А", "Сад Б", "Сад В"}


class TestEncodingAndMoney:
    def test_all_four_endpoints_start_with_bom_and_keep_cyrillic(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        _closed_period(client, session, bill="500.00")
        owner = make_user(session, first_name="Олена", last_name="Ґрунтовська")
        household = make_household(session, name="Ділянка №7", user_id=owner.id)
        _add_payment(session, household, paid_on=date(2024, 3, 1), note="готівка")
        session.add(
            AuditLog(
                action="probe",
                entity_type="x",
                reason="причина",
                actor_user_id=owner.id,
            )
        )
        session.flush()

        expectations = {
            f"period/{PERIOD}": "Сад Б",
            "balances": "Ґрунтовська",
            "payments": "готівка",
            "audit-log": "причина",
        }
        for path, needle in expectations.items():
            response = client.get(f"/admin/export/{path}")
            assert response.status_code == 200, path
            assert response.content.startswith(b"\xef\xbb\xbf"), path
            assert needle in response.content.decode("utf-8"), path

    @pytest.mark.parametrize(
        ("amount", "standard", "ua"),
        [
            ("0.10", "0.10", "0,10"),
            ("0.30", "0.30", "0,30"),
            ("1234567.89", "1234567.89", "1234567,89"),
            ("9999999999.99", "9999999999.99", "9999999999,99"),
        ],
    )
    def test_payment_amounts_keep_exact_decimals(
        self, client, session: Session, amount: str, standard: str, ua: str
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        _add_payment(session, household, amount=amount, paid_on=date(2024, 5, 1))

        std = _parse(client.get("/admin/export/payments"))
        ua_rows = _parse(client.get("/admin/export/payments?format=ua"), ";")

        assert std[1][std[0].index("amount_uah")] == standard
        assert ua_rows[1][ua_rows[0].index("amount_uah")] == ua

    def test_ua_format_with_decimal_commas_stays_one_column_per_field(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        _add_payment(session, household, amount="12.50", paid_on=date(2024, 5, 1))

        rows = _parse(client.get("/admin/export/payments?format=ua"), ";")

        assert len(rows[0]) == len(rows[1])


class TestPaymentsRange:
    def _seed(self, session: Session):
        household = make_household(session, name="H")
        for day in (
            date(2024, 4, 30),
            date(2024, 5, 1),
            date(2024, 5, 15),
            date(2024, 5, 31),
            date(2024, 6, 1),
        ):
            _add_payment(session, household, paid_on=day)

    def test_from_and_to_bounds_are_inclusive(self, client, session: Session) -> None:
        _admin(client, session)
        self._seed(session)

        rows = _parse(
            client.get("/admin/export/payments?from=2024-05-01&to=2024-05-31")
        )

        col = rows[0].index("paid_on")
        assert [r[col] for r in rows[1:]] == ["2024-05-01", "2024-05-15", "2024-05-31"]

    def test_voided_payments_are_included_with_their_reason(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session)
        payment = _add_payment(
            session, household, amount="5.00", paid_on=date(2024, 5, 2)
        )
        response = client.post(
            f"/admin/payments/{payment.id}/void", json={"reason": 'помилка, "двічі"'}
        )
        assert response.status_code == 200, response.text

        rows = _parse(client.get("/admin/export/payments"))

        row = dict(zip(rows[0], rows[1], strict=True))
        assert row["void_reason"] == 'помилка, "двічі"'
        assert row["voided_at_utc"] != ""

        assert row["voided"] == "true"


class TestAuditRange:
    def test_date_range_includes_the_whole_end_day(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        stamps = {
            "before": datetime(2024, 5, 9, 23, 59, 59),
            "start": datetime(2024, 5, 10, 0, 0, 0),
            "endday-late": datetime(2024, 5, 12, 23, 59, 59),
            "after": datetime(2024, 5, 13, 0, 0, 0),
        }
        for action, created in stamps.items():
            session.add(AuditLog(action=action, entity_type="x", created_at=created))
        session.flush()

        rows = _parse(
            client.get("/admin/export/audit-log?from=2024-05-10&to=2024-05-12")
        )

        col = rows[0].index("action")
        assert [r[col] for r in rows[1:]] == ["start", "endday-late"]


class TestEscaping:
    def test_commas_quotes_and_newlines_round_trip(
        self, client, session: Session
    ) -> None:
        _admin(client, session)
        household = make_household(session, name='Сад "Зоря", ділянка 5\nпівнічна')
        note = 'a,b "c"\r\nline2; semi'
        _add_payment(session, household, paid_on=date(2024, 5, 1), note=note)

        for fmt, delim in (("standard", ","), ("ua", ";")):
            rows = _parse(client.get(f"/admin/export/payments?format={fmt}"), delim)
            assert len(rows) == 2, fmt
            row = dict(zip(rows[0], rows[1], strict=True))
            assert row["household"] == 'Сад "Зоря", ділянка 5\nпівнічна'
            assert row["note"].replace("\r\n", "\n") == note.replace("\r\n", "\n")


class TestSafety:
    def test_formula_prefixed_text_is_neutralised_but_negative_numbers_are_not(
        self, client, session: Session
    ) -> None:
        owner = make_user(session)
        make_household(session, user_id=owner.id, name="=1+1")
        authenticate(client, make_user(session, is_admin=True))

        rows = _parse(client.get("/admin/export/balances"))

        row = dict(zip(rows[0], rows[1], strict=True))
        assert row["household"] == "'=1+1"

    def test_open_period_cannot_be_exported(self, client, session: Session) -> None:
        make_electricity_rate(session)
        authenticate(client, make_user(session, is_admin=True))

        response = client.get("/admin/export/period/2024-05")

        assert response.status_code == 409
        assert response.json()["detail"] == "periodNotClosed"
