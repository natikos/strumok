import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.auth.schemas import ErrorOut
from app.api.cron.schemas import CronTickOut
from app.api.cron.service import run_tick
from app.core.config import settings

router = APIRouter(prefix="/internal/cron", tags=["cron"], include_in_schema=False)


def require_cron_secret(
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = settings.cron_secret
    if secret is None or not secret.get_secret_value():
        raise HTTPException(status_code=404, detail="notFound")
    if x_cron_secret is None or not hmac.compare_digest(
        x_cron_secret.encode(), secret.get_secret_value().encode()
    ):
        raise HTTPException(status_code=401, detail="invalidCronSecret")


@router.post(
    "/tick",
    response_model=CronTickOut,
    dependencies=[Depends(require_cron_secret)],
    responses={
        401: {
            "model": ErrorOut,
            "description": "Missing or wrong cron secret",
            "content": {
                "application/json": {"example": {"detail": "invalidCronSecret"}}
            },
        },
    },
)
def tick() -> CronTickOut:
    """Runs the reminder and bank-inbox jobs. Called hourly by GitHub Actions
    so the app can scale to zero between calls."""
    return run_tick()
