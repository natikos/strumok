import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import SecretStr

from app.api.auth.schemas import ErrorOut
from app.api.cron.schemas import CronTickOut
from app.api.cron.service import run_inbox_only, run_tick
from app.core.config import settings

router = APIRouter(prefix="/internal/cron", tags=["cron"], include_in_schema=False)
inbox_router = APIRouter(
    prefix="/internal/inbox", tags=["cron"], include_in_schema=False
)


def _check_secret(configured: SecretStr | None, given: str | None) -> None:
    if configured is None or not configured.get_secret_value():
        raise HTTPException(status_code=404, detail="notFound")
    if given is None or not hmac.compare_digest(
        given.encode(), configured.get_secret_value().encode()
    ):
        raise HTTPException(status_code=401, detail="invalidCronSecret")


def require_cron_secret(
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    _check_secret(settings.cron_secret, x_cron_secret)


def require_inbox_trigger_secret(
    x_cron_secret: Annotated[str | None, Header()] = None,
) -> None:
    _check_secret(settings.inbox_trigger_secret, x_cron_secret)


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
    """Runs the reminder and bank-inbox jobs. Called hourly by GitHub Actions on the days jobs are due
    so the app can scale to zero between calls."""
    return run_tick()


@inbox_router.post(
    "/check",
    response_model=CronTickOut,
    dependencies=[Depends(require_inbox_trigger_secret)],
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
def inbox() -> CronTickOut:
    """Runs only the bank-inbox check. Called by the Gmail Apps Script when a
    statement email arrives."""
    return run_inbox_only()
