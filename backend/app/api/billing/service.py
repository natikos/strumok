from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, desc, func, select

from app.api.billing.schemas import StatementLineOut
from app.api.electricity_rates.service import NoRateConfiguredError, get_effective_rate
from app.core import audit
from app.core.domain import (
    ChargeInput,
    compute_period_statement,
    current_billing_period,
    derive_usage,
    period_window_closed,
)
from app.core.time import utc_now
from app.db.models import (
    BillingPeriod,
    Household,
    HouseholdCharge,
    MeterReading,
    User,
)


class PeriodAlreadyClosedError(Exception):
    pass


class PeriodNotEndedError(Exception):
    pass


class PeriodClosedError(Exception):
    """A resident tried to submit for a period the head has closed."""


def ensure_period(*, session: Session, period: str) -> None:
    """Creates the period's row on first use; safe under concurrent callers."""
    session.execute(
        insert(BillingPeriod.__table__).values(period=period).on_conflict_do_nothing()  # type: ignore[arg-type]
    )


def lock_period_for_submission(*, session: Session, period: str) -> None:
    """Takes a shared lock on the period row, so a submission racing a close
    either lands first (the close waits for it) or sees `closed`."""
    ensure_period(session=session, period=period)
    row = session.exec(
        select(BillingPeriod)
        .where(BillingPeriod.period == period)
        .with_for_update(read=True)
    ).one()
    if row.status == "closed":
        raise PeriodClosedError


def derive_reading_usage(
    *, session: Session, reading: MeterReading
) -> tuple[Decimal, Decimal]:
    """Usage is derived from the household's consecutive readings at read time,
    so it can't go stale when an earlier reading changes."""
    previous = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == reading.household_id)
        .where(MeterReading.period < reading.period)
        .order_by(desc(MeterReading.period))
    ).first()
    return (
        derive_usage(
            previous.day_meter_value if previous else None, reading.day_meter_value
        ),
        derive_usage(
            previous.night_meter_value if previous else None, reading.night_meter_value
        ),
    )


def provisional_line(*, session: Session, household_id: int) -> StatementLineOut | None:
    """The open period's figure for a household: usage × rate, not stored."""
    period = current_billing_period()
    closed = session.get(BillingPeriod, period)
    if closed is not None and closed.status == "closed":
        return None

    reading = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period == period)
    ).first()
    if reading is None:
        return None

    try:
        rate = get_effective_rate(session=session, period=period)
    except NoRateConfiguredError:
        return None

    household = session.get(Household, household_id)
    day, night = derive_reading_usage(session=session, reading=reading)
    (line,) = compute_period_statement(
        [
            ChargeInput(
                household_id=household_id,
                owner_user_id=household.user_id if household else None,
                reading_id=reading.id,
                day_usage_kwh=day,
                night_usage_kwh=night,
            )
        ],
        day_rate_uah=rate.day_rate_uah,
        night_rate_uah=rate.night_rate_uah,
    )
    return StatementLineOut(
        period=period,
        status="provisional",
        day_usage_kwh=line.day_usage_kwh,
        night_usage_kwh=line.night_usage_kwh,
        is_estimated=line.is_estimated,
        tariff_uah=line.tariff_uah,
        loss_share_uah=line.loss_share_uah,
        penalty_uah=line.penalty_uah,
        penalty_credit_uah=line.penalty_credit_uah,
        total_uah=line.total_uah,
    )


def list_statements(*, session: Session, household_id: int) -> list[StatementLineOut]:
    """Closed charges (newest first) plus the provisional open-period line."""
    charges = session.exec(
        select(HouseholdCharge)
        .where(HouseholdCharge.household_id == household_id)
        .order_by(desc(HouseholdCharge.period))
    ).all()
    lines = [
        StatementLineOut.model_validate({**charge.model_dump(), "status": "closed"})
        for charge in charges
    ]
    provisional = provisional_line(session=session, household_id=household_id)
    return [provisional, *lines] if provisional else lines


