from decimal import Decimal

from sqlmodel import Session, desc, select

from app.api.billing.schemas import StatementLineOut
from app.api.electricity_rates.service import NoRateConfiguredError, get_effective_rate
from app.core.domain import (
    ChargeInput,
    compute_period_statement,
    current_billing_period,
    derive_usage,
)
from app.db.models import BillingPeriod, Household, HouseholdCharge, MeterReading


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
