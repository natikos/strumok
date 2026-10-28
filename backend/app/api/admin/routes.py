from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlmodel import Session

from app.api.admin.schemas import (
    AdminDashboardOut,
    AdminHouseholdCreateIn,
    AdminHouseholdOut,
    AdminHouseholdUpdateIn,
    AdminInviteIn,
    AdminInviteOut,
    AdminUserOut,
    AdminUserSummaryOut,
    AdminUserUpdateIn,
    AuditLogEntryOut,
    AuditLogPageOut,
    BillIn,
    HouseholdOwnerAssignIn,
    ReconciliationOut,
    PeriodCloseIn,
    ReadingReviewIn,
    RestateIn,
    RestatementOut,
    PeriodOverviewOut,
)
from app.api.admin.service import (
    ReadingNotFoundError,
    review_reading,
    EmailTakenError,
    InviteAlreadyAcceptedError,
    invite_user,
    resend_invite,
    CannotModifySelfError,
    LastAdminRequiredError,
    UserOwnsActiveHouseholdsError,
    update_household,
    update_user,
    HouseholdAlreadyAssignedError,
    HouseholdNotFoundError,
    UserInactiveError,
    UserNotFoundError,
    assign_household_owner,
    create_household_for_user,
    get_admin_dashboard,
    list_audit_log,
    list_households_with_owners,
    list_users,
)
from app.api.auth.schemas import ErrorOut
from app.api.billing.restatement import (
    Corrections,
    NothingToCorrectError,
    PeriodNotClosedError,
    restate_period,
)
from app.api.billing.service import (
    BillNotEnteredError,
    PeriodHasUnreviewedReadingsError,
    PeriodHasNoReadingsError,
    enter_bill,
    get_reconciliation,
    PeriodAlreadyClosedError,
    PeriodNotEndedError,
    close_period,
    list_period_overviews,
)
from app.api.electricity_rates.service import NoRateConfiguredError
from app.api.auth.throttle import TooManyAttemptsError
from app.api.deps import require_admin
from app.db import get_session
from app.db.models import User

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

# FastAPI caches dependencies per request, so this reuses the router-level
# check and just hands the admin to the handler (needed as the audit actor).
CurrentAdmin = Depends(require_admin)

USER_LOOKUP_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "User does not exist",
        "model": ErrorOut,
        "content": {"application/json": {"example": {"detail": "userNotFound"}}},
    },
    status.HTTP_409_CONFLICT: {
        "description": "User is not active",
        "model": ErrorOut,
        "content": {"application/json": {"example": {"detail": "userInactive"}}},
    },
}

ASSIGN_OWNER_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Household or user does not exist",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "householdNotFound": {"value": {"detail": "householdNotFound"}},
                    "userNotFound": {"value": {"detail": "userNotFound"}},
                }
            }
        },
    },
    status.HTTP_409_CONFLICT: {
        "description": "Household already has a different owner, or user is not active",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "householdAlreadyAssigned": {
                        "value": {"detail": "householdAlreadyAssigned"}
                    },
                    "userInactive": {"value": {"detail": "userInactive"}},
                }
            }
        },
    },
}


UPDATE_USER_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: USER_LOOKUP_RESPONSES[status.HTTP_404_NOT_FOUND],
    status.HTTP_409_CONFLICT: {
        "description": "The change would lock out the co-op or orphan households",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "cannotModifySelf": {"value": {"detail": "cannotModifySelf"}},
                    "lastAdminRequired": {"value": {"detail": "lastAdminRequired"}},
                    "userOwnsActiveHouseholds": {
                        "value": {"detail": "userOwnsActiveHouseholds"}
                    },
                }
            }
        },
    },
}


@router.get("/users", response_model=list[AdminUserOut])
def list_admin_users(session: Session = Depends(get_session)) -> list[AdminUserOut]:
    return list_users(session=session)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserOut,
    responses=UPDATE_USER_RESPONSES,
)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdateIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminUserOut:
    try:
        return update_user(
            session=session,
            user_id=user_id,
            actor_id=admin.id,
            is_active=payload.is_active,
            is_admin=payload.is_admin,
            unassign_households=payload.unassign_households,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="userNotFound"
        ) from exc
    except CannotModifySelfError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="cannotModifySelf"
        ) from exc
    except LastAdminRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="lastAdminRequired"
        ) from exc
    except UserOwnsActiveHouseholdsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="userOwnsActiveHouseholds"
        ) from exc


@router.get("/dashboard", response_model=AdminDashboardOut)
def get_admin_dashboard_summary(
    session: Session = Depends(get_session),
) -> AdminDashboardOut:
    return get_admin_dashboard(session=session)


@router.get("/households", response_model=list[AdminHouseholdOut])
def list_admin_households(
    session: Session = Depends(get_session),
) -> list[AdminHouseholdOut]:
    return [
        AdminHouseholdOut.from_household(household, owner=owner)
        for household, owner in list_households_with_owners(session=session)
    ]


