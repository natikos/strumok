import html
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from http import HTTPStatus
from typing import Literal

from pywebpush import WebPushException, webpush
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, delete, select

from app.api.auth.service import build_action_email_html
from app.core.config import settings
from app.core.domain import (
    SUBMISSION_DEADLINE_DAY,
    SUBMISSION_OPEN_DAY,
    current_billing_period,
)
from app.core.domain.billing import kyiv_now
from app.core.email import EmailSendError, send_email
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

# ENVIRONMENT=e2e only: pushes land here instead of the browser vendor.
e2e_push_outbox: list[dict[str, str]] = []

ReminderVariant = Literal["opening", "final"]

# Keyed by language so this stays separate from the frontend's vue-i18n JSON:
# the service worker renders the payload as-is, with no client-side lookup.
_NOTIFICATION_CONTENT: dict[LanguageCode, dict[ReminderVariant, dict[str, str]]] = {
    LanguageCode.EN: {
        "opening": {
            "title": "Meter reading window is open",
            "body": f"Submit your day/night reading by the {SUBMISSION_DEADLINE_DAY}th.",
        },
        "final": {
            "title": "Last day to submit your reading",
            "body": "Today's the deadline — submit before midnight.",
        },
    },
    LanguageCode.UA: {
        "opening": {
            "title": "Відкрито подання показників лічильника",
            "body": f"Подайте денний/нічний показник до {SUBMISSION_DEADLINE_DAY} числа.",
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


_EMAIL_CONTENT: dict[LanguageCode, dict[str, str]] = {
    LanguageCode.EN: {
        "opening_subject": "[Strumok] Submit your meter reading by {date}",
        "final_subject": "[Strumok] Last day to submit your meter reading",
        "greeting": "Hi {name},",
        "message": "It's day {day} of the submission window for {households}.",
        "button": "Submit your reading",
        "link_hint": "If the button doesn't work, copy and paste this link into your browser:",
        "footer": "Manage reminders in",
        "settings": "Settings → Notifications",
    },
    LanguageCode.UA: {
        "opening_subject": "[Strumok] Подайте показники лічильника до {date}",
        "final_subject": "[Strumok] Останній день подання показників лічильника",
        "greeting": "Вітаємо, {name}!",
        "message": "Сьогодні {day}-й день періоду подання показників для: {households}.",
        "button": "Подати показники",
        "link_hint": "Якщо кнопка не працює, скопіюйте це посилання у браузер:",
        "footer": "Керуйте нагадуваннями в",
        "settings": "Налаштування → Сповіщення",
    },
}


def _send_reminder_email(
    user: User, variant: ReminderVariant, households: list[str], now: datetime
) -> bool:
    text = _EMAIL_CONTENT.get(user.language, _EMAIL_CONTENT[LanguageCode.UA])
    base_url = settings.brevo.app_base_url
    deadline = f"{SUBMISSION_DEADLINE_DAY:02}.{now.month:02}.{now.year}"
    day = SUBMISSION_OPEN_DAY if variant == "opening" else SUBMISSION_DEADLINE_DAY
    names = html.escape(", ".join(households))
    settings_link = f"{base_url}/settings"
    try:
        send_email(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject=text[f"{variant}_subject"].format(date=deadline),
            html_content=build_action_email_html(
                first_name=html.escape(user.first_name),
                greeting=text["greeting"].format(name=html.escape(user.first_name)),
                message=text["message"].format(day=day, households=names),
                link=f"{base_url}/",
                button_label=text["button"],
                link_hint=text["link_hint"],
                footer_html=(
                    '<p class="email-footnote" style="margin: 16px 0 0; font-size: 13px; '
                    f'color: #64748b;">{text["footer"]} '
                    f'<a href="{settings_link}" class="email-link" '
                    f'style="color: #2c8ad7;">{text["settings"]}</a></p>'
                ),
            ),
        )
    except EmailSendError:
        return False
    return True


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


class SendOutcome(StrEnum):
    SENT = "sent"
    GONE = "gone"
    FAILED = "failed"


def _seconds_until_window_closes() -> int:
    """Seconds left in the submission window (Kyiv time). Used as the push
    TTL so an offline device still gets the reminder when it reconnects, but a
    reminder is dropped rather than delivered after the deadline has passed."""
    now = kyiv_now()
    window_end = now.replace(
        day=SUBMISSION_DEADLINE_DAY + 1, hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((window_end - now).total_seconds()), 0)


def send_one(
    subscription: PushSubscription, payload: str, ttl: int | None = None
) -> SendOutcome:
    """Send to a single subscription. Runs on a worker thread; must not touch the session."""
    if settings.environment == "e2e":
        # Never reach a vendor push service from a test run; the e2e suite
        # reads what would have been sent.
        e2e_push_outbox.append({"endpoint": subscription.endpoint, "payload": payload})
        return SendOutcome.SENT
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
            ttl=_seconds_until_window_closes() if ttl is None else ttl,
            headers={"Urgency": "normal"},
        )
    except WebPushException as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.GONE):
            return SendOutcome.GONE
        logger.exception("Push send failed for subscription %s", subscription.id)
        return SendOutcome.FAILED
    except Exception:
        logger.exception("Push send failed for subscription %s", subscription.id)
        return SendOutcome.FAILED
    return SendOutcome.SENT


def reminder_variant_for(now: datetime) -> ReminderVariant | None:
    """Which reminder (if any) is sent on the Kyiv calendar day of `now`.
    Days 1 and 5 never contain a DST shift (those fall on days 25-31), so
    every Kyiv hour occurs exactly once on them."""
    if now.day == SUBMISSION_OPEN_DAY:
        return "opening"
    if now.day == SUBMISSION_DEADLINE_DAY:
        return "final"
    return None


def _due_households(
    *, session: Session, period: str, variant: ReminderVariant, hour: int
) -> dict[int, list[str]]:
    """Names of the unsubmitted households of each active user whose chosen
    hour has arrived and who haven't been sent this variant. `<=` rather
    than `==` so a missed tick is caught up on the next one."""
    query = (
        select(User.id, Household.name)
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
            col(User.reminder_hour) <= hour,
            Household.is_active,
            col(MeterReading.household_id).is_(None),
            col(NotificationLog.user_id).is_(None),
        )
        .order_by(col(Household.name))
    )
    due: dict[int, list[str]] = {}
    for user_id, name in session.exec(query).all():
        due.setdefault(user_id, []).append(name)
    return due


