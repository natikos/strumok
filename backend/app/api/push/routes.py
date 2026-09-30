from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_current_user, require_internal_secret
from app.api.push.schemas import (
    PushSubscriptionIn,
    PushUnsubscribeIn,
    SendRemindersOut,
    VapidPublicKeyOut,
)
from app.api.push.service import (
    ReminderVariant,
    delete_subscription,
    send_reminders,
    upsert_subscription,
)
from app.core.config import settings
from app.db import get_session
from app.db.models import User

router = APIRouter(prefix="/push", tags=["push"])
internal_router = APIRouter(
    prefix="/internal/push",
    tags=["push-internal"],
    dependencies=[Depends(require_internal_secret)],
    include_in_schema=False,
)


@router.get("/vapid-public-key", response_model=VapidPublicKeyOut)
def get_vapid_public_key() -> VapidPublicKeyOut:
    return VapidPublicKeyOut(public_key=settings.push.vapid_public_key)


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def subscribe(
    payload: PushSubscriptionIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    upsert_subscription(
        session=session,
        user=current_user,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
    )


@router.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: PushUnsubscribeIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    delete_subscription(session=session, user=current_user, endpoint=payload.endpoint)


@internal_router.post("/send-reminders", response_model=SendRemindersOut)
def trigger_send_reminders(
    variant: ReminderVariant = "opening",
    session: Session = Depends(get_session),
) -> SendRemindersOut:
    sent, removed = send_reminders(session=session, variant=variant)
    return SendRemindersOut(sent=sent, removed=removed)