@router.post(
    "/households",
    response_model=AdminHouseholdOut,
    responses=USER_LOOKUP_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_household(
    payload: AdminHouseholdCreateIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminHouseholdOut:
    try:
        household, owner = create_household_for_user(
            session=session,
            name=payload.name,
            user_id=payload.user_id,
            actor_id=admin.id,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="userNotFound"
        ) from exc
    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="userInactive"
        ) from exc

    return AdminHouseholdOut.from_household(household, owner=owner)


@router.patch(
    "/households/{household_id}/owner",
    response_model=AdminHouseholdOut,
    responses=ASSIGN_OWNER_RESPONSES,
)
def assign_admin_household_owner(
    household_id: int,
    payload: HouseholdOwnerAssignIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminHouseholdOut:
    try:
        household, owner = assign_household_owner(
            session=session,
            household_id=household_id,
            user_id=payload.user_id,
            confirm_reassignment=payload.confirm_reassignment,
            actor_id=admin.id,
        )
    except HouseholdNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="householdNotFound"
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="userNotFound"
        ) from exc
    except UserInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="userInactive"
        ) from exc
    except HouseholdAlreadyAssignedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="householdAlreadyAssigned"
        ) from exc

    return AdminHouseholdOut.from_household(household, owner=owner)


@router.get("/audit-log", response_model=AuditLogPageOut)
def get_audit_log(
    household_id: int | None = None,
    period: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    action: str | None = None,
    cursor: int | None = None,
    session: Session = Depends(get_session),
) -> AuditLogPageOut:
    rows, next_cursor = list_audit_log(
        session=session,
        household_id=household_id,
        period=period,
        action=action,
        cursor=cursor,
    )
    return AuditLogPageOut(
        items=[
            AuditLogEntryOut.model_validate(
                {
                    **entry.model_dump(),
                    "actor": AdminUserSummaryOut.model_validate(actor)
                    if actor
                    else None,
                }
            )
            for entry, actor in rows
        ],
        next_cursor=next_cursor,
    )


@router.patch(
    "/households/{household_id}",
    response_model=AdminHouseholdOut,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Household does not exist",
            "model": ErrorOut,
            "content": {
                "application/json": {"example": {"detail": "householdNotFound"}}
            },
        }
    },
)
def update_admin_household(
    household_id: int,
    payload: AdminHouseholdUpdateIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminHouseholdOut:
    try:
        household, owner = update_household(
            session=session,
            household_id=household_id,
            actor_id=admin.id,
            name=payload.name,
            is_active=payload.is_active,
        )
    except HouseholdNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="householdNotFound"
        ) from exc

    return AdminHouseholdOut.from_household(household, owner=owner)


INVITE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: ASSIGN_OWNER_RESPONSES[status.HTTP_404_NOT_FOUND],
    status.HTTP_409_CONFLICT: {
        "description": "Email taken, household owned, or invite already accepted",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "emailAlreadyRegistered": {
                        "value": {"detail": "emailAlreadyRegistered"}
                    },
                    "householdAlreadyAssigned": {
                        "value": {"detail": "householdAlreadyAssigned"}
                    },
                    "inviteAlreadyAccepted": {
                        "value": {"detail": "inviteAlreadyAccepted"}
                    },
                }
            }
        },
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Invite resent too often; see Retry-After",
        "model": ErrorOut,
        "content": {"application/json": {"example": {"detail": "tooManyAttempts"}}},
    },
}


@router.post(
    "/users",
    response_model=AdminInviteOut,
    responses=INVITE_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def invite_admin_user(
    payload: AdminInviteIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminInviteOut:
    try:
        user, link, sent = invite_user(
            session=session,
            actor_id=admin.id,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            language=payload.language,
            household_id=payload.household_id,
        )
    except EmailTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="emailAlreadyRegistered"
        ) from exc
    except HouseholdNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="householdNotFound"
        ) from exc
    except HouseholdAlreadyAssignedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="householdAlreadyAssigned"
        ) from exc
    return AdminInviteOut(user=user, invite_link=link, email_sent=sent)


@router.post(
    "/users/{user_id}/invite",
    response_model=AdminInviteOut,
    responses=INVITE_RESPONSES,
)
def resend_admin_invite(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> AdminInviteOut:
    try:
        user, link, sent = resend_invite(
            session=session, actor_id=admin.id, user_id=user_id
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="userNotFound"
        ) from exc
    except InviteAlreadyAcceptedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="inviteAlreadyAccepted"
        ) from exc
    except TooManyAttemptsError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="tooManyAttempts",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return AdminInviteOut(user=user, invite_link=link, email_sent=sent)


CLOSE_PERIOD_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": "The period can't be closed",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "periodAlreadyClosed": {"value": {"detail": "periodAlreadyClosed"}},
                    "periodNotEnded": {"value": {"detail": "periodNotEnded"}},
                    "noRateConfigured": {"value": {"detail": "noRateConfigured"}},
                    "billNotEntered": {"value": {"detail": "billNotEntered"}},
                    "periodHasNoReadings": {"value": {"detail": "periodHasNoReadings"}},
                    "periodHasUnreviewedReadings": {
                        "value": {"detail": "periodHasUnreviewedReadings"}
                    },
                }
            }
        },
    }
}


