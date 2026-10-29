import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.billing.payment_details import get_payment_details
from app.core import audit
from app.core.domain.bank_statement import BankStatementError, parse_statement
from app.db.models import BankStatementFile, BankTransaction

MAX_BYTES = 1024 * 1024


class StatementTooLargeError(Exception):
    pass


class StatementNotCsvError(Exception):
    pass


@dataclass(frozen=True)
class ImportResult:
    file_id: int
    already_imported: bool
    credits_new: int
    credits_duplicate: int
    debits_skipped: int
    covered_through: date


def _overall_coverage(session: Session) -> date:
    return session.exec(select(func.max(BankStatementFile.covered_through))).one()  # type: ignore[return-value]


def _existing(session: Session, sha256: str) -> ImportResult | None:
    row = session.exec(
        select(BankStatementFile).where(BankStatementFile.sha256 == sha256)
    ).first()
    if row is None:
        return None
    return ImportResult(
        file_id=row.id,
        already_imported=True,
        credits_new=0,
        credits_duplicate=row.credits_new + row.credits_duplicate,
        debits_skipped=row.debits_skipped,
        covered_through=_overall_coverage(session),
    )


def import_statement(
    session: Session, *, actor_id: int, filename: str, data: bytes
) -> ImportResult:
    """Stores a statement's credits idempotently. Re-uploading identical bytes
    or a file overlapping an earlier one adds no duplicate rows. Raises
    `BankStatementError` for content problems; nothing is written then."""
    if not filename.lower().endswith(".csv"):
        raise StatementNotCsvError
    if len(data) > MAX_BYTES:
        raise StatementTooLargeError

    sha256 = hashlib.sha256(data).hexdigest()
    if (found := _existing(session, sha256)) is not None:
        return found

    details = get_payment_details(session)
    parsed = parse_statement(data, details.iban if details else None)

    file = BankStatementFile(
        sha256=sha256,
        original_filename=filename[:255],
        encoding=parsed.encoding,
        account_iban=parsed.account_iban,
        first_operation_date=parsed.first_operation_date,
        last_operation_date=parsed.last_operation_date,
        covered_through=parsed.last_operation_date,
        rows_total=parsed.rows_total,
        credits_new=0,
        credits_duplicate=0,
        debits_skipped=parsed.debits_skipped,
        uploaded_by_user_id=actor_id,
    )
    session.add(file)
    try:
        session.flush()
    except IntegrityError:
        # A concurrent upload of the same bytes won the unique sha256.
        session.rollback()
        found = _existing(session, sha256)
        if found is None:
            raise
        return found

    new = 0
    for credit in parsed.credits:
        inserted = session.exec(
            insert(BankTransaction)
            .values(
                document_number=credit.document_number,
                operation_date=credit.operation_date,
                amount_uah=credit.amount_uah,
                payer_iban=credit.payer_iban,
                payer_name=credit.payer_name,
                purpose=credit.purpose,
                first_file_id=file.id,
            )
            .on_conflict_do_nothing(constraint="uq_bank_transactions_dedupe")
            .returning(col(BankTransaction.id))
        ).first()
        if inserted is not None:
            new += 1
    file.credits_new = new
    file.credits_duplicate = len(parsed.credits) - new
    session.add(file)

    audit.record(
        session,
        actor_user_id=actor_id,
        action="bank_statement.import",
        entity_type="bank_statement_file",
        entity_id=file.id,
        after={
            "rows_total": file.rows_total,
            "credits_new": file.credits_new,
            "credits_duplicate": file.credits_duplicate,
            "debits_skipped": file.debits_skipped,
            "first_operation_date": file.first_operation_date,
            "last_operation_date": file.last_operation_date,
        },
    )
    session.commit()
    return ImportResult(
        file_id=file.id,
        already_imported=False,
        credits_new=file.credits_new,
        credits_duplicate=file.credits_duplicate,
        debits_skipped=file.debits_skipped,
        covered_through=_overall_coverage(session),
    )


__all__ = [
    "BankStatementError",
    "ImportResult",
    "StatementNotCsvError",
    "StatementTooLargeError",
    "import_statement",
]
