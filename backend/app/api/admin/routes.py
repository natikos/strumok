from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.admin.schemas import (
    AdminDashboardOut,
    AdminHouseholdCreateIn,
    AdminHouseholdOut,
    AdminUserSummaryOut,
    HouseholdOwnerAssignIn,
)
from app.api.admin.service import (
    HouseholdAlreadyAssignedError,
    HouseholdNotFoundError,
    UserInactiveError,
    UserNotFoundError,
    assign_household_owner,
    create_household_for_user,
    get_admin_dashboard,
    list_households_with_owners,
    list_users,
)
from app.api.auth.schemas import ErrorOut
from app.api.deps import require_admin
from app.db import get_session
from app.db.models import User

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

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


@router.get("/users", response_model=list[AdminUserSummaryOut])
def list_admin_users(session: Session = Depends(get_session)) -> list[User]:
    return list_users(session=session)


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
) -> AdminHouseholdOut:
    try:
        household, owner = create_household_for_user(
            session=session, name=payload.name, user_id=payload.user_id
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
) -> AdminHouseholdOut:
    try:
        household, owner = assign_household_owner(
            session=session,
            household_id=household_id,
            user_id=payload.user_id,
            confirm_reassignment=payload.confirm_reassignment,
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
