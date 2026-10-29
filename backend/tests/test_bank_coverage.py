"""Bank coverage notice: when balances may be missing recent payments."""

from datetime import date

from sqlmodel import Session

from app.api.billing.bank_coverage import STALE_AFTER_DAYS, is_awaiting_statement
from app.db.models import BankStatementFile
from tests.factories import authenticate, make_user


def _file(session: Session, covered: date, sha: str = "a" * 64) -> None:
    session.add(
        BankStatementFile(
            sha256=sha,
            original_filename="s.csv",
            encoding="utf-8",
            account_iban="UA0",
            first_operation_date=covered,
            last_operation_date=covered,
            covered_through=covered,
            rows_total=1,
            credits_new=1,
            credits_duplicate=0,
            debits_skipped=0,
        )
    )
    session.commit()


class TestIsAwaiting:
    def test_never_imported_is_awaiting(self) -> None:
        assert is_awaiting_statement(None, date(2026, 5, 10))

    def test_boundary(self) -> None:
        today = date(2026, 5, 30)
        fresh = date(2026, 5, 30).replace(day=30 - STALE_AFTER_DAYS)
        assert not is_awaiting_statement(fresh, today)
        assert is_awaiting_statement(date(2026, 5, 8), today)


class TestEndpoint:
    def test_no_statement_shows_awaiting(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        body = client.get("/billing/bank-coverage").json()
        assert body["covered_through"] is None
        assert body["awaiting_statement"] is True
        assert body["last_imported_at"] is None

    def test_uses_max_coverage_and_hides_import_time_from_residents(
        self, client, session: Session
    ) -> None:
        today = date.today()
        _file(session, date(2020, 1, 1), "a" * 64)
        _file(session, today, "b" * 64)
        authenticate(client, make_user(session))
        body = client.get("/billing/bank-coverage").json()
        assert body["covered_through"] == today.isoformat()
        assert body["awaiting_statement"] is False
        assert body["last_imported_at"] is None

    def test_admin_sees_last_import_time(self, client, session: Session) -> None:
        _file(session, date.today())
        authenticate(client, make_user(session, is_admin=True))
        assert client.get("/billing/bank-coverage").json()["last_imported_at"]

    def test_requires_login(self, client) -> None:
        assert client.get("/billing/bank-coverage").status_code == 401
