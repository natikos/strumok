from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, asc, desc, select

from app.api.billing.service import (
    get_meter_segment,
    lock_period_for_submission,
    usage_since,
)
from app.api.electricity_rates.service import get_effective_rate
from app.api.meter_readings.schemas import MeterReadingOut
from app.core.domain import current_billing_period
from app.core.domain.billing import derive_usage, detect_review_reason, previous_period
from app.db.models import Household, MeterReading, MeterSegment, User


class NoHouseholdMembershipError(Exception):
    pass


class HouseholdNotAccessibleError(Exception):
    pass


class HouseholdInactiveError(Exception):
    pass


class PeriodAlreadySubmittedError(Exception):
    pass


class PeriodNotOpenError(Exception):
    pass


def get_owned_household_id(*, session: Session, user: User, household_id: int) -> int:
    household = session.exec(
        select(Household)
        .where(Household.user_id == user.id)
        .where(Household.id == household_id)
    ).first()

    if household is None:
        raise HouseholdNotAccessibleError

    if not household.is_active:
        raise HouseholdInactiveError

    return household.id


def get_user_household_id(*, session: Session, user: User) -> int:
    household_id = session.exec(
        select(Household.id)
        .where(Household.user_id == user.id)
        .where(Household.is_active)
        .order_by(asc(Household.created_at))
    ).first()

    if household_id is None:
        raise NoHouseholdMembershipError

    return household_id


def list_meter_readings(
    *, session: Session, household_id: int, since_period: str | None = None
) -> list[MeterReadingOut]:
    """`since_period` hides everything before it: an owner who took a plot over
    doesn't see the previous owner's readings."""
    household_created_at = session.exec(
        select(Household.created_at).where(Household.id == household_id)
    ).one()

    query = select(MeterReading).where(MeterReading.household_id == household_id)
    if since_period is not None:
        query = query.where(MeterReading.period >= since_period)
    readings = list(session.exec(query.order_by(desc(MeterReading.period))).all())

    start_period = (
        readings[-1].period if readings else household_created_at.strftime("%Y-%m")
    )
    if since_period is not None:
        start_period = max(start_period, since_period)
    readings_by_period = {reading.period: reading for reading in readings}

    result: list[MeterReadingOut] = []
    period = current_billing_period()
    while period >= start_period:
        reading = readings_by_period.get(period)
        if reading is not None:
            result.append(MeterReadingOut.model_validate(reading))
        else:
            result.append(
                MeterReadingOut(
                    id=None,
                    household_id=household_id,
                    submitted_by_user_id=None,
                    period=period,
                    day_meter_value=None,
                    night_meter_value=None,
                    day_usage_kwh=Decimal("0"),
                    night_usage_kwh=Decimal("0"),
                    amount_charged_uah=Decimal("0"),
                    submitted_at=None,
                    source="resident",
                    corrected_at=None,
                    correction_reason=None,
                )
            )
        period = previous_period(period)

    replaced_periods = set(
        session.exec(
            select(MeterSegment.period).where(MeterSegment.household_id == household_id)
        )
    )
    for entry in result:
        entry.meter_replaced = entry.period in replaced_periods

    return result


def _review_reason(
    *,
    session: Session,
    household_id: int,
    period: str,
    day_meter_value: Decimal,
    night_meter_value: Decimal,
) -> str | None:
    """Looks at the last four real readings: the newest is the comparison
    point, the rest give up to three past usages. A recorded meter
    replacement explains a lower or jumping value, so nothing is flagged."""
    if get_meter_segment(session=session, household_id=household_id, period=period):
        return None
    history = list(
        session.exec(
            select(MeterReading)
            .where(MeterReading.household_id == household_id)
            .where(MeterReading.period < period)
            .where(MeterReading.source != "estimate")
            .order_by(desc(MeterReading.period))
            .limit(4)
        )
    )
    if not history:
        return None

    usages = []
    for newer, older in zip(history, history[1:]):
        usages.append(
            derive_usage(older.day_meter_value, newer.day_meter_value)
            + derive_usage(older.night_meter_value, newer.night_meter_value)
        )
    return detect_review_reason(
        previous=(history[0].day_meter_value, history[0].night_meter_value),
        recent_usages_kwh=usages,
        day_meter_value=day_meter_value,
        night_meter_value=night_meter_value,
    )


def submit_meter_reading(
    *,
    session: Session,
    user: User,
    household_id: int,
    period: str,
    day_meter_value: Decimal,
    night_meter_value: Decimal,
) -> MeterReading:
    if period != current_billing_period():
        raise PeriodNotOpenError

    lock_period_for_submission(session=session, period=period)

    previous = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period < period)
        .order_by(desc(MeterReading.period))
    ).first()

    day_usage_kwh, night_usage_kwh = usage_since(
        session=session,
        household_id=household_id,
        period=period,
        previous_values=(
            (previous.day_meter_value, previous.night_meter_value) if previous else None
        ),
        previous_is_estimate=False,
        day=day_meter_value,
        night=night_meter_value,
    )

    review_reason = _review_reason(
        session=session,
        household_id=household_id,
        period=period,
        day_meter_value=day_meter_value,
        night_meter_value=night_meter_value,
    )

    rate = get_effective_rate(session=session, period=period)
    amount_charged_uah = (
        day_usage_kwh * rate.day_rate_uah + night_usage_kwh * rate.night_rate_uah
    ).quantize(Decimal("0.01"))

    reading = MeterReading(
        household_id=household_id,
        submitted_by_user_id=user.id,
        period=period,
        day_meter_value=day_meter_value,
        night_meter_value=night_meter_value,
        day_usage_kwh=day_usage_kwh,
        night_usage_kwh=night_usage_kwh,
        amount_charged_uah=amount_charged_uah,
        needs_review=review_reason is not None,
        review_reason=review_reason,
    )
    session.add(reading)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PeriodAlreadySubmittedError from exc

    session.refresh(reading)
    return reading
