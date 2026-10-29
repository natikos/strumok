"""Shortfall: whether the bank statement has reached the due date of the
latest app-closed period, and who still owes once it has. Spreadsheet-backfilled
periods are closed without a `closed_by_user_id`, so they never open a window."""

from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal

from sqlmodel import Session, col, select

from app.core.bank_queue import has_queued_through
from app.api.billing.bank_coverage import get_coverage
from app.api.billing.payments import ZERO, get_balance
from app.core.domain.billing import KYIV_TZ
from app.core.ownership import owner_scope
from app.db.models import BillingPeriod, Household

DUE_DAY = 20


@dataclass(frozen=True)
class ShortfallWindow:
    period: str
    due_date: date


def _next_due(after: date) -> date:
    """The first 20th on or after `after`."""
    if after.day <= DUE_DAY:
        return after.replace(day=DUE_DAY)
    year, month = (
        (after.year + 1, 1) if after.month == 12 else (after.year, after.month + 1)
    )
    return date(year, month, DUE_DAY)


def _closed_windows(session: Session) -> list[ShortfallWindow]:
    """One window per app-closed period, newest first."""
    windows = []
    for row in session.exec(
        select(BillingPeriod)
        .where(BillingPeriod.status == "closed")
        .where(col(BillingPeriod.closed_by_user_id).is_not(None))
        .order_by(col(BillingPeriod.period).desc())
    ):
        year, month = (int(part) for part in row.period.split("-"))
        earliest = date(year + (month == 12), month % 12 + 1, 1)
        if row.closed_at is not None:
            earliest = max(
                earliest, row.closed_at.replace(tzinfo=UTC).astimezone(KYIV_TZ).date()
            )
        windows.append(ShortfallWindow(period=row.period, due_date=_next_due(earliest)))
    return windows


def latest_window(session: Session) -> ShortfallWindow | None:
    windows = _closed_windows(session)
    return windows[0] if windows else None


def settled_window(session: Session) -> ShortfallWindow | None:
    """The newest app-closed period whose due date the statement covers, with
    no credit dated on or before that date still waiting in the review queue,
    else None. Closing a later period does not hide an earlier one that is
    already past due."""
    covered, _ = get_coverage(session)
    if covered is None:
        return None
    for window in _closed_windows(session):
        if window.due_date <= covered:
            if has_queued_through(session, window.due_date):
                return None
            return window
    return None


def household_shortfall(
    session: Session, window: ShortfallWindow | None, household: Household
) -> Decimal:
    """What the current owner still owes on `household` for periods up to the
    window's. Payments settle the oldest debt first, so the overdue part is
    the balance minus what is unpaid on later periods; zero when no window."""
    if window is None:
        return ZERO
    balance = get_balance(
        session=session,
        household_id=household.id,
        owner_user_id=owner_scope(session, household.id, household.user_id)
        if household.user_id
        else None,
    )
    later_unpaid = sum(
        (
            max(p.due_uah - p.paid_uah, ZERO)
            for p in balance.periods
            if p.period > window.period
        ),
        ZERO,
    )
    return max(balance.balance_uah - later_unpaid, ZERO)


def shortfall_for_household_id(
    session: Session, window: ShortfallWindow | None, household_id: int
) -> Decimal:
    household = session.get(Household, household_id)
    if household is None:
        return ZERO
    return household_shortfall(session, window, household)
