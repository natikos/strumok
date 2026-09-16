from sqlmodel import Session, select

from app.db.models import Household, User


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