def _claim_users(
    *, session: Session, user_ids: set[int], period: str, variant: ReminderVariant
) -> set[int]:
    """Record the send before it happens; returns the users this call won.
    A concurrent run (or another instance) gets nothing back for them, so
    each user is notified at most once per (period, variant)."""
    if not user_ids:
        return set()
    rows = session.exec(
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
        .returning(col(NotificationLog.user_id))
    ).all()
    session.commit()
    return {row[0] for row in rows}


def send_reminders(*, session: Session, now: datetime) -> tuple[int, int]:
    """Push a reminder to each subscribed, active user with an unsubmitted
    household reading whose chosen Kyiv hour has arrived; users with no
    subscription get an email instead. `now` is Kyiv time.
    At most one push per (user, period, variant): users are claimed in
    NotificationLog before sending, and the claim is released only if every
    send to that user failed, so the next hourly run retries. Returns
    (sent, removed) counts."""
    variant = reminder_variant_for(now)
    if variant is None:
        return 0, 0
    period = current_billing_period(now)
    due = _due_households(
        session=session, period=period, variant=variant, hour=now.hour
    )
    claimed = _claim_users(
        session=session, user_ids=set(due), period=period, variant=variant
    )
    subscriptions = list(
        session.exec(
            select(PushSubscription).where(col(PushSubscription.user_id).in_(claimed))
        ).all()
    )
    users_by_id = {
        user.id: user
        for user in session.exec(select(User).where(col(User.id).in_(claimed))).all()
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
        outcomes = executor.map(send_one, subscriptions, payloads)
        results = list(zip(subscriptions, outcomes))

    sent = [sub for sub, outcome in results if outcome == SendOutcome.SENT]
    gone = [sub for sub, outcome in results if outcome == SendOutcome.GONE]
    delivered_users = {
        sub.user_id for sub, outcome in results if outcome != SendOutcome.FAILED
    }
    # Users with no push subscription get the email instead.
    emailed = {
        user_id
        for user_id in claimed - {sub.user_id for sub in subscriptions}
        if _send_reminder_email(users_by_id[user_id], variant, due[user_id], now)
    }
    unreached = claimed - delivered_users - emailed

    for subscription in gone:
        session.delete(subscription)
    if unreached:
        session.exec(
            delete(NotificationLog)
            .where(col(NotificationLog.user_id).in_(unreached))
            .where(col(NotificationLog.period) == period)
            .where(col(NotificationLog.variant) == variant)
        )

    session.commit()
    return len(sent), len(gone)


def _notification_payload(content: dict[str, str]) -> str:
    return json.dumps({**content, "url": "/"})
