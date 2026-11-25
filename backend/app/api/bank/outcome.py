"""What happened to each credit of one imported statement: booked by the
automatic confirmation, waiting with a suggestion, or waiting with none. All of
it is derived from existing rows. A credit belongs to the file that first
imported it, which is also the file the automatic confirmation ran on."""

from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.api.bank import review
from app.api.bank.matching import Suggestion, suggest_households
from app.core.bank_queue import queued_select
from app.db.models import AuditLog, BankStatementFile, BankTransaction, Payment

OUTCOME_FILE_LIMIT = 20


class StatementFileNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AutoConfirmed:
    transaction: BankTransaction
    payments: list[Payment]


@dataclass(frozen=True)
class Outcome:
    file: BankStatementFile
    auto_confirmed: list[AutoConfirmed]
    needs_attention: list[tuple[review.QueueItem, list[Suggestion]]]
    unmatched: list[tuple[review.QueueItem, list[Suggestion]]]
    handled_count: int


def recent_files(session: Session) -> list[BankStatementFile]:
    return list(
        session.exec(
            select(BankStatementFile)
            .order_by(
                col(BankStatementFile.uploaded_at).desc(),
                col(BankStatementFile.id).desc(),
            )
            .limit(OUTCOME_FILE_LIMIT)
        )
    )


def _automatic_ids(session: Session, transaction_ids: list[int]) -> set[int]:
    """Credits whose latest confirmation was written without an actor. The audit
    log is append-only, so unlike a null `recorded_by_user_id` (which linking an
    old payment could also leave) it says who really booked the credit. Only the
    latest row counts: an admin who voids an automatic payment and confirms the
    credit again has taken it over."""
    if not transaction_ids:
        return set()
    latest: dict[int, int | None] = {}
    rows = session.exec(
        select(AuditLog.entity_id, AuditLog.actor_user_id)
        .where(AuditLog.action == "bankTransactionConfirmed")
        .where(AuditLog.entity_type == "bank_transaction")
        .where(col(AuditLog.entity_id).in_(transaction_ids))
        .order_by(col(AuditLog.id).desc())
    )
    for entity_id, actor_id in rows:
        if entity_id is not None:
            latest.setdefault(entity_id, actor_id)
    return {entity_id for entity_id, actor_id in latest.items() if actor_id is None}


def file_outcome(session: Session, file_id: int) -> Outcome:
    file = session.get(BankStatementFile, file_id)
    if file is None:
        raise StatementFileNotFoundError

    transactions = list(
        session.exec(
            select(BankTransaction)
            .where(BankTransaction.first_file_id == file_id)
            .order_by(col(BankTransaction.operation_date), col(BankTransaction.id))
        )
    )
    ids = [t.id for t in transactions]
    live: dict[int, list[Payment]] = {}
    if ids:
        for payment in session.exec(
            select(Payment)
            .where(col(Payment.bank_transaction_id).in_(ids))
            .where(col(Payment.voided_at).is_(None))
            .order_by(col(Payment.id))
        ):
            if payment.bank_transaction_id is not None:
                live.setdefault(payment.bank_transaction_id, []).append(payment)

    automatic = _automatic_ids(session, [i for i in ids if i in live])
    queued_ids = {
        t.id
        for t in session.exec(
            queued_select().where(BankTransaction.first_file_id == file_id)
        )
    }

    auto = [AutoConfirmed(t, live[t.id]) for t in transactions if t.id in automatic]
    queued = [t for t in transactions if t.id in queued_ids]
    items = [review.QueueItem(t, review._link_candidates(session, t)) for t in queued]
    found = suggest_households(session, queued)

    paired = list(zip(items, found))
    return Outcome(
        file=file,
        auto_confirmed=auto,
        needs_attention=[p for p in paired if p[1]],
        unmatched=[p for p in paired if not p[1]],
        handled_count=len(transactions) - len(auto) - len(queued),
    )
