from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut
from app.api.deps import require_admin
from app.api.electricity_rates.schemas import ElectricityRateCreateIn, ElectricityRateOut
from app.api.electricity_rates.service import (
    EffectiveFromAlreadyExistsError,
    create_rate,
    list_rates,
)
from app.db import get_session

router = APIRouter(
    prefix="/electricity-rates",
    tags=["electricity-rates"],
    dependencies=[Depends(require_admin)],
)

CREATE_RATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": "A rate is already configured for this period",
        "model": ErrorOut,
        "content": {
            "application/json": {"example": {"detail": "effectiveFromAlreadyExists"}}
        },
    },
}


@router.get("", response_model=list[ElectricityRateOut])
def list_electricity_rates(
    session: Session = Depends(get_session),
) -> list[ElectricityRateOut]:
    return list_rates(session=session)


@router.post(
    "",
    response_model=ElectricityRateOut,
    responses=CREATE_RATE_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def create_electricity_rate(
    payload: ElectricityRateCreateIn,
    session: Session = Depends(get_session),
) -> ElectricityRateOut:
    try:
        return create_rate(
            session=session,
            day_rate_uah=payload.day_rate_uah,
            night_rate_uah=payload.night_rate_uah,
            effective_from=payload.effective_from,
        )
    except EffectiveFromAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="effectiveFromAlreadyExists"
        ) from exc
