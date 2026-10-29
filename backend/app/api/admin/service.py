from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.api.admin.schemas import (
    AdminDashboardHouseholdOut,
    AdminDashboardOut,
    AdminReadingOut,
    AdminUserOut,
    AdminUserSummaryOut,
)
from app.api.auth.service import build_invite_link, send_invite_email
from app.api.auth.throttle import (
    INVITE_RESEND_LIMIT,
    check_not_throttled,
    record_failure,
)
from app.core import audit
from app.core.ownership import set_owner
from app.api.billing.payments import get_balance
from app.api.billing.service import derive_reading_usage
from app.core.domain import (
    current_billing_period,
    period_window_closed,
    previous_period,
)
from app.core.time import utc_now
from app.db.models import (
    AuditLog,
    BillingPeriod,
    Household,
    HouseholdCharge,
    LanguageCode,
    MeterReading,
    MeterSegment,
    User,
)


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


class CannotModifySelfError(Exception):
    pass


class LastAdminRequiredError(Exception):
    pass


class UserOwnsActiveHouseholdsError(Exception):
    pass


def _active_household_counts(*, session: Session) -> dict[int, int]:
    rows = session.exec(
        select(col(Household.user_id), func.count())
        .where(col(Household.user_id).is_not(None), Household.is_active)
        .group_by(col(Household.user_id))
    )
    return {user_id: count for user_id, count in rows if user_id is not None}


def list_users(*, session: Session) -> list[AdminUserOut]:
    counts = _active_household_counts(session=session)
    users = session.exec(select(User).order_by(User.first_name, User.last_name))
    return [
        AdminUserOut.model_validate(
            {
                **user.model_dump(),
                "household_count": counts.get(user.id, 0),
                "invite_pending": user.password_hash is None,
            }
        )
        for user in users
    ]


def _active_admin_count(*, session: Session) -> int:
    return session.exec(
        select(func.count()).select_from(User).where(User.is_admin, User.is_active)
    ).one()


def update_user(
    *,
    session: Session,
    user_id: int,
    actor_id: int,
    is_active: bool | None,
    is_admin: bool | None,
    unassign_households: bool,
) -> AdminUserOut:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    if user.id == actor_id:
        raise CannotModifySelfError

    losing_admin_access = (
        user.is_admin and user.is_active and (is_active is False or is_admin is False)
    )
    if losing_admin_access and _active_admin_count(session=session) <= 1:
        raise LastAdminRequiredError

    if is_active is False and user.is_active:
        owned = list(
            session.exec(
                select(Household).where(
                    Household.user_id == user.id, Household.is_active
                )
            )
        )
        if owned and not unassign_households:
            raise UserOwnsActiveHouseholdsError
        for household in owned:
            audit.record(
                session,
                actor_user_id=actor_id,
                action="householdOwnerAssigned",
                entity_type="household",
                entity_id=household.id,
                household_id=household.id,
                before={"user_id": user.id},
                after={"user_id": None},
                reason="ownerDeactivated",
            )
            set_owner(session, household, None)

    def change(field: str, value: bool, action: str) -> None:
        if getattr(user, field) == value:
            return
        audit.record(
            session,
            actor_user_id=actor_id,
            action=action,
            entity_type="user",
            entity_id=user.id,
            before={field: getattr(user, field)},
            after={field: value},
        )
        setattr(user, field, value)

    if is_active is not None:
        was_active = user.is_active
        change(
            "is_active",
            is_active,
            "userDeactivated" if not is_active else "userReactivated",
        )
        if was_active and not is_active:
            # Signs the user out everywhere; their cookie stops working at once.
            user.token_version += 1
    if is_admin is not None:
        change("is_admin", is_admin, "adminGranted" if is_admin else "adminRevoked")

    session.add(user)
    session.commit()
    session.refresh(user)
    return next(u for u in list_users(session=session) if u.id == user.id)


def list_households_with_owners(
    *, session: Session
) -> list[tuple[Household, User | None]]:
    households = session.exec(select(Household).order_by(Household.name)).all()
    owners_by_id = {
        user.id: user
        for user in session.exec(
            select(User).where(
                col(User.id).in_(
                    {h.user_id for h in households if h.user_id is not None}
                )
            )
        )
    }
    return [
        (h, owners_by_id.get(h.user_id) if h.user_id is not None else None)
        for h in households
    ]


