from datetime import date, datetime

from sqlmodel import Session, func, select

from app.core.domain.billing import kyiv_now
from app.db.models import BankStatementFile

# Statements arrive about days 1-6 and ~17, so the longest honest gap is a
# statement covering the 17th that is followed by one on the 6th (20 days).
STALE_AFTER_DAYS = 21


def get_coverage(session: Session) -> tuple[date | None, datetime | None]:
    """Latest `covered_through` and upload time across imported statements."""
    covered, uploaded = session.exec(
        select(
            func.max(BankStatementFile.covered_through),
            func.max(BankStatementFile.uploaded_at),
        )
    ).one()
    return covered, uploaded


def is_awaiting_statement(
    covered_through: date | None, today: date | None = None
) -> bool:
    """True when no statement was ever imported or the newest one is stale, so
    balances may not include recent payments."""
    if covered_through is None:
        return True
    reference = today if today is not None else kyiv_now().date()
    return (reference - covered_through).days > STALE_AFTER_DAYS