@router.get("/periods", response_model=list[PeriodOverviewOut])
def get_admin_periods(
    session: Session = Depends(get_session),
) -> list[PeriodOverviewOut]:
    return [
        PeriodOverviewOut.model_validate(overview, from_attributes=True)
        for overview in list_period_overviews(session=session)
    ]


@router.post(
    "/periods/{period}/close",
    response_model=PeriodOverviewOut,
    responses=CLOSE_PERIOD_RESPONSES,
)
def close_admin_period(
    payload: PeriodCloseIn,
    period: str = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> PeriodOverviewOut:
    try:
        close_period(
            session=session,
            period=period,
            actor_id=admin.id,
            acknowledge_flags=payload.acknowledge_flags,
        )
    except PeriodAlreadyClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="periodAlreadyClosed"
        ) from exc
    except PeriodNotEndedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="periodNotEnded"
        ) from exc
    except NoRateConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="noRateConfigured"
        ) from exc
    except BillNotEnteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="billNotEntered"
        ) from exc
    except PeriodHasUnreviewedReadingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="periodHasUnreviewedReadings",
        ) from exc
    except PeriodHasNoReadingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="periodHasNoReadings"
        ) from exc

    return next(
        PeriodOverviewOut.model_validate(overview, from_attributes=True)
        for overview in list_period_overviews(session=session)
        if overview.period == period
    )


PERIOD_PATH = Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


@router.put(
    "/periods/{period}/bill",
    response_model=PeriodOverviewOut,
    responses=CLOSE_PERIOD_RESPONSES,
)
def put_admin_period_bill(
    payload: BillIn,
    period: str = PERIOD_PATH,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> PeriodOverviewOut:
    try:
        enter_bill(
            session=session,
            period=period,
            actor_id=admin.id,
            day_kwh=payload.day_kwh,
            night_kwh=payload.night_kwh,
            total_uah=payload.total_uah,
        )
    except PeriodAlreadyClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="periodAlreadyClosed"
        ) from exc
    return next(
        PeriodOverviewOut.model_validate(overview, from_attributes=True)
        for overview in list_period_overviews(session=session)
        if overview.period == period
    )


@router.get(
    "/periods/{period}/reconciliation",
    response_model=ReconciliationOut,
    responses=CLOSE_PERIOD_RESPONSES,
)
def get_admin_period_reconciliation(
    period: str = PERIOD_PATH,
    session: Session = Depends(get_session),
) -> ReconciliationOut:
    return _reconciliation(session=session, period=period)


def _reconciliation(*, session: Session, period: str) -> ReconciliationOut:
    try:
        result = get_reconciliation(session=session, period=period)
    except NoRateConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="noRateConfigured"
        ) from exc
    return ReconciliationOut.model_validate(result, from_attributes=True)


@router.post(
    "/readings/{reading_id}/review",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Reading does not exist",
            "model": ErrorOut,
            "content": {"application/json": {"example": {"detail": "readingNotFound"}}},
        }
    },
)
def review_admin_reading(
    reading_id: int,
    payload: ReadingReviewIn,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> Response:
    try:
        review_reading(session=session, reading_id=reading_id, actor_id=admin.id)
    except ReadingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="readingNotFound"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/periods/{period}/restate",
    response_model=RestatementOut,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "The period isn't closed, or nothing was corrected",
            "model": ErrorOut,
            "content": {
                "application/json": {
                    "examples": {
                        "periodNotClosed": {"value": {"detail": "periodNotClosed"}},
                        "nothingToCorrect": {"value": {"detail": "nothingToCorrect"}},
                    }
                }
            },
        }
    },
)
def restate_admin_period(
    payload: RestateIn,
    period: str = PERIOD_PATH,
    session: Session = Depends(get_session),
    admin: User = CurrentAdmin,
) -> RestatementOut:
    corrections = Corrections(
        rate=(
            (
                payload.corrections.rate.day_rate_uah,
                payload.corrections.rate.night_rate_uah,
            )
            if payload.corrections.rate
            else None
        ),
        bill_total_uah=payload.corrections.bill_total_uah,
        readings={
            (r.household_id, r.period or period): (
                r.day_meter_value,
                r.night_meter_value,
            )
            for r in payload.corrections.readings
        },
    )
    try:
        result = restate_period(
            session=session,
            period=period,
            corrections=corrections,
            reason=(payload.reason or "").strip(),
            actor_id=admin.id,
            dry_run=payload.dry_run,
        )
    except PeriodNotClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="periodNotClosed"
        ) from exc
    except NothingToCorrectError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="nothingToCorrect"
        ) from exc
    return RestatementOut.from_result(result)