def get_admin_dashboard(*, session: Session) -> AdminDashboardOut:
    current_period = current_billing_period()
    readings = session.exec(
        select(MeterReading).order_by(
            col(MeterReading.household_id), col(MeterReading.period).desc()
        )
    ).all()

    latest_by_household: dict[int, MeterReading] = {}
    current_by_household: dict[int, MeterReading] = {}
    for reading in readings:
        latest_by_household.setdefault(reading.household_id, reading)
        if reading.period == current_period:
            current_by_household[reading.household_id] = reading

    previous_by_reading: dict[int, MeterReading] = {}
    by_household: dict[int, list[MeterReading]] = {}
    for reading in readings:
        by_household.setdefault(reading.household_id, []).append(reading)
    for household_readings in by_household.values():
        # `readings` is newest first per household, so the next one is the prior.
        for newer, older in zip(household_readings, household_readings[1:]):
            previous_by_reading[newer.id] = older

    # Only a closed period has a charge; an open period's figure isn't one yet.
    charges_by_key = {
        (charge.household_id, charge.period): charge.total_uah
        for charge in session.exec(select(HouseholdCharge)).all()
    }

    households = []
    for household, owner in list_households_with_owners(session=session):
        current = current_by_household.get(household.id)
        latest = latest_by_household.get(household.id)
        households.append(
            AdminDashboardHouseholdOut(
                id=household.id,
                name=household.name,
                owner=AdminUserSummaryOut.model_validate(owner) if owner else None,
                submission_status=(
                    ("estimated" if current.source == "estimate" else "submitted")
                    if current
                    else "missing"
                ),
                submitted_at=current.submitted_at if current else None,
                reading=(
                    AdminReadingOut(
                        id=current.id,
                        day_meter_value=current.day_meter_value,
                        night_meter_value=current.night_meter_value,
                        previous_day_meter_value=(
                            previous_by_reading[current.id].day_meter_value
                            if current.id in previous_by_reading
                            else None
                        ),
                        previous_night_meter_value=(
                            previous_by_reading[current.id].night_meter_value
                            if current.id in previous_by_reading
                            else None
                        ),
                        needs_review=current.needs_review,
                        review_reason=current.review_reason,  # type: ignore[arg-type]
                    )
                    if current
                    else None
                ),
                latest_period=latest.period if latest else None,
                latest_usage_kwh=(
                    _summed_usage_kwh(
                        *derive_reading_usage(session=session, reading=latest)
                    )
                    if latest
                    else None
                ),
                latest_amount_charged_uah=(
                    charges_by_key.get((latest.household_id, latest.period))
                    if latest
                    else None
                ),
            )
        )

    return AdminDashboardOut(
        current_period=current_period,
        households=households,
    )


def _get_active_user(*, session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    if not user.is_active:
        raise UserInactiveError
    return user


def create_household_for_user(
    *,
    session: Session,
    name: str,
    user_id: int,
    actor_id: int,
    starting_day: Decimal | None = None,
    starting_night: Decimal | None = None,
) -> tuple[Household, User]:
    owner = _get_active_user(session=session, user_id=user_id)

    household = Household(name=name)
    session.add(household)
    session.flush()
    set_owner(session, household, user_id)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="householdCreated",
        entity_type="household",
        entity_id=household.id,
        household_id=household.id,
        after={"name": name, "user_id": user_id},
    )
    if starting_day is None or starting_night is None:
        # No starting values means a brand-new meter, which starts at 0, so
        # the first resident reading is billed in full and the plot can be
        # estimated before it ever submits.
        starting_day = Decimal(0)
        starting_night = Decimal(0)
    # The first period residents submit is the current one; the baseline
    # sits just before it so that month is measured against it.
    period = previous_period(current_billing_period())
    baseline = MeterReading(
        household_id=household.id,
        submitted_by_user_id=actor_id,
        period=period,
        day_meter_value=starting_day,
        night_meter_value=starting_night,
        source="baseline",
        corrected_at=utc_now(),
        correction_reason="Starting meter reading",
    )
    session.add(baseline)
    session.flush()
    audit.record(
        session,
        actor_user_id=actor_id,
        action="baselineSet",
        entity_type="meter_reading",
        entity_id=baseline.id,
        household_id=household.id,
        period=period,
        after={"day": starting_day, "night": starting_night},
        reason="Starting meter reading",
    )
    session.commit()
    session.refresh(household)
    return household, owner


class HandoverReadingRequiredError(Exception):
    """Handing a plot from one owner to another needs the meter values at the
    handover."""


class HouseholdHasOutstandingBalanceError(Exception):
    """The outgoing owner still owes money; the head must acknowledge that it
    stays with them."""


