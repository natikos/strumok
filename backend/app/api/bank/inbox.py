import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr

from sqlmodel import Session, col, select

from app.api.bank.service import (
    MAX_BYTES,
    BankStatementError,
    PaymentDetailsMissingError,
    StatementNotCsvError,
    StatementTooLargeError,
    import_statement,
)
from app.api.billing.payment_details import get_payment_details
from app.api.push.billing_notifications import notify_bank_queue, notify_shortfall
from app.core.config import ImapSettings, settings
from app.core.domain.bank_statement import parse_statement
from app.core.time import utc_now
from app.db.models import BankMailFetch

logger = logging.getLogger(__name__)

# A statement is a CSV under 1 MB; anything much bigger than that as a whole
# message is not one, so it is rejected without being downloaded.
MAX_MESSAGE_BYTES = 5 * MAX_BYTES
LOOKBACK = timedelta(days=45)

_SIZE = re.compile(rb"RFC822\.SIZE (\d+)")


class InboxNotConfiguredError(Exception):
    pass


class InboxUnavailableError(Exception):
    pass


@dataclass
class InboxResult:
    received: int = 0
    imported: int = 0
    rejected: int = 0
    credits_new: int = 0
    file_ids: list[int] = field(default_factory=list)


def _aligned(signer: str, domain: str) -> bool:
    signer = signer.lower().lstrip("@")
    return signer == domain or signer.endswith("." + domain)


def _sender_authenticated(msg: EmailMessage, address: str, authserv_id: str) -> bool:
    """Trusts only the topmost Authentication-Results header, written by the
    receiving server named `authserv_id`. Each result is parsed by method, so
    sender-controlled text elsewhere in the header (e.g. smtp.mailfrom) cannot
    pass for a verdict."""
    header = msg.get("Authentication-Results")
    if header is None:
        return False
    text = re.sub(r"\([^)]*\)", " ", str(header))
    first, *results = [part.strip() for part in text.split(";")]
    if first.split(" ")[0].lower() != authserv_id.lower():
        return False
    domain = address.rpartition("@")[2]
    for result in results:
        tokens = result.split()
        if not tokens:
            continue
        method, _, verdict = tokens[0].partition("=")
        if verdict.lower() != "pass":
            continue
        props = dict(t.lower().split("=", 1) for t in tokens[1:] if "=" in t)
        if method.lower() == "dmarc" and props.get("header.from") == domain:
            return True
        if method.lower() == "dkim":
            signer = (
                props.get("header.d") or props.get("header.i", "").rpartition("@")[2]
            )
            if signer and _aligned(signer, domain):
                return True
    return False


def _csv_attachments(msg: EmailMessage) -> list[tuple[str, bytes]]:
    found = []
    for part in msg.iter_attachments():
        name = part.get_filename() or ""
        if name.lower().endswith(".csv"):
            found.append((name, part.get_payload(decode=True) or b""))
    return found


def _record(
    session: Session,
    result: InboxResult,
    *,
    message_id: str,
    status: str,
    reason: str | None = None,
    file_id: int | None = None,
) -> None:
    session.add(
        BankMailFetch(
            message_id=message_id[:512], status=status, reason=reason, file_id=file_id
        )
    )
    session.commit()
    result.received += 1
    if status == "imported":
        result.imported += 1
    elif status == "rejected":
        result.rejected += 1


def process_message(
    session: Session,
    result: InboxResult,
    *,
    message_id: str,
    raw: bytes,
    allowed_senders: list[str],
    authserv_id: str = "mx.google.com",
) -> None:
    """Imports every CSV attachment of one message and records the verdict.
    Imported rows land in the review queue like an upload; nothing is
    confirmed here."""

    def reject(reason: str) -> None:
        _record(
            session, result, message_id=message_id, status="rejected", reason=reason
        )

    msg = message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)
    address = parseaddr(str(msg.get("From", "")))[1].lower()
    if address not in allowed_senders:
        return reject("senderNotAllowed")
    if not _sender_authenticated(msg, address, authserv_id):
        return reject("senderNotAuthenticated")
    attachments = _csv_attachments(msg)
    if not attachments:
        return reject("noCsvAttachment")

    # Validate every attachment first: import_statement commits per file, so a
    # bad second attachment must not leave the message half imported.
    details = get_payment_details(session)
    if details is None:
        return reject("paymentDetailsMissing")
    for name, data in attachments:
        if len(data) > MAX_BYTES:
            return reject("bankStatementTooLarge")
        try:
            parse_statement(data, details.iban)
        except BankStatementError as exc:
            return reject(exc.code)

    file_id: int | None = None
    new_files = 0
    for name, data in attachments:
        try:
            imported = import_statement(
                session, actor_id=None, filename=name, data=data
            )
        except StatementTooLargeError:
            return reject("bankStatementTooLarge")
        except StatementNotCsvError:
            return reject("bankStatementNotCsv")
        except PaymentDetailsMissingError:
            return reject("paymentDetailsMissing")
        except BankStatementError as exc:
            return reject(exc.code)
        if not imported.already_imported:
            new_files += 1
            file_id = imported.file_id
            result.credits_new += imported.credits_new
            result.file_ids.append(imported.file_id)
    if new_files:
        _record(
            session, result, message_id=message_id, status="imported", file_id=file_id
        )
    else:
        _record(
            session,
            result,
            message_id=message_id,
            status="received",
            reason="alreadyImported",
        )


