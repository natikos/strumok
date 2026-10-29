"""Bank statement ingest from the mailbox (issue #257). Messages are synthetic."""

from email.message import EmailMessage
from unittest.mock import patch

import pytest
from pydantic import SecretStr
from sqlmodel import Session, func, select

from app.api.bank import inbox
from app.core.config import ImapSettings
from app.db.models import (
    BankMailFetch,
    BankStatementFile,
    BankTransaction,
    PaymentDetails,
)
from tests.factories import authenticate, make_user
from tests.test_bank_import import OWN, _csv, _row

SENDER = "accountant@example.com"
AUTH_PASS = "mx.google.com; dmarc=pass header.from=example.com"


def _mail(
    *,
    sender: str = SENDER,
    auth: str | None = AUTH_PASS,
    attachment: tuple[str, bytes] | None = ("statement.csv", _csv(_row())),
) -> bytes:
    msg = EmailMessage()
    msg["From"] = f"Accountant <{sender}>"
    msg["To"] = "coop@example.com"
    msg["Subject"] = "statement"
    if auth is not None:
        msg["Authentication-Results"] = auth
    msg.set_content("attached")
    if attachment is not None:
        name, data = attachment
        msg.add_attachment(data, maintype="text", subtype="csv", filename=name)
    return msg.as_bytes()


def _process(session: Session, raw: bytes, message_id: str = "<m1@x>"):
    result = inbox.InboxResult()
    inbox.process_message(
        session, result, message_id=message_id, raw=raw, allowed_senders=[SENDER]
    )
    return result


def _details(session: Session) -> None:
    session.add(PaymentDetails(id=1, iban=OWN, recipient_name="Co-op"))
    session.flush()


def _fetch(session: Session) -> BankMailFetch:
    return session.exec(select(BankMailFetch)).one()


def test_valid_message_is_imported_into_the_queue(session: Session) -> None:
    _details(session)
    result = _process(session, _mail())
    assert (result.received, result.imported, result.rejected) == (1, 1, 0)
    assert result.credits_new == 1
    row = _fetch(session)
    assert row.status == "imported" and row.file_id is not None
    assert session.exec(select(func.count()).select_from(BankTransaction)).one() == 1
    assert session.exec(select(BankStatementFile)).one().uploaded_by_user_id is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"sender": "evil@example.com"}, "senderNotAllowed"),
        ({"auth": None}, "senderNotAuthenticated"),
        ({"auth": "mx.google.com; dkim=fail; dmarc=fail"}, "senderNotAuthenticated"),
        (
            {
                "auth": "mx.google.com; spf=pass smtp.mailfrom=dmarc=pass@evil.org;"
                " dmarc=fail header.from=example.com"
            },
            "senderNotAuthenticated",
        ),
        (
            {"auth": "mx.google.com; dmarc=pass header.from=evil.org"},
            "senderNotAuthenticated",
        ),
        (
            {"auth": "attacker.test; dmarc=pass header.from=example.com"},
            "senderNotAuthenticated",
        ),
        (
            {"auth": "mx.google.com; dkim=pass header.i=@other.org"},
            "senderNotAuthenticated",
        ),
        ({"attachment": None}, "noCsvAttachment"),
        ({"attachment": ("statement.pdf", b"x")}, "noCsvAttachment"),
        ({"attachment": ("s.csv", b"not;a;statement\n1;2;3")}, "bankStatementInvalid"),
        (
            {"attachment": ("s.csv", b"x" * (1024 * 1024 + 1))},
            "bankStatementTooLarge",
        ),
    ],
)
def test_rejections_record_a_reason_and_import_nothing(
    session: Session, kwargs: dict, reason: str
) -> None:
    _details(session)
    result = _process(session, _mail(**kwargs))
    assert (result.imported, result.rejected) == (0, 1)
    row = _fetch(session)
    assert (row.status, row.reason) == ("rejected", reason)
    assert session.exec(select(func.count()).select_from(BankTransaction)).one() == 0


def test_dkim_pass_for_sender_domain_is_accepted(session: Session) -> None:
    _details(session)
    result = _process(
        session, _mail(auth="mx.google.com; dkim=pass header.i=@mail.example.com")
    )
    assert result.imported == 1


def test_resent_statement_is_received_not_duplicated(session: Session) -> None:
    _details(session)
    _process(session, _mail(), "<m1@x>")
    again = _process(session, _mail(), "<m2@x>")
    assert (again.received, again.imported, again.credits_new) == (1, 0, 0)
    rows = session.exec(select(BankMailFetch).order_by(BankMailFetch.id)).all()
    assert [(r.status, r.reason) for r in rows] == [
        ("imported", None),
        ("received", "alreadyImported"),
    ]
    assert session.exec(select(func.count()).select_from(BankTransaction)).one() == 1


def test_missing_payment_details_is_a_recorded_rejection(session: Session) -> None:
    _process(session, _mail())
    assert _fetch(session).reason == "paymentDetailsMissing"