def assign_household_owner(
    *,
    session: Session,
    household_id: int,
    user_id: int | None,
    confirm_reassignment: bool,
    actor_id: int,
    handover_day: Decimal | None = None,
    handover_night: Decimal | None = None,
    acknowledge_balance: bool = False,
) -> tuple[Household, User | None]:
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdNotFoundError

    owner = (
        _get_active_user(session=session, user_id=user_id)
        if user_id is not None
        else None
    )

    previous_owner_id = household.user_id
    is_reassignment = previous_owner_id is not None and previous_owner_id != user_id
    if is_reassignment and not confirm_reassignment:
        raise HouseholdAlreadyAssignedError

    is_transfer = is_reassignment and user_id is not None
    handover = None
    if is_transfer:
        if handover_day is None or handover_night is None:
            raise HandoverReadingRequiredError
        handover = (handover_day, handover_night)
        owed = get_balance(
            session=session, household_id=household.id, owner_user_id=previous_owner_id
        ).balance_uah
        if owed > 0 and not acknowledge_balance:
            raise HouseholdHasOutstandingBalanceError

    audit.record(
        session,
        actor_user_id=actor_id,
        action="householdTransferred" if is_transfer else "householdOwnerAssigned",
        entity_type="household",
        entity_id=household.id,
        household_id=household.id,
        before={"user_id": previous_owner_id},
        after={
            "user_id": user_id,
            **(
                {
                    "handover_day": handover_day,
                    "handover_night": handover_night,
                    "balance_acknowledged": acknowledge_balance,
                }
                if is_transfer
                else {}
            ),
        },
    )
    set_owner(session, household, user_id, handover=handover)
    if handover is not None:
        _record_handover_reading(
            session=session,
            household_id=household.id,
            values=handover,
            actor_id=actor_id,
        )
    session.commit()
    session.refresh(household)
    return household, owner


def _record_handover_reading(
    *,
    session: Session,
    household_id: int,
    values: tuple[Decimal, Decimal],
    actor_id: int,
) -> None:
    """A handover while residents still report the open period (days 1-5)
    stands in for that period's reading, so it's billed on real values to the
    outgoing owner instead of estimated and penalised."""
    period = current_billing_period()
    if period_window_closed(period):
        # Later in the month the meter already counts the new month's usage.
        return
    billing_period = session.get(BillingPeriod, period)
    if billing_period is not None and billing_period.status == "closed":
        return
    if session.exec(
        select(MeterReading.id)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period == period)
    ).first():
        return
    reading = MeterReading(
        household_id=household_id,
        submitted_by_user_id=actor_id,
        period=period,
        day_meter_value=values[0],
        night_meter_value=values[1],
        source="admin",
        corrected_at=utc_now(),
        correction_reason="Handover meter reading",
    )
    session.add(reading)
    session.flush()
    audit.record(
        session,
        actor_user_id=actor_id,
        action="readingSubmittedOnBehalf",
        entity_type="meter_reading",
        entity_id=reading.id,
        household_id=household_id,
        period=period,
        after={"day": values[0], "night": values[1]},
        reason="Handover meter reading",
    )


AUDIT_PAGE_SIZE = 50


def list_audit_log(
    *,
    session: Session,
    household_id: int | None = None,
    period: str | None = None,
    action: str | None = None,
    cursor: int | None = None,
    limit: int = AUDIT_PAGE_SIZE,
) -> tuple[Sequence[tuple[AuditLog, User | None]], int | None]:
    """Newest first. `cursor` is the id of the last row of the previous page;
    returns the next cursor, or None on the last page."""
    query = select(AuditLog, User).join(
        User, col(User.id) == col(AuditLog.actor_user_id), isouter=True
    )
    if household_id is not None:
        query = query.where(AuditLog.household_id == household_id)
    if period is not None:
        query = query.where(AuditLog.period == period)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if cursor is not None:
        query = query.where(col(AuditLog.id) < cursor)

    rows = list(session.exec(query.order_by(col(AuditLog.id).desc()).limit(limit + 1)))
    next_cursor = rows[limit - 1][0].id if len(rows) > limit else None
    return rows[:limit], next_cursor


def update_household(
    *,
    session: Session,
    household_id: int,
    actor_id: int,
    name: str | None,
    is_active: bool | None,
) -> tuple[Household, User | None]:
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdNotFoundError

    def change(field: str, value: object, action: str) -> None:
        if getattr(household, field) == value:
            return
        audit.record(
            session,
            actor_user_id=actor_id,
            action=action,
            entity_type="household",
            entity_id=household.id,
            household_id=household.id,
            before={field: getattr(household, field)},
            after={field: value},
        )
        setattr(household, field, value)

    if name is not None:
        change("name", name.strip(), "householdRenamed")
    if is_active is not None:
        change(
            "is_active",
            is_active,
            "householdReactivated" if is_active else "householdDeactivated",
        )

    session.add(household)
    session.commit()
    session.refresh(household)
    owner = session.get(User, household.user_id) if household.user_id else None
    return household, owner


