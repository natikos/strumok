from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut
from app.api.deps import require_admin
from app.api.electricity_rates.schemas import (
    ElectricityRateCreateIn,
    ElectricityRateOut,
    ElectricityRateUpdateIn,
)
from app.api.electricity_rates.service import (
    EffectiveFromAlreadyExistsError,
    RateNotFoundError,
    RateUsedByClosedPeriodError,
    closed_periods_by_rate,
    create_rate,
    delete_rate,
    list_rates,
    rate_history,
    update_rate,
)
from app.db import get_session
from app.db.models import ElectricityRate, User

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


def _rate_out(
    *, session: Session, rate: ElectricityRate, used: dict[int, list[str]]
) -> ElectricityRateOut:
    return ElectricityRateOut.model_validate(
        {
            **rate.model_dump(),
            "used_by_closed_periods": used.get(rate.id, []),
            "history": [
                {
                    **entry.model_dump(),
                    "actor_name": f"{actor.first_name} {actor.last_name}"
                    if actor
                    else None,
                }
                for entry, actor in rate_history(session=session, rate_id=rate.id)
            ],
        }
    )


@router.get("", response_model=list[ElectricityRateOut])
def list_electricity_rates(
    session: Session = Depends(get_session),
) -> list[ElectricityRateOut]:
    used = closed_periods_by_rate(session=session)
    return [
        _rate_out(session=session, rate=r, used=used)
        for r in list_rates(session=session)
    ]


RATE_CHANGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Rate does not exist",
        "model": ErrorOut,
        "content": {"application/json": {"example": {"detail": "rateNotFound"}}},
    },
    status.HTTP_409_CONFLICT: {
        "description": "A closed period was billed with this rate",
        "model": ErrorOut,
        "content": {
            "application/json": {"example": {"detail": "rateUsedByClosedPeriod"}}
        },
    },
}


@router.patch(
    "/{rate_id}",
    response_model=ElectricityRateOut,
    responses=RATE_CHANGE_RESPONSES,
)
def update_electricity_rate(
    rate_id: int,
    payload: ElectricityRateUpdateIn,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> ElectricityRateOut:
    try:
        rate = update_rate(
            session=session,
            rate_id=rate_id,
            actor_id=admin.id,
            day_rate_uah=payload.day_rate_uah,
            night_rate_uah=payload.night_rate_uah,
            reason=payload.reason,
        )
    except RateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rateNotFound"
        ) from exc
    except RateUsedByClosedPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="rateUsedByClosedPeriod"
        ) from exc
    return _rate_out(
        session=session, rate=rate, used=closed_periods_by_rate(session=session)
    )


@router.delete(
    "/{rate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=RATE_CHANGE_RESPONSES,
)
def delete_electricity_rate(
    rate_id: int,
    confirm: bool,
    reason: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> Response:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="confirmRequired"
        )
    try:
        delete_rate(session=session, rate_id=rate_id, actor_id=admin.id, reason=reason)
    except RateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="rateNotFound"
        ) from exc
    except RateUsedByClosedPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="rateUsedByClosedPeriod"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "",
    response_model=ElectricityRateOut,
    responses=CREATE_RATE_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def create_electricity_rate(
    payload: ElectricityRateCreateIn,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> ElectricityRateOut:
    try:
        rate = create_rate(
            session=session,
            day_rate_uah=payload.day_rate_uah,
            night_rate_uah=payload.night_rate_uah,
            effective_from=payload.effective_from,
            actor_id=admin.id,
        )
        return ElectricityRateOut.model_validate(rate)
    except EffectiveFromAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="effectiveFromAlreadyExists"
        ) from exc