class _FakeImap:
    def __init__(self, messages: dict[bytes, tuple[str, bytes]]) -> None:
        self.messages = messages

    def uid(self, command: str, *args: str):
        if command == "SEARCH":
            return "OK", [b" ".join(self.messages)]
        uid = args[0].encode()
        message_id, raw = self.messages[uid]
        if "HEADER" in args[1]:
            head = f"Message-ID: {message_id}\r\n\r\n".encode()
            return "OK", [(b"1 (RFC822.SIZE %d" % len(raw), head), b")"]
        return "OK", [(b"1 (BODY[]", raw), b")"]


def _cfg() -> ImapSettings:
    return ImapSettings(
        user="coop@example.com",
        password=SecretStr("app-password"),
        allowed_senders=[SENDER],  # type: ignore[arg-type]
    )


def test_fetch_skips_known_messages_and_survives_a_bad_one(session: Session) -> None:
    _details(session)
    good = _mail()
    client = _FakeImap(
        {
            b"1": ("<a@x>", good),
            b"2": ("<b@x>", b"\xff\xfe broken"),
            b"3": ("<c@x>", good),
        }
    )
    first = inbox._check(session, client, _cfg())  # type: ignore[arg-type]
    assert (first.imported, first.rejected, first.received) == (1, 1, 3)
    second = inbox._check(session, client, _cfg())  # type: ignore[arg-type]
    assert second.received == 0


def test_oversized_message_is_rejected_without_download(session: Session) -> None:
    class Big(_FakeImap):
        def uid(self, command: str, *args: str):
            if command == "FETCH" and "HEADER" not in args[1]:
                raise AssertionError("body must not be downloaded")
            status, data = super().uid(command, *args)
            if command == "FETCH":
                data[0] = (b"1 (RFC822.SIZE 99999999", data[0][1])
            return status, data

    result = inbox._check(
        session,
        Big({b"1": ("<big@x>", _mail())}),
        _cfg(),  # type: ignore[arg-type]
    )
    assert result.rejected == 1
    assert _fetch(session).reason == "bankStatementTooLarge"


def test_check_requires_configuration(session: Session) -> None:
    with pytest.raises(inbox.InboxNotConfiguredError):
        inbox.check_inbox(session)


def test_unreachable_mailbox_raises_unavailable(session: Session) -> None:
    with (
        patch.object(inbox.settings, "imap", _cfg()),
        patch("app.api.bank.inbox.imaplib.IMAP4_SSL", side_effect=OSError("down")),
        pytest.raises(inbox.InboxUnavailableError),
    ):
        inbox.check_inbox(session)


def test_password_is_not_exposed_in_settings_repr() -> None:
    assert "app-password" not in repr(_cfg())
    assert ImapSettings.model_fields["password"].annotation is SecretStr


def test_check_inbox_route(client, session: Session) -> None:
    authenticate(client, make_user(session))
    assert client.post("/admin/bank-statements/check-inbox").status_code == 403
    authenticate(client, make_user(session, is_admin=True))
    res = client.post("/admin/bank-statements/check-inbox")
    assert (res.status_code, res.json()["detail"]) == (422, "inboxNotConfigured")
    with (
        patch.object(inbox.settings, "imap", _cfg()),
        patch("app.api.bank.inbox.imaplib.IMAP4_SSL", side_effect=OSError("down")),
    ):
        res = client.post("/admin/bank-statements/check-inbox")
    assert (res.status_code, res.json()["detail"]) == (502, "inboxUnavailable")


def _two(second: bytes) -> bytes:
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["Authentication-Results"] = AUTH_PASS
    msg.set_content("attached")
    msg.add_attachment(_csv(_row()), maintype="text", subtype="csv", filename="a.csv")
    msg.add_attachment(second, maintype="text", subtype="csv", filename="b.csv")
    return msg.as_bytes()


def test_bad_second_attachment_imports_nothing(session: Session) -> None:
    _details(session)
    result = _process(session, _two(b"garbage"))
    assert (result.imported, result.rejected) == (0, 1)
    assert session.exec(select(func.count()).select_from(BankStatementFile)).one() == 0


def test_two_valid_attachments_are_both_imported(session: Session) -> None:
    _details(session)
    result = _process(session, _two(_csv(_row("2.", "21.05.2025"))))
    assert (result.imported, result.credits_new) == (1, 2)
    assert session.exec(select(func.count()).select_from(BankStatementFile)).one() == 2


def test_unexpected_failure_is_recorded_without_content_in_log(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    _details(session)
    client = _FakeImap({b"1": ("<a@x>", _mail())})
    with patch(
        "app.api.bank.inbox.process_message", side_effect=ValueError("secret payer")
    ):
        result = inbox._check(session, client, _cfg())  # type: ignore[arg-type]
    assert result.rejected == 1
    assert _fetch(session).reason == "processingFailed"
    assert "secret payer" not in caplog.text and "ValueError" in caplog.text


def test_imap_error_mid_run_is_unavailable(session: Session) -> None:
    import imaplib

    class Dropped(_FakeImap):
        def uid(self, command: str, *args: str):
            if command == "FETCH":
                raise imaplib.IMAP4.abort("socket error")
            return super().uid(command, *args)

    with pytest.raises(inbox.InboxUnavailableError):
        inbox._check(session, Dropped({b"1": ("<a@x>", _mail())}), _cfg())  # type: ignore[arg-type]
