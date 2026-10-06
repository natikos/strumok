import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pywebpush import WebPushException, webpush
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.domain import current_billing_period
from app.db.models import Household, LanguageCode, MeterReading, PushSubscription, User

logger = logging.getLogger(__name__)

ReminderVariant = Literal["opening", "final"]

# Reminder window is days 1-5 of the month; keep messages queued by the push
# service for that long instead of the pywebpush default (ttl=0, drop if the
# device is offline right now).
_REMINDER_TTL_SECONDS = 5 * 24 * 60 * 60
_MAX_CONCURRENT_SENDS = 10

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
    period = current_billing_period()

    households_by_user: dict[int, list[int]] = defaultdict(list)
    active_households = (
        select(Household.id, Household.user_id)
        .join(User)
        .where(Household.is_active)
        .where(User.is_active)
    )
    rows = session.exec(active_households).all()
    for household_id, user_id in rows:
        if household_id is None or user_id is None:
            continue
        households_by_user[user_id].append(household_id)

    submitted_household_ids = set(
        session.exec(
            select(MeterReading.household_id).where(MeterReading.period == period)
        ).all()
    )

    subscriptions_by_user: dict[int, list[PushSubscription]] = defaultdict(list)
    for subscription in session.exec(select(PushSubscription)).all():
        subscriptions_by_user[subscription.user_id].append(subscription)

    users_by_id = {
        user.id: user
        for user in session.exec(
            select(User).where(col(User.id).in_(subscriptions_by_user.keys()))
        ).all()
    }

    due_subscriptions: list[tuple[PushSubscription, str]] = []
    for user_id, subscriptions in subscriptions_by_user.items():
        household_ids = households_by_user.get(user_id, [])
        if not household_ids:
            continue
        if all(
            household_id in submitted_household_ids for household_id in household_ids
        ):
            continue
        user = users_by_id.get(user_id)
        if user is None:
            continue
        payload = _notification_payload(_content_for(user, variant))
        due_subscriptions.extend(
            (subscription, payload) for subscription in subscriptions
        )

    sent = 0
    removed = 0
    # Bounded concurrency: each webpush() call is a blocking HTTP request, and a serial
    # loop over hundreds of subscriptions could stall the whole request for one slow push
    # service. A thread pool keeps requests in flight without unbounded concurrency.
    with ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_SENDS) as executor:
        for subscription, outcome in executor.map(
            lambda item: _send_one(item[0], item[1]), due_subscriptions
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

