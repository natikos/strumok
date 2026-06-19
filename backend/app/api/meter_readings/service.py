from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, asc, desc, select

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


def list_meter_readings(*, session: Session, household_id: int) -> list[MeterReading]:
    return list(
        session.exec(
            select(MeterReading)
            .where(MeterReading.household_id == household_id)
            .order_by(desc(MeterReading.period))
        ).all()
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
    previous = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .order_by(desc(MeterReading.period))
    ).first()

    if previous:
        day_usage_kwh = day_meter_value - previous.day_meter_value
        night_usage_kwh = night_meter_value - previous.night_meter_value
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
