from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.billing.schemas import StatementLineOut
from app.api.billing.service import list_statements
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