class EmailTakenError(Exception):
    pass


class InviteAlreadyAcceptedError(Exception):
    pass


def invite_user(
    *,
    session: Session,
    actor_id: int,
    email: str,
    first_name: str,
    last_name: str,
    language: LanguageCode,
    household_id: int | None,
) -> tuple[AdminUserOut, str, bool]:
    household = None
    if household_id is not None:
        household = session.get(Household, household_id)
        if household is None:
            raise HouseholdNotFoundError
        if household.user_id is not None:
            raise HouseholdAlreadyAssignedError

    email = email.strip().lower()
    if session.exec(select(User.id).where(User.email == email)).first() is not None:
        raise EmailTakenError

    user = User(
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        language=language,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        # Lost a race with a concurrent invite; the unique index caught it.
        session.rollback()
        raise EmailTakenError from exc

    audit.record(
        session,
        actor_user_id=actor_id,
        action="userInvited",
        entity_type="user",
        entity_id=user.id,
        after={"email": user.email, "household_id": household_id},
    )
    if household is not None:
        audit.record(
            session,
            actor_user_id=actor_id,
            action="householdOwnerAssigned",
            entity_type="household",
            entity_id=household.id,
            household_id=household.id,
            before={"user_id": None},
            after={"user_id": user.id},
        )
        set_owner(session, household, user.id)
    session.commit()
    session.refresh(user)

    link = build_invite_link(user)
    sent = send_invite_email(user=user, link=link)
    return _user_out(session=session, user=user), link, sent


def resend_invite(
    *, session: Session, actor_id: int, user_id: int
) -> tuple[AdminUserOut, str, bool]:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    if user.password_hash is not None:
        raise InviteAlreadyAcceptedError

    key = f"invite:user:{user.id}"
    check_not_throttled(session=session, key=key, limit=INVITE_RESEND_LIMIT)
    record_failure(session=session, key=key, limit=INVITE_RESEND_LIMIT)

    # The previous link stays valid until used or expired; the token's `ver`
    # is unchanged, so resending doesn't revoke it.
    audit.record(
        session,
        actor_user_id=actor_id,
        action="inviteResent",
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
    link = build_invite_link(user)
    sent = send_invite_email(user=user, link=link)
    return _user_out(session=session, user=user), link, sent


def _user_out(*, session: Session, user: User) -> AdminUserOut:
    return next(u for u in list_users(session=session) if u.id == user.id)


class ReadingNotFoundError(Exception):
    pass


def review_reading(*, session: Session, reading_id: int, actor_id: int) -> MeterReading:
    reading = session.get(MeterReading, reading_id)
    if reading is None:
        raise ReadingNotFoundError
    if reading.needs_review:
        audit.record(
            session,
            actor_user_id=actor_id,
            action="readingReviewed",
            entity_type="meter_reading",
            entity_id=reading.id,
            household_id=reading.household_id,
            period=reading.period,
            before={"needs_review": True, "review_reason": reading.review_reason},
            after={"needs_review": False},
        )
        reading.needs_review = False
        reading.reviewed_by_user_id = actor_id
        reading.reviewed_at = utc_now()
        session.add(reading)
        session.commit()
        session.refresh(reading)
    return reading


class PeriodInFutureError(Exception):
    pass


class PeriodClosedForEditError(Exception):
    """The period is closed; corrections go through POST /admin/periods/{period}/restate."""


class ReadingAlreadyExistsError(Exception):
    pass


class BaselineNotFirstError(Exception):
    """A baseline only makes sense before the household has any reading."""


class MeterChangeAlreadyRecordedError(Exception):
    pass


def _is_closed(*, session: Session, period: str) -> bool:
    row = session.get(BillingPeriod, period)
    return row is not None and row.status == "closed"


def admin_submit_reading(
    *,
    session: Session,
    household_id: int,
    period: str,
    day: Decimal,
    night: Decimal,
    reason: str,
    actor_id: int,
    kind: str = "reading",
) -> MeterReading:
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdNotFoundError
    if period > current_billing_period():
        raise PeriodInFutureError
    if _is_closed(session=session, period=period):
        raise PeriodClosedForEditError
    existing = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period == period)
    ).first()
    if existing is not None:
        raise ReadingAlreadyExistsError
    if (
        kind == "baseline"
        and session.exec(
            select(MeterReading.id).where(MeterReading.household_id == household_id)
        ).first()
    ):
        raise BaselineNotFirstError

    reading = MeterReading(
        household_id=household_id,
        submitted_by_user_id=actor_id,
        period=period,
        day_meter_value=day,
        night_meter_value=night,
        source="baseline" if kind == "baseline" else "admin",
        corrected_at=utc_now(),
        correction_reason=reason,
    )
    session.add(reading)
    session.flush()
    audit.record(
        session,
        actor_user_id=actor_id,
        action="baselineSet" if kind == "baseline" else "readingSubmittedOnBehalf",
        entity_type="meter_reading",
        entity_id=reading.id,
        household_id=household_id,
        period=period,
        after={"day": day, "night": night},
        reason=reason,
    )
    session.commit()
    session.refresh(reading)
    return reading


