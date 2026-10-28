from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, desc, func, select

from app.api.billing.schemas import StatementLineOut
from app.api.electricity_rates.service import NoRateConfiguredError, get_effective_rate
from app.core import audit
from app.core.domain import (
    ChargeInput,
    compute_period_statement,
    reconcile_period,
    current_billing_period,
    derive_usage,
    period_window_closed,
)
from app.core.time import utc_now
from app.db.models import (
    BillingPeriod,
    ElectricityRate,
    Household,
    HouseholdCharge,
    MeterReading,
    User,
)


class PeriodAlreadyClosedError(Exception):
    pass


class PeriodNotEndedError(Exception):
    pass


class BillNotEnteredError(Exception):
    pass


class PeriodHasNoReadingsError(Exception):
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


def charge_inputs_for_period(*, session: Session, period: str) -> list[ChargeInput]:
    """One input per household that has a reading for `period`, with usage
    derived from its consecutive readings."""
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
    return inputs


def enter_bill(
    *,
    session: Session,
    period: str,
    actor_id: int,
    day_kwh: Decimal,
    night_kwh: Decimal,
    total_uah: Decimal,
) -> BillingPeriod:
    """Records what the utility charged the co-op for an open period. Entering
    it again replaces the figures; each change is audited."""
    ensure_period(session=session, period=period)
    row = session.exec(
        select(BillingPeriod).where(BillingPeriod.period == period).with_for_update()
    ).one()
    if row.status == "closed":
        raise PeriodAlreadyClosedError

    audit.record(
        session,
        actor_user_id=actor_id,
        action="billEntered",
        entity_type="billing_period",
        period=period,
        before={
            "day_kwh": row.bill_day_kwh,
            "night_kwh": row.bill_night_kwh,
            "total_uah": row.bill_total_uah,
        },
        after={"day_kwh": day_kwh, "night_kwh": night_kwh, "total_uah": total_uah},
    )
    row.bill_day_kwh = day_kwh
    row.bill_night_kwh = night_kwh
    row.bill_total_uah = total_uah
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


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

    inputs = charge_inputs_for_period(session=session, period=period)
    if not inputs:
        raise PeriodHasNoReadingsError
    if row.bill_total_uah is None:
        raise BillNotEnteredError

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
            bill_total_uah=row.bill_total_uah,
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

    active_households = session.exec(
        select(func.count()).select_from(Household).where(Household.is_active)
    ).one()
    reading_counts = dict(
        session.exec(
            select(MeterReading.period, func.count()).group_by(col(MeterReading.period))
        ).all()
    )
    periods = sorted(
        {*rows, *reading_counts, current_billing_period(now)}, reverse=True
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
            if readings == 0:
                blockers.append("noReadings")
            if row is None or row.bill_total_uah is None:
                blockers.append("billNotEntered")
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


@dataclass(frozen=True)
class ReconciliationLine:
    household_id: int
    household_name: str
    usage_kwh: Decimal
    usage_share_percent: Decimal
    tariff_uah: Decimal
    loss_share_uah: Decimal
    penalty_uah: Decimal
    total_uah: Decimal
    is_estimated: bool


@dataclass(frozen=True)
class PeriodReconciliation:
    period: str
    status: str
    closed_at: datetime | None
    bill_day_kwh: Decimal | None
    bill_night_kwh: Decimal | None
    bill_total_uah: Decimal | None
    total_usage_kwh: Decimal
    total_tariff_uah: Decimal
    loss_uah: Decimal | None
    loss_percent: Decimal | None
    kwh_loss: Decimal | None
    kwh_loss_percent: Decimal | None
    shares_total_uah: Decimal
    variance_uah: Decimal | None
    lines: list[ReconciliationLine]
    remainder_household_names: list[str]


def _percent(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole == 0:
        return None
    return (part * 100 / whole).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_reconciliation(*, session: Session, period: str) -> PeriodReconciliation:
    """The bill versus Σ household charges. Open periods are computed from the
    current readings; closed ones read the stored charges."""
    row = session.get(BillingPeriod, period) or BillingPeriod(period=period)
    if row.status == "closed":
        charges = session.exec(
            select(HouseholdCharge).where(HouseholdCharge.period == period)
        ).all()
        inputs = [
            ChargeInput(
                household_id=c.household_id,
                owner_user_id=c.owner_user_id,
                reading_id=c.reading_id,
                day_usage_kwh=c.day_usage_kwh,
                night_usage_kwh=c.night_usage_kwh,
                is_estimated=c.is_estimated,
            )
            for c in charges
        ]
        rate = session.get(ElectricityRate, row.rate_id) if row.rate_id else None
    else:
        inputs = charge_inputs_for_period(session=session, period=period)
        charges = []
        rate = get_effective_rate(session=session, period=period)

    stored = {c.household_id: c for c in charges}
    if rate is not None:
        result = reconcile_period(
            inputs,
            day_rate_uah=rate.day_rate_uah,
            night_rate_uah=rate.night_rate_uah,
            bill_total_uah=row.bill_total_uah,
        )
        computed = {line.household_id: line for line in result.lines}
        total_tariff = result.total_tariff_uah
        loss = result.loss_uah
        remainder_ids = result.remainder_household_ids
    else:
        # Backfilled history has no rate on record: the stored amounts are final.
        computed = {}
        total_tariff = sum((c.tariff_uah for c in charges), Decimal("0.00"))
        loss = None
        remainder_ids = []

    names = {
        h.id: h.name
        for h in session.exec(
            select(Household).where(
                col(Household.id).in_([i.household_id for i in inputs])
            )
        )
    }
    total_usage = sum(
        (i.day_usage_kwh + i.night_usage_kwh for i in inputs), Decimal("0")
    )
    lines = []
    for item in inputs:
        usage = item.day_usage_kwh + item.night_usage_kwh
        line = stored.get(item.household_id) or computed[item.household_id]
        lines.append(
            ReconciliationLine(
                household_id=item.household_id,
                household_name=names.get(item.household_id, ""),
                usage_kwh=usage,
                usage_share_percent=_percent(usage, total_usage) or Decimal("0.00"),
                tariff_uah=line.tariff_uah,
                loss_share_uah=line.loss_share_uah,
                penalty_uah=line.penalty_uah,
                total_uah=line.total_uah,
                is_estimated=item.is_estimated,
            )
        )
    lines.sort(key=lambda line: line.household_name)

    shares_total = sum((line.total_uah for line in lines), Decimal("0.00"))
    bill_kwh = (
        row.bill_day_kwh + row.bill_night_kwh
        if row.bill_day_kwh is not None and row.bill_night_kwh is not None
        else None
    )
    kwh_loss = bill_kwh - total_usage if bill_kwh is not None else None
    return PeriodReconciliation(
        period=period,
        status=row.status,
        closed_at=row.closed_at,
        bill_day_kwh=row.bill_day_kwh,
        bill_night_kwh=row.bill_night_kwh,
        bill_total_uah=row.bill_total_uah,
        total_usage_kwh=total_usage,
        total_tariff_uah=total_tariff,
        loss_uah=loss,
        loss_percent=(
            _percent(loss, row.bill_total_uah)
            if loss is not None and row.bill_total_uah
            else None
        ),
        kwh_loss=kwh_loss,
        kwh_loss_percent=(
            _percent(kwh_loss, bill_kwh) if kwh_loss is not None and bill_kwh else None
        ),
        shares_total_uah=shares_total,
        variance_uah=(
            shares_total - row.bill_total_uah
            if row.bill_total_uah is not None
            else None
        ),
        lines=lines,
        remainder_household_names=[names.get(i, "") for i in remainder_ids],
    )
