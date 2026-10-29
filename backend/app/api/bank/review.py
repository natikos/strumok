"""Review queue for imported bank credits. A credit becomes payments only when
an admin confirms it; nothing here runs on import. The state of a credit is
derived (a live payment links to it, it is dismissed, or it is still queued),
and every state change locks the credit row first so two admins cannot
confirm or dismiss it twice."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, col, select

from app.core import audit
from app.core.bank_queue import queued_select
from app.core.domain.billing import KYIV_TZ
from app.core.ownership import owner_at
from app.core.time import utc_now
from app.db.models import BankTransaction, Household, OpeningBalance, Payment

LINK_WINDOW_DAYS = 5
DISMISS_REASON = "notResidentPayment"


class BankTransactionNotFoundError(Exception):
    pass


class BankTransactionResolvedError(Exception):
    """Already confirmed, linked or dismissed."""


class HouseholdNotFoundError(Exception):
    pass


class SplitInvalidError(Exception):
    """Empty split, repeated household, or amounts not summing to the credit."""


class BeforeOpeningBalanceError(Exception):
    """The credit predates a household's opening balance, which it is already in."""


class ManualPaymentNotLinkableError(Exception):
    pass


@dataclass(frozen=True)
class SplitLine:
    household_id: int
    amount_uah: Decimal


@dataclass(frozen=True)
class QueueItem:
    transaction: BankTransaction
    link_candidates: list[Payment]


def _lock(session: Session, transaction_id: int) -> BankTransaction:
    transaction = session.exec(
        select(BankTransaction)
        .where(BankTransaction.id == transaction_id)
        .with_for_update()
    ).first()
    if transaction is None:
        raise BankTransactionNotFoundError
    return transaction


def _live_payments(session: Session, transaction_id: int) -> list[Payment]:
    return list(
        session.exec(
            select(Payment)
            .where(Payment.bank_transaction_id == transaction_id)
            .where(col(Payment.voided_at).is_(None))
        )
    )


def _ensure_unresolved(session: Session, transaction: BankTransaction) -> None:
    if transaction.dismissed_at is not None or _live_payments(session, transaction.id):
        raise BankTransactionResolvedError


def _link_candidates(session: Session, transaction: BankTransaction) -> list[Payment]:
    return list(
        session.exec(
            select(Payment)
            .where(Payment.method == "transfer")
            .where(col(Payment.bank_transaction_id).is_(None))
            .where(col(Payment.voided_at).is_(None))
            .where(Payment.amount_uah == transaction.amount_uah)
            .where(
                Payment.paid_on
                >= transaction.operation_date - timedelta(days=LINK_WINDOW_DAYS)
            )
            .where(
                Payment.paid_on
                <= transaction.operation_date + timedelta(days=LINK_WINDOW_DAYS)
            )
            .order_by(col(Payment.paid_on), col(Payment.id))
        )
    )


def list_queue(session: Session) -> list[QueueItem]:
    rows = session.exec(
        queued_select().order_by(
            col(BankTransaction.operation_date), col(BankTransaction.id)
        )
    )
    return [QueueItem(row, _link_candidates(session, row)) for row in rows]


def _end_of_day(day: date) -> datetime:
    """The last instant of `day` in Kyiv, as naive UTC like every timestamp."""
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=KYIV_TZ)
    return end.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(microseconds=1)


def confirm(
    session: Session,
    *,
    transaction_id: int,
    lines: list[SplitLine],
    actor_id: int,
) -> list[Payment]:
    transaction = _lock(session, transaction_id)
    _ensure_unresolved(session, transaction)

    household_ids = [line.household_id for line in lines]
    if (
        not lines
        or len(set(household_ids)) != len(household_ids)
        or any(line.amount_uah <= 0 for line in lines)
        or sum((line.amount_uah for line in lines), Decimal("0"))
        != transaction.amount_uah
    ):
        raise SplitInvalidError

    payments: list[Payment] = []
    for line in lines:
        household = session.get(Household, line.household_id)
        if household is None:
            raise HouseholdNotFoundError
        opening = session.exec(
            select(OpeningBalance).where(OpeningBalance.household_id == household.id)
        ).first()
        if opening is not None and transaction.operation_date <= opening.as_of:
            raise BeforeOpeningBalanceError
        payments.append(
            Payment(
                household_id=household.id,
                owner_user_id=owner_at(
                    session, household, _end_of_day(transaction.operation_date)
                ),
                amount_uah=line.amount_uah,
                paid_on=transaction.operation_date,
                method="transfer",
                note=None,
                recorded_by_user_id=actor_id,
                bank_transaction_id=transaction.id,
            )
        )
    session.add_all(payments)
    session.flush()
    audit.record(
        session,
        actor_user_id=actor_id,
        action="bankTransactionConfirmed",
        entity_type="bank_transaction",
        entity_id=transaction.id,
        after={
            "payments": [
                {
                    "payment_id": payment.id,
                    "household_id": payment.household_id,
                    "amount_uah": payment.amount_uah,
                }
                for payment in payments
            ]
        },
    )
    session.commit()
    for payment in payments:
        session.refresh(payment)
    return payments


def link(
    session: Session, *, transaction_id: int, payment_id: int, actor_id: int
) -> Payment:
    transaction = _lock(session, transaction_id)
    _ensure_unresolved(session, transaction)
    payment = session.exec(
        select(Payment).where(Payment.id == payment_id).with_for_update()
    ).first()
    if (
        payment is None
        or payment.method != "transfer"
        or payment.voided_at is not None
        or payment.bank_transaction_id is not None
        or payment.amount_uah != transaction.amount_uah
        or abs((payment.paid_on - transaction.operation_date).days) > LINK_WINDOW_DAYS
    ):
        raise ManualPaymentNotLinkableError
    payment.bank_transaction_id = transaction.id
    session.add(payment)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="bankTransactionLinked",
        entity_type="bank_transaction",
        entity_id=transaction.id,
        household_id=payment.household_id,
        after={"payment_id": payment.id, "amount_uah": payment.amount_uah},
    )
    session.commit()
    session.refresh(payment)
    return payment


def dismiss(session: Session, *, transaction_id: int, actor_id: int) -> BankTransaction:
    transaction = _lock(session, transaction_id)
    _ensure_unresolved(session, transaction)
    transaction.dismissed_at = utc_now()
    transaction.dismissed_by_user_id = actor_id
    transaction.dismiss_reason = DISMISS_REASON
    session.add(transaction)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="bankTransactionDismissed",
        entity_type="bank_transaction",
        entity_id=transaction.id,
        after={"amount_uah": transaction.amount_uah},
    )
    session.commit()
    session.refresh(transaction)
    return transaction