def _message_id(header: bytes) -> str | None:
    msg = message_from_bytes(header, policy=policy.default)
    value = str(msg.get("Message-ID", "")).strip()
    return value or None


def _fetch_data(client: imaplib.IMAP4, uid: bytes, spec: str) -> list:
    status, data = client.uid("FETCH", uid.decode(), spec)
    if status != "OK":
        raise InboxUnavailableError
    return [item for item in data if isinstance(item, tuple)]


def _check(session: Session, client: imaplib.IMAP4, cfg: ImapSettings) -> InboxResult:
    result = InboxResult()
    since = (utc_now() - LOOKBACK).strftime("%d-%b-%Y")
    uids: set[bytes] = set()
    for sender in cfg.allowed_senders:
        status, data = client.uid("SEARCH", "FROM", f'"{sender}"', "SINCE", since)
        if status != "OK":
            raise InboxUnavailableError
        uids.update(data[0].split())

    for uid in sorted(uids, key=int):
        message_id = None
        try:
            head = _fetch_data(
                client, uid, "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"
            )[0]
            message_id = _message_id(head[1])
            if message_id is None:
                continue
            known = session.exec(
                select(BankMailFetch.id).where(
                    col(BankMailFetch.message_id) == message_id[:512]
                )
            ).first()
            if known is not None:
                continue
            size = _SIZE.search(head[0])
            if size is not None and int(size.group(1)) > MAX_MESSAGE_BYTES:
                _record(
                    session,
                    result,
                    message_id=message_id,
                    status="rejected",
                    reason="bankStatementTooLarge",
                )
                continue
            raw = _fetch_data(client, uid, "(BODY.PEEK[])")[0][1]
            process_message(
                session,
                result,
                message_id=message_id,
                raw=raw,
                allowed_senders=cfg.allowed_senders,
                authserv_id=cfg.authserv_id,
            )
        except InboxUnavailableError:
            raise
        except (imaplib.IMAP4.error, OSError) as exc:
            raise InboxUnavailableError from exc
        except Exception as exc:
            # One bad message must not hide the rest. Only the type is logged:
            # parser errors can carry statement content.
            session.rollback()
            logger.error(
                "Bank inbox message %s failed: %s", uid.decode(), type(exc).__name__
            )
            if message_id is None:
                continue
            _record(
                session,
                result,
                message_id=message_id,
                status="rejected",
                reason="processingFailed",
            )
    return result


def check_inbox(session: Session) -> InboxResult:
    """Fetches new messages from the allow-listed senders. Raises
    `InboxNotConfiguredError` when the mailbox is not set up and
    `InboxUnavailableError` when it cannot be reached."""
    cfg = settings.imap
    if not cfg.enabled:
        raise InboxNotConfiguredError
    try:
        with imaplib.IMAP4_SSL(cfg.host, timeout=30) as client:
            client.login(cfg.user, cfg.password.get_secret_value())
            status, _ = client.select(cfg.folder, readonly=True)
            if status != "OK":
                raise InboxUnavailableError
            result = _check(session, client, cfg)
    except (imaplib.IMAP4.error, OSError) as exc:
        # The error text can echo server replies; log the type only.
        logger.error("Bank inbox unreachable: %s", type(exc).__name__)
        raise InboxUnavailableError from exc

    for file_id in result.file_ids:
        try:
            notify_bank_queue(session=session, file_id=file_id)
        except Exception:
            logger.exception("Bank queue notification failed")
    if result.file_ids:
        try:
            notify_shortfall(session=session)
        except Exception:
            logger.exception("Shortfall notification failed")
    return result
