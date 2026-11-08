"""Credits that cite exactly one STR-<id> are booked on import; the rest wait
for an admin. Fixtures are synthetic, plus a smoke test on the real statements
when they are present locally (they are git-ignored)."""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.api.bank.matching.matcher import match
from app.core.domain.bank_statement import parse_statement
from app.db.models import BankTransaction, Household, Payment
from tests.factories import make_household
from tests.test_bank_import import OWN, _admin, _csv, _upload


def _row(
    doc: str, purpose: str, amount: str = "500.00", day: str = "15.05.2025"
) -> str:
    return f"1;305299;{OWN};UAH;{doc};{day};1;Bank;UA111;2;Payer;{amount};{purpose};"


def _payments(session: Session) -> list[Payment]:
    return list(session.exec(select(Payment)))


def test_single_reference_is_booked_automatically(
    client, session: Session, monkeypatch
) -> None:
    _admin(client, session)
    house = make_household(session, name="Plot 1")
    notified: list[int] = []
    monkeypatch.setattr(
        "app.api.bank.routes.notify_bank_queue",
        lambda **kw: notified.append(kw["file_id"]),
    )

    res = _upload(client, _csv(_row("1.", f"Електроенергія STR-{house.id}")))

    assert res.status_code == 200
    [payment] = _payments(session)
    assert payment.household_id == house.id
    assert str(payment.amount_uah) == "500.00"
    assert payment.recorded_by_user_id is None
    assert notified == []


def test_unclear_credits_stay_queued_and_admin_is_notified(
    client, session: Session, monkeypatch
) -> None:
    _admin(client, session)
    a = make_household(session, name="Іваненко")
    b = make_household(session, name="Петренко")
    notified: list[int] = []
    monkeypatch.setattr(
        "app.api.bank.routes.notify_bank_queue",
        lambda **kw: notified.append(kw["file_id"]),
    )

    _upload(
        client,
        _csv(
            _row("1.", f"STR-{a.id} STR-{b.id}"),  # several references
            _row("2.", "STR-99999"),  # unknown household
            _row("3.", "за світло Іваненко"),  # name only
            _row("4.", f"STR-{a.id}", amount="-5.00"),  # debit, never a credit
        ),
    )

    assert _payments(session) == []
    assert len(list(session.exec(select(BankTransaction)))) == 3
    assert len(notified) == 1


def test_mixed_file_books_only_the_certain_one(client, session: Session) -> None:
    _admin(client, session)
    house = make_household(session, name="Plot 1")

    _upload(client, _csv(_row("1.", f"STR-{house.id}"), _row("2.", "невідомо")))

    assert len(_payments(session)) == 1
    assert len(list(session.exec(select(BankTransaction)))) == 2


REAL = sorted((Path(__file__).parents[1] / "scripts" / "data" / "bank").glob("*.csv"))


@pytest.mark.skipif(not REAL, reason="real statements are not checked in")
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.name)
def test_real_statements_parse_and_never_auto_match(path: Path) -> None:
    houses = [Household(id=i, name=f"Plot {i}") for i in range(1, 200)]
    iban = None
    for line in path.read_bytes().decode("cp1251").splitlines()[1:2]:
        iban = line.split(";")[2]
    assert iban

    parsed = parse_statement(path.read_bytes(), iban)

    assert parsed.credits
    for credit in parsed.credits:
        assert credit.amount_uah > 0
        assert credit.purpose is not None
        # Pre-app statements carry no STR reference, so none may be booked blindly.
        assert [
            s for s in match(credit.purpose, houses) if s.source == "reference"
        ] == []
