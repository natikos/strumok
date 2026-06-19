from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut
from app.api.deps import get_current_user
from app.api.meter_readings.schemas import MeterReadingIn, MeterReadingOut
from app.api.meter_readings.service import (
    HouseholdNotAccessibleError,
    NoHouseholdMembershipError,
    PeriodAlreadySubmittedError,
    get_owned_household_id,
    get_user_household_id,
    list_meter_readings,
    submit_meter_reading,
)
from app.db import get_session
from app.db.models import User

router = APIRouter(prefix="/meter-readings", tags=["meter-readings"])

NO_HOUSEHOLD_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "User is not a member of any household",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "noHouseholdMembership"},
            }
        },
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "User does not own this household",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "householdNotAccessible"},
            }
        },
    },
}

SUBMIT_RESPONSES: dict[int | str, dict[str, Any]] = {
    **NO_HOUSEHOLD_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "Reading for this period already exists",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "periodAlreadySubmitted"},
            }
        },
    },
}


def require_household_id(
    household_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> int:
    try:
        if household_id is not None:
            return get_owned_household_id(
                session=session, user=current_user, household_id=household_id
            )
        return get_user_household_id(session=session, user=current_user)
    except NoHouseholdMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="noHouseholdMembership",
        ) from exc
    except HouseholdNotAccessibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="householdNotAccessible",
        ) from exc


@router.get("", response_model=list[MeterReadingOut], responses=NO_HOUSEHOLD_RESPONSES)
def list_my_meter_readings(
    household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> list[MeterReadingOut]:
    readings = list_meter_readings(session=session, household_id=household_id)
    return [MeterReadingOut.model_validate(r) for r in readings]


@router.post(
    "",
    response_model=MeterReadingOut,
    responses=SUBMIT_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def submit_my_meter_reading(
    payload: MeterReadingIn,
    household_id: int = Depends(require_household_id),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MeterReadingOut:
    try:
        reading = submit_meter_reading(
            session=session,
            user=current_user,
            household_id=household_id,
            period=payload.period,
            day_meter_value=payload.day_meter_value,
            night_meter_value=payload.night_meter_value,
        )
    except PeriodAlreadySubmittedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="periodAlreadySubmitted",
        ) from exc

    return MeterReadingOut.model_validate(reading)
