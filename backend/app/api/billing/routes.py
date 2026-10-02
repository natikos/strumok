from fastapi import APIRouter, Depends

from app.api.billing.schemas import BillingWindowOut
from app.api.deps import get_current_user
from app.core.domain import (
    current_billing_period,
    is_submission_window_open,
    submission_window,
)
from app.db.models import User

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/window", response_model=BillingWindowOut)
def get_billing_window(
    current_user: User = Depends(get_current_user),
) -> BillingWindowOut:
    del current_user
    opens_at, closes_at = submission_window()
    return BillingWindowOut(
        period=current_billing_period(),
        opens_at=opens_at,
        closes_at=closes_at,
        is_open=is_submission_window_open(),
    )