def close_period(
    *, session: Session, period: str, actor_id: int, now: datetime | None = None
) -> list[HouseholdCharge]:
    """Closes `period` in one transaction: locks the row, computes every
    household's charge from its reading, inserts the ledger rows and flips the
    status. Any failure leaves the period open and writes nothing."""
    ensure_period(session=session, period=period)
    row = session.exec(
        select(BillingPeriod).where(BillingPeriod.period == period).with_for_update()
    ).one()
    if row.status == "closed":
        raise PeriodAlreadyClosedError
    if not period_window_closed(period, now):
        raise PeriodNotEndedError

    rate = get_effective_rate(session=session, period=period)

    readings = session.exec(
        select(MeterReading).where(MeterReading.period == period)
    ).all()
    owners = {
        household.id: household.user_id
        for household in session.exec(
            select(Household).where(
                col(Household.id).in_([r.household_id for r in readings])
            )
        )
    }
    inputs = []
    for reading in readings:
        day, night = derive_reading_usage(session=session, reading=reading)
        inputs.append(
            ChargeInput(
                household_id=reading.household_id,
                owner_user_id=owners.get(reading.household_id),
                reading_id=reading.id,
                day_usage_kwh=day,
                night_usage_kwh=night,
            )
        )

    charges = [
        HouseholdCharge(
            period=period,
            household_id=line.household_id,
            owner_user_id=line.owner_user_id,
            reading_id=line.reading_id,
            day_usage_kwh=line.day_usage_kwh,
            night_usage_kwh=line.night_usage_kwh,
            is_estimated=line.is_estimated,
            tariff_uah=line.tariff_uah,
            loss_share_uah=line.loss_share_uah,
            penalty_uah=line.penalty_uah,
            penalty_credit_uah=line.penalty_credit_uah,
            total_uah=line.total_uah,
        )
        for line in compute_period_statement(
            inputs,
            day_rate_uah=rate.day_rate_uah,
            night_rate_uah=rate.night_rate_uah,
        )
    ]
    session.add_all(charges)

    row.status = "closed"
    row.rate_id = rate.id
    row.closed_at = utc_now()
    row.closed_by_user_id = actor_id
    session.add(row)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="periodClosed",
        entity_type="billing_period",
        period=period,
        after={
            "households_charged": len(charges),
            "total_uah": sum((c.total_uah for c in charges), Decimal("0.00")),
            "rate_id": rate.id,
        },
    )
    session.commit()
    return charges


@dataclass(frozen=True)
class PeriodOverview:
    period: str
    status: str
    closed_at: datetime | None
    closed_by_name: str | None
    readings_count: int
    missing_count: int
    blockers: list[str]


def list_period_overviews(
    *, session: Session, now: datetime | None = None
) -> list[PeriodOverview]:
    """Every known period plus the current one, newest first. Blockers say
    what currently prevents closing an open period."""
    rows = {row.period: row for row in session.exec(select(BillingPeriod))}
    periods = sorted({*rows, current_billing_period(now)}, reverse=True)

    active_households = session.exec(
        select(func.count()).select_from(Household).where(Household.is_active)
    ).one()
    reading_counts = dict(
        session.exec(
            select(MeterReading.period, func.count()).group_by(col(MeterReading.period))
        ).all()
    )
    closers = {
        user.id: f"{user.first_name} {user.last_name}"
        for user in session.exec(
            select(User).where(
                col(User.id).in_(
                    [r.closed_by_user_id for r in rows.values() if r.closed_by_user_id]
                )
            )
        )
    }

    overviews = []
    for period in periods:
        row = rows.get(period)
        status = row.status if row else "open"
        readings = reading_counts.get(period, 0)
        blockers: list[str] = []
        if status == "open":
            if not period_window_closed(period, now):
                blockers.append("periodNotEnded")
            try:
                get_effective_rate(session=session, period=period)
            except NoRateConfiguredError:
                blockers.append("noRateConfigured")
        overviews.append(
            PeriodOverview(
                period=period,
                status=status,
                closed_at=row.closed_at if row else None,
                closed_by_name=closers.get(row.closed_by_user_id)
                if row and row.closed_by_user_id
                else None,
                readings_count=readings,
                missing_count=max(active_households - readings, 0),
                blockers=blockers,
            )
        )
    return overviews
