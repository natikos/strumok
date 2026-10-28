"""Household ownership history. `households.user_id` is the current owner; every
change goes through `set_owner` so the history and that pointer never diverge."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, col, select

from app.core.domain.billing import KYIV_TZ, next_period
from app.core.time import utc_now
from app.db.models import Household, HouseholdOwnership


def set_owner(
    session: Session,
    household: Household,
    user_id: int | None,
    *,
    handover: tuple[Decimal, Decimal] | None = None,
) -> None:
    """Ends the open ownership and opens one for `user_id` (None leaves the
    plot unowned). Does not commit."""
    now = utc_now()
    open_row = session.exec(
        select(HouseholdOwnership)
        .where(HouseholdOwnership.household_id == household.id)
        .where(col(HouseholdOwnership.valid_to).is_(None))
    ).first()
    if open_row is None and household.user_id is not None:
        # An owner the history doesn't know about (the pointer was set before
        # ownership rows existed): record them so the change is complete.
        open_row = HouseholdOwnership(
            household_id=household.id,
            user_id=household.user_id,
            valid_from=household.created_at,
        )
        session.add(open_row)
    if open_row is not None:
        if open_row.user_id == user_id:
            return
        open_row.valid_to = now
        if handover is not None:
            open_row.handover_day_meter_value, open_row.handover_night_meter_value = (
                handover
            )
        session.add(open_row)
        # The partial unique index allows one open row per household, so the
        # close must reach the database before the next row opens.
        session.flush()
    if user_id is not None:
        session.add(
            HouseholdOwnership(household_id=household.id, user_id=user_id, valid_from=now)
        )
    household.user_id = user_id
    session.add(household)
    session.flush()


def period_end(period: str) -> datetime:
    """The instant `period` ends (Kyiv midnight into the next month), as naive
    UTC like every timestamp column."""
    year, month = (int(part) for part in next_period(period).split("-"))
    return (
        datetime(year, month, 1, tzinfo=KYIV_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def owner_at(session: Session, household: Household, at: datetime) -> int | None:
    """Who owned the household at `at` (naive UTC). A plot with no recorded
    history reports its current owner; a moment before the first owner took
    over reports that first owner, who inherits the earlier periods."""
    rows = list(
        session.exec(
            select(HouseholdOwnership)
            .where(HouseholdOwnership.household_id == household.id)
            .order_by(col(HouseholdOwnership.valid_from))
        )
    )
    if not rows:
        return household.user_id
    if at < rows[0].valid_from:
        return rows[0].user_id
    for row in rows:
        if row.valid_from <= at and (row.valid_to is None or at < row.valid_to):
            return row.user_id
    return None


def tenure_start(session: Session, household_id: int) -> datetime | None:
    """When the current owner took the plot over, but only if it changed hands:
    a first owner keeps the whole history, a later one sees nothing earlier."""
    rows = list(
        session.exec(
            select(HouseholdOwnership)
            .where(HouseholdOwnership.household_id == household_id)
            .order_by(col(HouseholdOwnership.valid_from))
        )
    )
    if len(rows) < 2 or rows[-1].valid_to is not None:
        return None
    return rows[-1].valid_from


def tenure_start_period(session: Session, household_id: int) -> str | None:
    """`tenure_start` as the first period (Kyiv month) the current owner can see."""
    start = tenure_start(session, household_id)
    if start is None:
        return None
    return start.replace(tzinfo=timezone.utc).astimezone(KYIV_TZ).strftime("%Y-%m")


def changed_hands(session: Session, household_id: int) -> bool:
    return (
        len(
            session.exec(
                select(HouseholdOwnership.id).where(
                    HouseholdOwnership.household_id == household_id
                )
            ).all()
        )
        >= 2
    )


def owner_scope(session: Session, household_id: int, user_id: int) -> int | None:
    """The owner id money queries must filter on: `user_id` once the plot has
    changed hands (each owner sees only their own tenure), otherwise None
    because the sole owner owns the whole history."""
    return user_id if changed_hands(session, household_id) else None
