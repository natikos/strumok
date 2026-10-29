"""Bank statement upload (issue #252). Fixtures are synthetic."""

from sqlmodel import Session, func, select

from app.api.bank.service import MAX_BYTES
from app.db.models import AuditLog, BankStatementFile, BankTransaction
from tests.factories import authenticate, make_user

OWN = "UA000000000000000000000000001"
HEADER = (
    "ЄДРПОУ;МФО;Рахунок;Валюта;Номер документу;Дата операції;МФО банку;"
    "Назва банку;Рахунок кореспондента;ЄДРПОУ кореспондента;Кореспондент;"
    "Сума;Призначення платежу;"
)


def _row(doc="100.", day="15.05.2025", amount="500.00") -> str:
    return f"1;305299;{OWN};UAH;{doc};{day};1;Bank;UA111;2;Payer;{amount};plot 7;"


def _csv(*rows: str) -> bytes:
    return "\n".join([HEADER, *rows]).encode("utf-8")


def _upload(client, data: bytes, name: str = "statement.csv"):
    return client.post(
        "/admin/bank-statements", files={"file": (name, data, "text/csv")}
    )


def _admin(client, session: Session):
    admin = make_user(session, is_admin=True)
    authenticate(client, admin)
    return admin


def _tx_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(BankTransaction)).one()


def test_requires_admin(client, session: Session) -> None:
    authenticate(client, make_user(session))
    assert _upload(client, _csv(_row())).status_code == 403


def test_import_reports_counts_and_coverage(client, session: Session) -> None:
    _admin(client, session)
    res = _upload(
        client, _csv(_row("1."), _row("2.", "20.05.2025"), _row("3.", amount="-5.00"))
    )
    assert res.status_code == 200
    assert res.json() == {
        "already_imported": False,
        "credits_new": 2,
        "credits_duplicate": 0,
        "debits_skipped": 1,
        "covered_through": "2025-05-20",
    }
    assert _tx_count(session) == 2


def test_same_file_twice_is_idempotent(client, session: Session) -> None:
    _admin(client, session)
    data = _csv(_row("1."), _row("2."))
    _upload(client, data)
    res = _upload(client, data)
    assert res.json()["already_imported"] is True
    assert res.json()["credits_new"] == 0
    assert res.json()["credits_duplicate"] == 2
    assert _tx_count(session) == 2
    assert session.exec(select(func.count()).select_from(BankStatementFile)).one() == 1


def test_overlapping_files_add_no_duplicates(client, session: Session) -> None:
    _admin(client, session)
    _upload(client, _csv(_row("1."), _row("2.")))
    res = _upload(client, _csv(_row("2."), _row("3.", "25.05.2025")))
    assert res.json()["credits_new"] == 1
    assert res.json()["credits_duplicate"] == 1
    assert res.json()["covered_through"] == "2025-05-25"
    assert _tx_count(session) == 3


def test_rejects_non_csv_oversize_and_bad_content(client, session: Session) -> None:
    _admin(client, session)
    assert (
        _upload(client, _csv(_row()), "s.xlsx").json()["detail"]
        == "bankStatementNotCsv"
    )
    big = _upload(client, b"x" * (MAX_BYTES + 1))
    assert big.status_code == 413
    bad = _upload(client, _csv(_row(amount="5,00")))
    assert bad.status_code == 422
    assert bad.json() == {"detail": "bankStatementInvalid", "row": 2, "column": "Сума"}
    assert _tx_count(session) == 0


def test_audit_has_no_pii_and_admins_notified(
    client, session: Session, monkeypatch
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "app.api.bank.routes.notify_bank_queue",
        lambda *, session, file_id: calls.append(file_id),
    )
    admin = _admin(client, session)
    _upload(client, _csv(_row("1.")), "private-name.csv")
    entry = session.exec(
        select(AuditLog).where(AuditLog.action == "bank_statement.import")
    ).one()
    assert entry.actor_user_id == admin.id
    dump = str(entry.after)
    assert "Payer" not in dump and "private-name" not in dump and "UA111" not in dump
    assert entry.after["credits_new"] == 1
    assert len(calls) == 1
    _upload(client, _csv(_row("1.")), "again.csv")
    assert len(calls) == 1
