"""Bank review queue (issue #253). Fixtures are synthetic."""

from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.core.ownership import set_owner
from app.db.models import (
    AuditLog,
    BankStatementFile,
    BankTransaction,
    OpeningBalance,
    Payment,
)
from tests.factories import authenticate, make_household, make_user

BASE = "/admin/bank-transactions"


def _tx(session: Session, amount="500.00", day=date(2025, 5, 15)) -> BankTransaction:
    file = session.exec(select(BankStatementFile)).first()
    if file is None:
        file = BankStatementFile(
            sha256="a" * 64,
            original_filename="s.csv",
            encoding="utf-8",
            account_iban="UA0",
            first_operation_date=day,
            last_operation_date=day,
            covered_through=day,
            rows_total=1,
            credits_new=1,
            credits_duplicate=0,
            debits_skipped=0,
        )
        session.add(file)
        session.flush()
    count = len(list(session.exec(select(BankTransaction))))
    tx = BankTransaction(
        document_number=f"d{count}",
        operation_date=day,
        amount_uah=Decimal(amount),
        payer_iban="UA111",
        payer_name="Ivan Secret",
        purpose="plot 7 secret purpose",
        first_file_id=file.id,
    )
    session.add(tx)
    session.flush()
    return tx


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _confirm(client, tx, *lines):
    return client.post(
        f"{BASE}/{tx.id}/confirm",
        json={
            "lines": [{"household_id": h, "amount_uah": a} for h, a in lines],
        },
    )


def test_requires_admin(client, session: Session) -> None:
    authenticate(client, make_user(session))
    assert client.get(BASE).status_code == 403


def test_queue_lists_unresolved(client, session: Session) -> None:
    _admin(client, session)
    tx = _tx(session)
    res = client.get(BASE)
    assert [row["id"] for row in res.json()] == [tx.id]


def test_confirm_creates_transfer_payment_without_pii(client, session: Session) -> None:
    admin = _admin(client, session)
    owner = make_user(session)
    household = make_household(session, user_id=owner.id)
    tx = _tx(session)

    res = _confirm(client, tx, (household.id, "500.00"))
    assert res.status_code == 200

    payment = session.exec(select(Payment)).one()
    assert payment.method == "transfer"
    assert payment.amount_uah == Decimal("500.00")
    assert payment.paid_on == tx.operation_date
    assert payment.owner_user_id == owner.id
    assert payment.note is None
    assert payment.bank_transaction_id == tx.id
    assert payment.recorded_by_user_id == admin.id
    assert client.get(BASE).json() == []

    trail = " ".join(str(a.after) for a in session.exec(select(AuditLog)))
    assert "Secret" not in trail and "UA111" not in trail


def test_double_confirm_is_409(client, session: Session) -> None:
    _admin(client, session)
    household = make_household(session)
    tx = _tx(session)
    assert _confirm(client, tx, (household.id, "500.00")).status_code == 200
    res = _confirm(client, tx, (household.id, "500.00"))
    assert res.status_code == 409
    assert res.json()["detail"] == "bankTransactionResolved"


def test_split_must_sum_to_credit(client, session: Session) -> None:
    _admin(client, session)
    a, b = make_household(session, name="A"), make_household(session, name="B")
    tx = _tx(session)
    res = _confirm(client, tx, (a.id, "200.00"), (b.id, "200.00"))
    assert res.status_code == 422
    assert res.json()["detail"] == "splitInvalid"
    assert session.exec(select(Payment)).first() is None


def test_split_creates_payment_per_household(client, session: Session) -> None:
    _admin(client, session)
    a, b = make_household(session, name="A"), make_household(session, name="B")
    tx = _tx(session)
    assert _confirm(client, tx, (a.id, "200.00"), (b.id, "300.00")).status_code == 200
    assert len(list(session.exec(select(Payment)))) == 2


def test_duplicate_household_in_split_rejected(client, session: Session) -> None:
    _admin(client, session)
    a = make_household(session)
    tx = _tx(session)
    res = _confirm(client, tx, (a.id, "200.00"), (a.id, "300.00"))
    assert res.status_code == 422


def test_credit_on_or_before_opening_balance_rejected(client, session: Session) -> None:
    _admin(client, session)
    household = make_household(session)
    session.add(
        OpeningBalance(
            household_id=household.id,
            amount_uah=Decimal("10.00"),
            as_of=date(2025, 5, 15),
        )
    )
    session.flush()
    tx = _tx(session, day=date(2025, 5, 15))
    res = _confirm(client, tx, (household.id, "500.00"))
    assert res.status_code == 422
    assert res.json()["detail"] == "beforeOpeningBalance"


def test_owner_is_owner_at_operation_date(client, session: Session) -> None:
    _admin(client, session)
    first, second = make_user(session), make_user(session)
    household = make_household(session, user_id=first.id)
    set_owner(session, household, second.id)
    session.flush()
    tx = _tx(session, day=date(2020, 1, 10))
    _confirm(client, tx, (household.id, "500.00"))
    assert session.exec(select(Payment)).one().owner_user_id == first.id


def test_voiding_one_sibling_voids_all_and_requeues(client, session: Session) -> None:
    _admin(client, session)
    a, b = make_household(session, name="A"), make_household(session, name="B")
    tx = _tx(session)
    _confirm(client, tx, (a.id, "200.00"), (b.id, "300.00"))
    first = session.exec(select(Payment)).first()
    res = client.post(f"/admin/payments/{first.id}/void", json={"reason": "wrong"})
    assert res.status_code == 200, res.text
    session.expire_all()
    assert all(p.voided_at is not None for p in session.exec(select(Payment)))
    assert [row["id"] for row in client.get(BASE).json()] == [tx.id]


def test_dismiss_removes_from_queue_and_blocks_confirm(
    client, session: Session
) -> None:
    _admin(client, session)
    household = make_household(session)
    tx = _tx(session)
    assert client.post(f"{BASE}/{tx.id}/dismiss").status_code == 204
    assert client.get(BASE).json() == []
    assert client.post(f"{BASE}/{tx.id}/dismiss").status_code == 409
    assert _confirm(client, tx, (household.id, "500.00")).status_code == 409


def test_link_existing_manual_transfer(client, session: Session) -> None:
    admin = _admin(client, session)
    household = make_household(session)
    tx = _tx(session, day=date(2025, 5, 15))
    near = Payment(
        household_id=household.id,
        amount_uah=Decimal("500.00"),
        paid_on=date(2025, 5, 12),
        method="transfer",
        recorded_by_user_id=admin.id,
    )
    far = Payment(
        household_id=household.id,
        amount_uah=Decimal("500.00"),
        paid_on=date(2025, 5, 1),
        method="transfer",
        recorded_by_user_id=admin.id,
    )
    session.add_all([near, far])
    session.flush()

    candidates = client.get(BASE).json()[0]["link_candidates"]
    assert [c["payment_id"] for c in candidates] == [near.id]
    assert (
        client.post(f"{BASE}/{tx.id}/link", json={"payment_id": far.id}).status_code
        == 422
    )
    assert (
        client.post(f"{BASE}/{tx.id}/link", json={"payment_id": near.id}).status_code
        == 204
    )
    assert client.get(BASE).json() == []
    assert (
        client.post(f"{BASE}/{tx.id}/link", json={"payment_id": near.id}).status_code
        == 409
    )


def test_unknown_transaction_404(client, session: Session) -> None:
    _admin(client, session)
    assert client.post(f"{BASE}/999999/dismiss").status_code == 404
