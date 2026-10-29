"""Shortfall: whether the bank statement has reached the due date of the
latest app-closed period, and who still owes once it has. Spreadsheet-backfilled
periods are closed without a `closed_by_user_id`, so they never open a window."""

from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal

from sqlmodel import Session, col, select

from app.api.billing.bank_coverage import get_coverage
from app.api.billing.payments import get_balance
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


def latest_window(session: Session) -> ShortfallWindow | None:
    row = session.exec(
        select(BillingPeriod)
        .where(BillingPeriod.status == "closed")
        .where(col(BillingPeriod.closed_by_user_id).is_not(None))
        .order_by(col(BillingPeriod.period).desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    year, month = (int(part) for part in row.period.split("-"))
    first_of_next = date(year + (month == 12), month % 12 + 1, 1)
    earliest = first_of_next
    if row.closed_at is not None:
        earliest = max(
            earliest, row.closed_at.replace(tzinfo=UTC).astimezone(KYIV_TZ).date()
        )
    return ShortfallWindow(period=row.period, due_date=_next_due(earliest))


def settled_window(session: Session) -> ShortfallWindow | None:
    """The window once the statement covers its due date and no credit dated
    on or before it is still waiting in the review queue, else None."""
    # Deferred: the bank package imports the push notifications, which import this.
    from app.api.bank.review import has_queued_through

    window = latest_window(session)
    if window is None:
        return None
    covered, _ = get_coverage(session)
    if covered is None or covered < window.due_date:
        return None
    if has_queued_through(session, window.due_date):
        return None
    return window


def household_shortfall(
    session: Session, window: ShortfallWindow | None, household: Household
) -> Decimal:
    """What the current owner still owes on `household`; zero when no window."""
    if window is None:
        return Decimal("0.00")
    balance = get_balance(
        session=session,
        household_id=household.id,
        owner_user_id=owner_scope(session, household.id, household.user_id)
        if household.user_id
        else None,
    ).balance_uah
    return max(balance, Decimal("0.00"))
