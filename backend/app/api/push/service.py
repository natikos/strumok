import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pywebpush import WebPushException, webpush
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.config import settings
from app.core.domain import current_billing_period
from app.core.time import utc_now
from app.db.models import (
    Household,
    MeterReading,
    NotificationLog,
    PushSubscription,
    ReminderDispatch,
    User,
)

logger = logging.getLogger(__name__)

ReminderVariant = Literal["opening", "final"]

# Reminder window is days 1-5 of the month; keep messages queued by the push
# service for that long instead of the pywebpush default (ttl=0, drop if the
# device is offline right now).
_REMINDER_TTL_SECONDS = 5 * 24 * 60 * 60
_MAX_CONCURRENT_SENDS = 10

_NOTIFICATION_CONTENT: dict[ReminderVariant, dict[str, str]] = {
    "opening": {
        "title": "Meter reading window is open",
        "body": "Submit your day/night reading by the 5th.",
    },
    "final": {
        "title": "Last day to submit your reading",
        "body": "Today's the deadline — submit before midnight.",
    },
}


def upsert_subscription(
    *, session: Session, user: User, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    existing = session.exec(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).first()

    if existing is not None:
        existing.user_id = user.id  # type: ignore[assignment]
        existing.p256dh = p256dh
        existing.auth = auth
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    subscription = PushSubscription(
        user_id=user.id,  # type: ignore[arg-type]
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


def delete_subscription(*, session: Session, user: User, endpoint: str) -> None:
    subscription = session.exec(
        select(PushSubscription)
        .where(PushSubscription.endpoint == endpoint)
        .where(PushSubscription.user_id == user.id)
    ).first()

    if subscription is not None:
        session.delete(subscription)
        session.commit()


def _send_one(
    subscription: PushSubscription, payload: str
) -> tuple[PushSubscription, str]:
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
            ttl=_REMINDER_TTL_SECONDS,
            headers={"Urgency": "normal"},
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (404, 410):
            return subscription, "remove"
        logger.exception("Push send failed for subscription %s", subscription.id)
        return subscription, "error"
    except Exception:
        # Anything else (network errors, malformed stored keys, ...) must not
        # escape the worker thread: executor.map() re-raises it at this item's
        # position while send_reminders() iterates results, which would abort
        # the whole batch and roll back every deletion already staged for
        # subscriptions handled earlier in the same run.
        logger.exception("Push send failed for subscription %s", subscription.id)
        return subscription, "error"
    return subscription, "sent"


def _get_or_create_dispatch(
    *, session: Session, period: str, variant: ReminderVariant
) -> ReminderDispatch:
    """A repeated call for the same (period, variant) must reuse the same
    dispatch row rather than erroring on the unique constraint -- an external
    cron retrying, or two overlapping runs, are exactly the case this exists
    to make safe."""
    stmt = (
        insert(ReminderDispatch)
        .values(period=period, variant=variant, started_at=utc_now())
        .on_conflict_do_nothing(index_elements=["period", "variant"])
    )
    session.exec(stmt)
    session.commit()

    dispatch = session.exec(
        select(ReminderDispatch)
        .where(ReminderDispatch.period == period)
        .where(ReminderDispatch.variant == variant)
    ).one()
    return dispatch


def send_reminders(*, session: Session, variant: ReminderVariant) -> tuple[int, int]:
    """Send a push reminder to every subscribed, active user with an active,
    unsubmitted household reading for the current period, skipping anyone
    already notified for this (period, variant, channel) -- so calling this
    more than once for the same period and variant (an external cron
    retrying, or two overlapping runs) delivers at most one notification per
    user. Returns (sent, removed) counts for this call."""
    content = _NOTIFICATION_CONTENT[variant]
    period = current_billing_period()
    channel = "push"

    dispatch = _get_or_create_dispatch(session=session, period=period, variant=variant)

    already_notified_user_ids = set(
        session.exec(
            select(NotificationLog.user_id)
            .where(NotificationLog.period == period)
            .where(NotificationLog.variant == variant)
            .where(NotificationLog.channel == channel)
            .where(NotificationLog.status == "sent")
        ).all()
    )

    households_by_user: dict[int, list[int]] = defaultdict(list)
    for household_id, user_id in session.exec(
        select(Household.id, Household.user_id)
        .join(User, User.id == Household.user_id)
        .where(Household.user_id.is_not(None))
        .where(Household.is_active == True)  # noqa: E712
        .where(User.is_active == True)  # noqa: E712
    ).all():
        households_by_user[user_id].append(household_id)

    submitted_household_ids = set(
        session.exec(
            select(MeterReading.household_id).where(MeterReading.period == period)
        ).all()
    )

    subscriptions_by_user: dict[int, list[PushSubscription]] = defaultdict(list)
    for subscription in session.exec(select(PushSubscription)).all():
        subscriptions_by_user[subscription.user_id].append(subscription)

    due_user_ids: list[int] = []
    for user_id, subscriptions in subscriptions_by_user.items():
        if user_id in already_notified_user_ids:
            continue
        household_ids = households_by_user.get(user_id, [])
        if not household_ids:
            continue
        if all(
            household_id in submitted_household_ids for household_id in household_ids
        ):
            continue
        due_user_ids.append(user_id)

    payload = _notification_payload(content)
    due_items = [
        (user_id, subscription)
        for user_id in due_user_ids
        for subscription in subscriptions_by_user[user_id]
    ]

    sent = 0
    removed = 0
    notified_user_ids: set[int] = set()
    # Bounded concurrency: each webpush() call is a blocking HTTP request, and a serial
    # loop over hundreds of subscriptions could stall the whole request for one slow push
    # service. A thread pool keeps requests in flight without unbounded concurrency.
    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_SENDS) as executor:
        for user_id, subscription, outcome in executor.map(
            lambda item: (item[0], *_send_one(item[1], payload)), due_items
        ):
            if outcome == "sent":
                sent += 1
                notified_user_ids.add(user_id)
            elif outcome == "remove":
                session.delete(subscription)
                removed += 1

    if notified_user_ids:
        log_stmt = (
            insert(NotificationLog)
            .values(
                [
                    {
                        "user_id": user_id,
                        "period": period,
                        "variant": variant,
                        "channel": channel,
                        "status": "sent",
                        "sent_at": utc_now(),
                    }
                    for user_id in notified_user_ids
                ]
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "period", "variant", "channel"]
            )
        )
        session.exec(log_stmt)

    dispatch.finished_at = utc_now()
    dispatch.sent += len(notified_user_ids)
    dispatch.removed += removed
    session.add(dispatch)

    session.commit()
    return sent, removed


def _notification_payload(content: dict[str, str]) -> str:
    return json.dumps({**content, "url": "/"})


# TEMPORARY: manual end-to-end check that a deployed subscription actually
# receives a push, without waiting for the scheduled reminder or depending on
# submission status. Safe to remove once push has been verified in production
# (issue #94).
def send_test_notification(*, session: Session, user: User) -> tuple[int, int]:
    subscriptions = session.exec(
        select(PushSubscription).where(PushSubscription.user_id == user.id)
    ).all()
    payload = _notification_payload(
        {"title": "Strumok", "body": "Test notification -- push is working."}
    )

    sent = 0
    removed = 0
    for subscription in subscriptions:
        _, outcome = _send_one(subscription, payload)
        if outcome == "sent":
            sent += 1
        elif outcome == "remove":
            session.delete(subscription)
            removed += 1

    session.commit()
    return sent, removed
