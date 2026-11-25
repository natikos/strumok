"""What happened to each credit of an imported statement."""

from decimal import Decimal

from sqlmodel import Session, select

from app.api.bank.review import link as review_link
from app.db.models import BankTransaction, Payment
from tests.factories import authenticate, make_household, make_user
from tests.test_bank_auto_confirm import _row
from tests.test_bank_import import _admin, _csv, _upload

LIST = "/admin/bank-statements"


def client_files(client) -> int:
    return client.get(LIST).json()[0]["id"]


def _outcome(client, file_id: int) -> dict:
    res = client.get(f"{LIST}/{file_id}/outcome")
    assert res.status_code == 200, res.text
    return res.json()


def _upload_ok(client, *rows: str, name: str = "s.csv") -> int:
    assert _upload(client, _csv(*rows), name).status_code == 200
    return client_files(client)


def _tx_by_doc(session: Session, doc: str) -> BankTransaction:
    return session.exec(
        select(BankTransaction).where(BankTransaction.document_number == doc)
    ).one()


def _ids(rows: list[dict]) -> set[int]:
    return {r["id"] for r in rows}


def test_auto_confirmed_credit_is_listed_with_its_payments(
    client, session: Session
) -> None:
    _admin(client, session)
    house = make_household(session, name="Plot 1")
    fid = _upload_ok(client, _row("1.", f"STR-{house.id}", amount="123.45"))

    out = _outcome(client, fid)

    [auto] = out["auto_confirmed"]
    assert auto["id"] == _tx_by_doc(session, "1.").id
    assert auto["payments"] == [{"household_id": house.id, "amount_uah": "123.45"}]
    assert out["needs_attention"] == [] and out["unmatched"] == []
    assert out["handled_count"] == 0


def test_admin_confirmed_credit_is_handled_not_auto(client, session: Session) -> None:
    _admin(client, session)
    house = make_household(session)
    fid = _upload_ok(client, _row("1.", "невідомо"))
    tx = _tx_by_doc(session, "1.")
    res = client.post(
        f"/admin/bank-transactions/{tx.id}/confirm",
        json={"lines": [{"household_id": house.id, "amount_uah": "500.00"}]},
    )
    assert res.status_code == 200

    out = _outcome(client, fid)

    assert out["auto_confirmed"] == []
    assert out["needs_attention"] == [] and out["unmatched"] == []
    assert out["handled_count"] == 1


def test_dismissed_credit_counts_as_handled(client, session: Session) -> None:
    _admin(client, session)
    fid = _upload_ok(client, _row("1.", "невідомо"))
    tx = _tx_by_doc(session, "1.")
    assert client.post(f"/admin/bank-transactions/{tx.id}/dismiss").status_code == 204

    out = _outcome(client, fid)

    assert out["handled_count"] == 1
    assert out["auto_confirmed"] == [] and out["unmatched"] == []


def test_queued_credits_are_bucketed_by_whether_a_suggestion_exists(
    client, session: Session
) -> None:
    _admin(client, session)
    a = make_household(session, name="Іваненко")
    b = make_household(session, name="Петренко")
    fid = _upload_ok(
        client,
        _row("1.", f"STR-{a.id} STR-{b.id}"),  # several references
        _row("2.", "за світло Іваненко"),  # surname only
        _row("3.", "нічого корисного"),  # nothing
    )
    out = _outcome(client, fid)

    assert out["auto_confirmed"] == []
    attention = {r["id"]: r for r in out["needs_attention"]}
    assert set(attention) == {
        _tx_by_doc(session, "1.").id,
        _tx_by_doc(session, "2.").id,
    }
    assert _ids(out["unmatched"]) == {_tx_by_doc(session, "3.").id}
    several = attention[_tx_by_doc(session, "1.").id]
    assert {s["household_id"] for s in several["suggestions"]} == {a.id, b.id}
    by_name = attention[_tx_by_doc(session, "2.").id]
    assert by_name["suggestion_source"] == "name"
    assert by_name["suggested_household_id"] == a.id


def test_unknown_household_reference_is_not_auto_booked(
    client, session: Session
) -> None:
    _admin(client, session)
    fid = _upload_ok(client, _row("1.", "STR-999999"))
    out = _outcome(client, fid)
    assert out["auto_confirmed"] == []
    assert _ids(out["needs_attention"] + out["unmatched"]) == {
        _tx_by_doc(session, "1.").id
    }


