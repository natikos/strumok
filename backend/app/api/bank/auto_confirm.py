"""Books a freshly imported credit as a payment without an admin step, but only
when its purpose carries exactly one `STR-<id>` reference to an active
household. Anything less certain (no, several or unknown references, a date the household has already settled) stays in the review
queue for an admin."""

from decimal import Decimal

from sqlmodel import Session, col, select

from app.api.bank.matching.matcher import match
from app.api.bank.review import (
    BankTransactionResolvedError,
    BeforeOpeningBalanceError,
    SplitInvalidError,
    SplitLine,
    confirm,
)
from app.core.bank_queue import queued_select
from app.db.models import BankTransaction, Household


def auto_confirm_new_credits(session: Session, *, file_id: int) -> int:
    """Confirms the file's queued credits that reference a single household.
    Returns how many were booked. Booked payments have no recorder: the audit
    entry's missing actor marks them as automatic."""
    households = session.exec(select(Household).where(col(Household.is_active))).all()
    queued = session.exec(
        queued_select().where(BankTransaction.first_file_id == file_id)
    ).all()

    booked = 0
    for transaction in queued:
        suggestions = match(transaction.purpose, households)
        if len(suggestions) != 1 or transaction.amount_uah <= Decimal("0"):
            continue
        try:
            confirm(
                session,
                transaction_id=transaction.id,
                lines=[SplitLine(suggestions[0].household_id, transaction.amount_uah)],
                actor_id=None,
            )
        except (
            BeforeOpeningBalanceError,
            SplitInvalidError,
            BankTransactionResolvedError,
        ):
            session.rollback()
            continue
        booked += 1
    return booked


def queued_count(session: Session, *, file_id: int) -> int:
    return len(
        session.exec(
            queued_select().where(BankTransaction.first_file_id == file_id)
        ).all()
    )
