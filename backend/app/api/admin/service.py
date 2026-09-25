from decimal import Decimal

from sqlmodel import Session, select

from app.api.admin.schemas import (
    AdminDashboardHouseholdOut,
    AdminDashboardOut,
    AdminUserSummaryOut,
)
from app.core.domain import current_billing_period
from app.db.models import Household, MeterReading, User


def _summed_usage_kwh(
    day_usage_kwh: Decimal | None, night_usage_kwh: Decimal | None = None
) -> Decimal | None:
    if day_usage_kwh is None and night_usage_kwh is None:
        return None
    if day_usage_kwh is None:
        return night_usage_kwh
    if night_usage_kwh is None:
        return day_usage_kwh
    return day_usage_kwh + night_usage_kwh


class UserNotFoundError(Exception):
    pass


class UserInactiveError(Exception):
    pass


class HouseholdNotFoundError(Exception):
    pass


class HouseholdAlreadyAssignedError(Exception):
    pass


def list_users(*, session: Session) -> list[User]:
    return list(session.exec(select(User).order_by(User.first_name, User.last_name)))


def list_households_with_owners(
    *, session: Session
) -> list[tuple[Household, User | None]]:
    households = session.exec(select(Household).order_by(Household.name)).all()
    owners_by_id = {
        user.id: user
        for user in session.exec(
            select(User).where(
                User.id.in_({h.user_id for h in households if h.user_id is not None})
            )
        )
    }
    return [(h, owners_by_id.get(h.user_id)) for h in households]


def get_admin_dashboard(*, session: Session) -> AdminDashboardOut:
    current_period = current_billing_period()
    readings = session.exec(
        select(MeterReading).order_by(
            MeterReading.household_id, MeterReading.period.desc()
        )
    ).all()

    latest_by_household: dict[int, MeterReading] = {}
    current_by_household: dict[int, MeterReading] = {}
    for reading in readings:
        latest_by_household.setdefault(reading.household_id, reading)
        if reading.period == current_period:
            current_by_household[reading.household_id] = reading

    households = []
    for household, owner in list_households_with_owners(session=session):
        current = current_by_household.get(household.id)
        latest = latest_by_household.get(household.id)
        households.append(
            AdminDashboardHouseholdOut(
                id=household.id,
                name=household.name,
                owner=AdminUserSummaryOut.model_validate(owner) if owner else None,
                submission_status="submitted" if current else "missing",
                submitted_at=current.submitted_at if current else None,
                latest_period=latest.period if latest else None,
                latest_usage_kwh=(
                    _summed_usage_kwh(
                        latest.day_usage_kwh,
                        latest.night_usage_kwh,
                    )
                    if latest
                    else None
                ),
                latest_amount_charged_uah=(
                    latest.amount_charged_uah if latest else None
                ),
            )
        )

    return AdminDashboardOut(current_period=current_period, households=households)


def _get_active_user(*, session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    if not user.is_active:
        raise UserInactiveError
    return user


def create_household_for_user(
    *, session: Session, name: str, user_id: int
) -> tuple[Household, User]:
    owner = _get_active_user(session=session, user_id=user_id)

    household = Household(name=name, user_id=user_id)
    session.add(household)
    session.commit()
    session.refresh(household)
    return household, owner


def assign_household_owner(
    *,
    session: Session,
    household_id: int,
    user_id: int | None,
    confirm_reassignment: bool,
) -> tuple[Household, User | None]:
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdNotFoundError

    owner = (
        _get_active_user(session=session, user_id=user_id)
        if user_id is not None
        else None
    )

    is_reassignment = household.user_id is not None and household.user_id != user_id
    if is_reassignment and not confirm_reassignment:
        raise HouseholdAlreadyAssignedError

    household.user_id = user_id
    session.add(household)
    session.commit()
    session.refresh(household)
    return household, owner