def record_meter_change(
    *,
    session: Session,
    household_id: int,
    period: str,
    old_final_day: Decimal,
    old_final_night: Decimal,
    new_start_day: Decimal,
    new_start_night: Decimal,
    reason: str,
    actor_id: int,
) -> tuple[MeterSegment, MeterReading | None]:
    """Records that the household's meter was replaced during `period` (the
    first period read on the new meter). The reading for that period, if any,
    now derives its usage across both meters and loses a 'decrease' flag the
    swap explains."""
    if session.get(Household, household_id) is None:
        raise HouseholdNotFoundError
    if period > current_billing_period():
        raise PeriodInFutureError
    if _is_closed(session=session, period=period):
        raise PeriodClosedForEditError
    if session.exec(
        select(MeterSegment.id)
        .where(MeterSegment.household_id == household_id)
        .where(MeterSegment.period == period)
    ).first():
        raise MeterChangeAlreadyRecordedError

    segment = MeterSegment(
        household_id=household_id,
        period=period,
        old_final_day=old_final_day,
        old_final_night=old_final_night,
        new_start_day=new_start_day,
        new_start_night=new_start_night,
        reason=reason,
        created_by_user_id=actor_id,
    )
    session.add(segment)
    session.flush()

    reading = session.exec(
        select(MeterReading)
        .where(MeterReading.household_id == household_id)
        .where(MeterReading.period == period)
    ).first()
    if reading is not None:
        if reading.review_reason == "decrease":
            reading.needs_review = False
            reading.review_reason = None
        session.add(reading)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="meterReplaced",
        entity_type="meter_segment",
        entity_id=segment.id,
        household_id=household_id,
        period=period,
        after={
            "old_final_day": old_final_day,
            "old_final_night": old_final_night,
            "new_start_day": new_start_day,
            "new_start_night": new_start_night,
        },
        reason=reason,
    )
    session.commit()
    session.refresh(segment)
    return segment, reading


def admin_correct_reading(
    *,
    session: Session,
    reading_id: int,
    day: Decimal | None,
    night: Decimal | None,
    reason: str,
    actor_id: int,
) -> MeterReading:
    reading = session.get(MeterReading, reading_id)
    if reading is None:
        raise ReadingNotFoundError
    if _is_closed(session=session, period=reading.period):
        raise PeriodClosedForEditError

    before = {"day": reading.day_meter_value, "night": reading.night_meter_value}
    reading.day_meter_value = day if day is not None else reading.day_meter_value
    reading.night_meter_value = (
        night if night is not None else reading.night_meter_value
    )
    reading.needs_review = False
    reading.corrected_at = utc_now()
    reading.correction_reason = reason
    audit.record(
        session,
        actor_user_id=actor_id,
        action="readingCorrected",
        entity_type="meter_reading",
        entity_id=reading.id,
        household_id=reading.household_id,
        period=reading.period,
        before=before,
        after={"day": reading.day_meter_value, "night": reading.night_meter_value},
        reason=reason,
    )
    session.add(reading)
    session.commit()
    session.refresh(reading)
    return reading


def admin_void_reading(
    *, session: Session, reading_id: int, reason: str, actor_id: int
) -> None:
    reading = session.get(MeterReading, reading_id)
    if reading is None:
        raise ReadingNotFoundError
    if _is_closed(session=session, period=reading.period):
        raise PeriodClosedForEditError

    audit.record(
        session,
        actor_user_id=actor_id,
        action="readingVoided",
        entity_type="meter_reading",
        entity_id=reading.id,
        household_id=reading.household_id,
        period=reading.period,
        before={"day": reading.day_meter_value, "night": reading.night_meter_value},
        reason=reason,
    )
    session.delete(reading)
    session.commit()
