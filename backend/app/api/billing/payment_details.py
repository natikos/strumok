from sqlmodel import Session

from app.core import audit
from app.core.time import utc_now
from app.db.models import PaymentDetails

IBAN_LENGTH = 29


class InvalidIbanError(Exception):
    pass


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
    session: Session, *, actor_id: int, iban: str, recipient_name: str
) -> PaymentDetails:
    normalized = normalize_iban(iban)
    recipient = recipient_name.strip()
    row = session.get(PaymentDetails, 1)
    before = {"iban": row.iban, "recipient_name": row.recipient_name} if row else None
    if row is None:
        row = PaymentDetails(id=1, iban=normalized, recipient_name=recipient)
    else:
        row.iban = normalized
        row.recipient_name = recipient
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
        after={"iban": normalized, "recipient_name": recipient},
    )
    session.commit()
    session.refresh(row)
    return row