def test_voided_auto_payment_returns_credit_to_the_queue(
    client, session: Session
) -> None:
    _admin(client, session)
    house = make_household(session, name="Plot 1")
    fid = _upload_ok(client, _row("1.", f"STR-{house.id}"))
    payment = session.exec(select(Payment)).one()

    res = client.post(f"/admin/payments/{payment.id}/void", json={"reason": "wrong"})
    assert res.status_code == 200, res.text

    out = _outcome(client, fid)
    tx = _tx_by_doc(session, "1.")
    assert out["auto_confirmed"] == []
    assert _ids(out["needs_attention"] + out["unmatched"]) == {tx.id}
    assert out["handled_count"] == 0


def test_credit_belongs_only_to_the_file_that_first_imported_it(
    client, session: Session
) -> None:
    _admin(client, session)
    house = make_household(session, name="Plot 1")
    first = _upload_ok(client, _row("1.", f"STR-{house.id}"), name="a.csv")
    second = _upload_ok(
        client,
        _row("1.", f"STR-{house.id}"),
        _row("2.", "невідомо", day="20.05.2025"),
        name="b.csv",
    )
    assert second != first

    out2 = _outcome(client, second)

    assert out2["auto_confirmed"] == []
    assert _ids(out2["unmatched"]) == {_tx_by_doc(session, "2.").id}
    assert len(_outcome(client, first)["auto_confirmed"]) == 1


def test_every_credit_lands_in_exactly_one_place(client, session: Session) -> None:
    _admin(client, session)
    h1 = make_household(session, name="Plot 1")
    h2 = make_household(session, name="Іваненко")
    fid = _upload_ok(
        client,
        _row("1.", f"STR-{h1.id}"),  # auto
        _row("2.", "за світло Іваненко"),  # attention
        _row("3.", "невідомо"),  # unmatched
        _row("4.", "невідомо"),  # to dismiss
        _row("5.", "невідомо"),  # to confirm
    )
    client.post(f"/admin/bank-transactions/{_tx_by_doc(session, '4.').id}/dismiss")
    client.post(
        f"/admin/bank-transactions/{_tx_by_doc(session, '5.').id}/confirm",
        json={"lines": [{"household_id": h2.id, "amount_uah": "500.00"}]},
    )

    out = _outcome(client, fid)

    placed = [r["id"] for r in out["auto_confirmed"]]
    placed += [r["id"] for r in out["needs_attention"]]
    placed += [r["id"] for r in out["unmatched"]]
    assert len(placed) == len(set(placed)) == 3
    assert len(placed) + out["handled_count"] == 5


def test_file_without_credits_has_empty_outcome(client, session: Session) -> None:
    _admin(client, session)
    fid = _upload_ok(client, _row("1.", "відправлено", amount="-5.00"))

    out = _outcome(client, fid)

    assert out["auto_confirmed"] == []
    assert out["needs_attention"] == [] and out["unmatched"] == []
    assert out["handled_count"] == 0


def test_unknown_file_is_404(client, session: Session) -> None:
    _admin(client, session)
    res = client.get(f"{LIST}/999999/outcome")
    assert res.status_code == 404
    assert res.json()["detail"] == "bankStatementFileNotFound"


def test_recent_files_lists_newest_first(client, session: Session) -> None:
    _admin(client, session)
    a = _upload_ok(client, _row("1.", "x"), name="a.csv")
    b = _upload_ok(client, _row("2.", "x"), name="b.csv")
    c = _upload_ok(client, _row("3.", "x"), name="c.csv")
    assert [f["id"] for f in client.get(LIST).json()] == [c, b, a]
    assert client.get(LIST).json()[0]["original_filename"] == "c.csv"


def test_endpoints_reject_non_admin_and_anonymous(client, session: Session) -> None:
    assert client.get(LIST).status_code == 401
    assert client.get(f"{LIST}/1/outcome").status_code == 401
    authenticate(client, make_user(session))
    assert client.get(LIST).status_code == 403
    assert client.get(f"{LIST}/1/outcome").status_code == 403


def test_manual_payment_linked_to_credit_is_not_reported_automatic(
    client, session: Session
) -> None:
    admin = _admin(client, session)
    house = make_household(session)
    fid = _upload_ok(client, _row("1.", "невідомо"))
    tx = _tx_by_doc(session, "1.")
    # A null recorder, like a payment the automatic booking would write.
    payment = Payment(
        household_id=house.id,
        amount_uah=Decimal("500.00"),
        paid_on=tx.operation_date,
        method="transfer",
        recorded_by_user_id=None,
    )
    session.add(payment)
    session.flush()
    review_link(session, transaction_id=tx.id, payment_id=payment.id, actor_id=admin.id)

    out = _outcome(client, fid)

    assert out["auto_confirmed"] == []
    assert out["handled_count"] == 1
