import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pywebpush import WebPushException, webpush
from sqlmodel import Session, select

from app.core.config import settings
from app.core.domain import current_billing_period
from app.db.models import Household, MeterReading, PushSubscription, User

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


def send_reminders(*, session: Session, variant: ReminderVariant) -> tuple[int, int]:
    """Send a push reminder to every subscribed user with an unsubmitted household
    reading for the current period. Returns (sent, removed) counts."""
    content = _NOTIFICATION_CONTENT[variant]
    period = current_billing_period()

    households_by_user: dict[int, list[int]] = defaultdict(list)
    for household_id, user_id in session.exec(
        select(Household.id, Household.user_id).where(Household.user_id.is_not(None))
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

    due_subscriptions: list[PushSubscription] = []
    for user_id, subscriptions in subscriptions_by_user.items():
        household_ids = households_by_user.get(user_id, [])
        if not household_ids:
            continue
        if all(
            household_id in submitted_household_ids for household_id in household_ids
        ):
            continue
        due_subscriptions.extend(subscriptions)

    payload = _notification_payload(content)
    sent = 0
    removed = 0
    # Bounded concurrency: each webpush() call is a blocking HTTP request, and a serial
    # loop over hundreds of subscriptions could stall the whole request for one slow push
    # service. A thread pool keeps requests in flight without unbounded concurrency.
    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_SENDS) as executor:
        for subscription, outcome in executor.map(
            lambda subscription: _send_one(subscription, payload), due_subscriptions
        ):
            if outcome == "sent":
                sent += 1
            elif outcome == "remove":
                session.delete(subscription)
                removed += 1

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
