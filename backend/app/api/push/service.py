import json
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from http import HTTPStatus
from typing import Literal

from pywebpush import WebPushException, webpush
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.core.domain import current_billing_period
from app.core.time import utc_now
from app.db.models import (
    Household,
    LanguageCode,
    MeterReading,
    NotificationLog,
    PushSubscription,
    User,
)

logger = logging.getLogger(__name__)

ReminderVariant = Literal["opening", "final"]

# Keyed by language so this stays separate from the frontend's vue-i18n JSON:
# the service worker renders the payload as-is, with no client-side lookup.
_NOTIFICATION_CONTENT: dict[LanguageCode, dict[ReminderVariant, dict[str, str]]] = {
    LanguageCode.EN: {
        "opening": {
            "title": "Meter reading window is open",
            "body": "Submit your day/night reading by the 5th.",
        },
        "final": {
            "title": "Last day to submit your reading",
            "body": "Today's the deadline — submit before midnight.",
        },
    },
    LanguageCode.UA: {
        "opening": {
            "title": "Відкрито подання показників лічильника",
            "body": "Подайте денний/нічний показник до 5 числа.",
        },
        "final": {
            "title": "Останній день подання показників",
            "body": "Сьогодні дедлайн — подайте показники до півночі.",
        },
    },
}


def _content_for(user: User, variant: ReminderVariant) -> dict[str, str]:
    catalog = _NOTIFICATION_CONTENT.get(
        user.language, _NOTIFICATION_CONTENT[LanguageCode.UA]
    )
    return catalog[variant]


def upsert_subscription(
    *, session: Session, user: User, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    stmt = (
        insert(PushSubscription)
        .values(user_id=user.id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        .on_conflict_do_update(
            index_elements=["endpoint"],
            set_={"user_id": user.id, "p256dh": p256dh, "auth": auth},
        )
        .returning(PushSubscription)
    )
    subscription = session.exec(stmt).scalar_one()
    session.commit()
    return subscription


def delete_subscription(*, session: Session, user: User, endpoint: str) -> None:
    session.exec(
        delete(PushSubscription)
        .where(col(PushSubscription.endpoint) == endpoint)
        .where(col(PushSubscription.user_id) == user.id)
    )
    session.commit()


class _SendOutcome(StrEnum):
    SENT = "sent"
    GONE = "gone"
    FAILED = "failed"


def _seconds_until_window_closes() -> int:
    """Seconds left in the submission window (days 1-5, UTC). Used as the push
    TTL so an offline device still gets the reminder when it reconnects, but a
    reminder is dropped rather than delivered after the deadline has passed."""
    now = utc_now()
    window_end = now.replace(day=6, hour=0, minute=0, second=0, microsecond=0)
    return max(int((window_end - now).total_seconds()), 0)


def _send_one(subscription: PushSubscription, payload: str) -> _SendOutcome:
    """Send to a single subscription. Runs on a worker thread; must not touch the session."""
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=payload,
            vapid_private_key=settings.push.vapid_private_key.get_secret_value(),
            vapid_claims={"sub": settings.push.vapid_subject},
            ttl=_seconds_until_window_closes(),
            headers={"Urgency": "normal"},
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
            return _SendOutcome.GONE
        logger.exception("Push send failed for subscription %s", subscription.id)
        return _SendOutcome.FAILED
    except Exception:
        logger.exception("Push send failed for subscription %s", subscription.id)
        return _SendOutcome.FAILED
    return _SendOutcome.SENT


def _due_subscriptions(
    *, session: Session, period: str, variant: ReminderVariant
) -> Sequence[PushSubscription]:
    """Subscriptions of active users who still owe a reading this period and
    haven't been sent this variant yet."""
    query = (
        select(PushSubscription)
        .join(User, col(User.id) == PushSubscription.user_id)
        .join(Household, col(Household.user_id) == User.id)
        .outerjoin(
            MeterReading,
            and_(
                col(MeterReading.household_id) == Household.id,
                col(MeterReading.period) == period,
            ),
        )
        .outerjoin(
            NotificationLog,
            and_(
                col(NotificationLog.user_id) == User.id,
                col(NotificationLog.period) == period,
                col(NotificationLog.variant) == variant,
            ),
        )
        .where(
            User.is_active,
            Household.is_active,
            col(MeterReading.household_id).is_(None),
            col(NotificationLog.user_id).is_(None),
        )
        .distinct()
    )
    return session.exec(query).all()


def _record_notified(
    *, session: Session, user_ids: set[int], period: str, variant: ReminderVariant
) -> None:
    session.exec(
        insert(NotificationLog)
        .values(
            [
                {
                    "user_id": user_id,
                    "period": period,
                    "variant": variant,
                    "sent_at": utc_now(),
                }
                for user_id in user_ids
            ]
        )
        .on_conflict_do_nothing(index_elements=["user_id", "period", "variant"])
    )


def send_reminders(*, session: Session, variant: ReminderVariant) -> tuple[int, int]:
    """Push a reminder to each subscribed, active user with an unsubmitted
    household reading this period. Idempotent per (period, variant):
    repeat or overlapping calls notify each user at most once. Returns
    (sent, removed) counts."""
    period = current_billing_period()
    subscriptions = _due_subscriptions(session=session, period=period, variant=variant)
    users_by_id = {
        user.id: user
        for user in session.exec(
            select(User).where(col(User.id).in_({sub.user_id for sub in subscriptions}))
        ).all()
    }
    payloads = [
        _notification_payload(_content_for(users_by_id[sub.user_id], variant))
        for sub in subscriptions
    ]

    # webpush() is a blocking HTTP call to the browser vendor's push service. Sending
    # serially would make the run take the sum of every round trip, so one slow or
    # timing-out endpoint delays all the others. The pool overlaps the waiting, and the
    # worker cap keeps us from opening hundreds of connections at once.
    with ThreadPoolExecutor(max_workers=10) as executor:
        outcomes = executor.map(_send_one, subscriptions, payloads)
        results = list(zip(subscriptions, outcomes))

    sent = [sub for sub, outcome in results if outcome == _SendOutcome.SENT]
    gone = [sub for sub, outcome in results if outcome == _SendOutcome.GONE]

    for subscription in gone:
        session.delete(subscription)
    if sent:
        _record_notified(
            session=session,
            user_ids={sub.user_id for sub in sent},
            period=period,
            variant=variant,
        )

    session.commit()
    return len(sent), len(gone)


def _notification_payload(content: dict[str, str]) -> str:
    return json.dumps({**content, "url": "/"})
