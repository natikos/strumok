from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, asc, desc, select

from app.api.meter_readings.schemas import MeterReadingOut
from app.core.time import utc_now
from app.db.models import Household, MeterReading, User


class NoHouseholdMembershipError(Exception):
    pass


class HouseholdNotAccessibleError(Exception):
    pass


class PeriodAlreadySubmittedError(Exception):
    pass


def get_owned_household_id(
    *, session: Session, user: User, household_id: int
) -> int:
    owned = session.exec(
        select(Household.id)
        .where(Household.user_id == user.id)
        .where(Household.id == household_id)
    ).first()

    if owned is None:
        raise HouseholdNotAccessibleError

    return owned


def get_user_household_id(*, session: Session, user: User) -> int:
    household_id = session.exec(
        select(Household.id)
        .where(Household.user_id == user.id)
        .order_by(asc(Household.created_at))
    ).first()

    if household_id is None:
        raise NoHouseholdMembershipError

    return household_id


def _previous_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def list_meter_readings(*, session: Session, household_id: int) -> list[MeterReadingOut]:
    household_created_at = session.exec(
        select(Household.created_at).where(Household.id == household_id)
    ).one()

    readings = list(
        session.exec(
            select(MeterReading)
            .where(MeterReading.household_id == household_id)
            .order_by(desc(MeterReading.period))
        ).all()
    )

    start_period = (
        readings[-1].period if readings else household_created_at.strftime("%Y-%m")
    )
    readings_by_period = {reading.period: reading for reading in readings}

    result: list[MeterReadingOut] = []
    period = _previous_period(utc_now().strftime("%Y-%m"))
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
                )
            )
        period = _previous_period(period)

    return result


def submit_meter_reading(
    *,
    session: Session,
    user: User,
    household_id: int,
    period: str,
    day_meter_value: Decimal,
    night_meter_value: Decimal,
) -> MeterReading:
    previous = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period < period)
        .order_by(desc(MeterReading.period))
    ).first()

    if previous:
        day_usage_kwh = max(day_meter_value - previous.day_meter_value, Decimal("0"))
        night_usage_kwh = max(night_meter_value - previous.night_meter_value, Decimal("0"))
    else:
        day_usage_kwh = Decimal("0")
        night_usage_kwh = Decimal("0")

    reading = MeterReading(
        household_id=household_id,
        submitted_by_user_id=user.id,
        period=period,
        day_meter_value=day_meter_value,
        night_meter_value=night_meter_value,
        day_usage_kwh=day_usage_kwh,
        night_usage_kwh=night_usage_kwh,
    )
    session.add(reading)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PeriodAlreadySubmittedError from exc

    session.refresh(reading)
    return reading
