from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.api.push.schemas import (
    PushSubscriptionIn,
    PushUnsubscribeIn,
    SendRemindersOut,
    VapidPublicKeyOut,
)
from app.api.push.service import (
    delete_subscription,
    send_test_notification,
    upsert_subscription,
)
from app.core.config import settings
from app.db import get_session
from app.db.models import User

router = APIRouter(prefix="/push", tags=["push"])


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


# TEMPORARY: manual verification endpoint, see send_test_notification (#94).
@router.post("/test", response_model=SendRemindersOut)
def send_test(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SendRemindersOut:
    sent, removed = send_test_notification(session=session, user=current_user)
    return SendRemindersOut(sent=sent, removed=removed)
