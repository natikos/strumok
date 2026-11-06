from sqlmodel import Session

from app.core import audit
from app.core.time import utc_now
from app.db.models import PaymentDetails

IBAN_LENGTH = 29


EDRPOU_LENGTH = 8


class InvalidIbanError(Exception):
    pass


class InvalidEdrpouError(Exception):
    pass


def normalize_edrpou(raw: str | None) -> str | None:
    """A blank value clears the code; otherwise it must be the 8 digits of a
    legal entity's EDRPOU, since a typo would make residents' bank apps reject
    or misroute the transfer."""
    code = "".join((raw or "").split())
    if not code:
        return None
    if len(code) != EDRPOU_LENGTH or not (code.isascii() and code.isdigit()):
        raise InvalidEdrpouError
    return code


def normalize_iban(raw: str) -> str:
    """Upper-cases and strips spaces, then checks a Ukrainian IBAN's shape and
    ISO 13616 mod-97 checksum. A typo here would send every payment to the wrong
    account, so a bad value is rejected rather than stored."""
    iban = "".join(raw.split()).upper()
    if len(iban) != IBAN_LENGTH or not iban.startswith("UA") or not iban.isalnum():
        raise InvalidIbanError
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(digits) % 97 != 1:
        raise InvalidIbanError
    return iban


def get_payment_details(session: Session) -> PaymentDetails | None:
    return session.get(PaymentDetails, 1)


def set_payment_details(
    session: Session,
    *,
    actor_id: int,
    iban: str,
    recipient_name: str,
    edrpou: str | None = None,
) -> PaymentDetails:
    normalized = normalize_iban(iban)
    code = normalize_edrpou(edrpou)
    recipient = recipient_name.strip()
    row = session.get(PaymentDetails, 1)
    before = (
        {
            "iban": row.iban,
            "recipient_name": row.recipient_name,
            "edrpou": row.edrpou,
        }
        if row
        else None
    )
    if row is None:
        row = PaymentDetails(
            id=1, iban=normalized, recipient_name=recipient, edrpou=code
        )
    else:
        row.iban = normalized
        row.recipient_name = recipient
        row.edrpou = code
        row.updated_at = utc_now()
    row.updated_by_user_id = actor_id
    session.add(row)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="payment_details.set",
        entity_type="payment_details",
        entity_id=1,
        before=before,
        after={"iban": normalized, "recipient_name": recipient, "edrpou": code},
    )
    session.commit()
    session.refresh(row)
    return row
