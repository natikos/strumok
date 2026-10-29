"""Which bank credits are still waiting in the review queue. Shared by the
review routes and the shortfall check; derived, never stored."""

from datetime import date

from sqlmodel import Session, col, select

from app.db.models import BankTransaction, Payment


def queued_select():
    live = select(Payment.bank_transaction_id).where(
        col(Payment.bank_transaction_id).is_not(None),
        col(Payment.voided_at).is_(None),
    )
    return (
        select(BankTransaction)
        .where(col(BankTransaction.dismissed_at).is_(None))
        .where(col(BankTransaction.id).not_in(live))
    )


def has_queued_through(session: Session, day: date) -> bool:
    """True while an unresolved credit dated on or before `day` is queued."""
    return (
        session.exec(
            queued_select().where(BankTransaction.operation_date <= day).limit(1)
        ).first()
        is not None
    )
