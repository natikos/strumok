from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.billing.payments import get_balance
from app.api.billing.schemas import (
    AdjustmentOut,
    BalanceOut,
    CurrentPeriodOut,
    StatementLineOut,
)
from app.api.billing.service import list_adjustments, list_statements
from app.core.domain import current_billing_period
from app.db.models import BillingPeriod
from app.api.meter_readings.routes import NO_HOUSEHOLD_RESPONSES, require_household_id
from app.db import get_session

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
)


@router.get(
    "/statements",
    response_model=list[StatementLineOut],
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_statements(
    household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> list[StatementLineOut]:
    return list_statements(session=session, household_id=household_id)


@router.get(
    "/adjustments",
    response_model=list[AdjustmentOut],
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_adjustments(
    household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> list[AdjustmentOut]:
    return [
        AdjustmentOut.model_validate(a)
        for a in list_adjustments(session=session, household_id=household_id)
    ]


@router.get("/current-period", response_model=CurrentPeriodOut)
def get_current_period(
    session: Session = Depends(get_session),
) -> CurrentPeriodOut:
    period = current_billing_period()
    row = session.get(BillingPeriod, period)
    return CurrentPeriodOut(
        period=period, status="closed" if row and row.status == "closed" else "open"
    )


@router.get(
    "/balance",
    response_model=BalanceOut,
    responses=NO_HOUSEHOLD_RESPONSES,
)
def get_my_balance(
    household_id: int = Depends(require_household_id),
    session: Session = Depends(get_session),
) -> BalanceOut:
    return BalanceOut.model_validate(
        get_balance(session=session, household_id=household_id), from_attributes=True
    )
