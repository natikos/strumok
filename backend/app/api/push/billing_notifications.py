"""Billing notifications: bill ready, restatement corrections, and the head's
day-6 missing-readings summary. Each goes out only after the triggering
transaction has committed, through `notification_log` so a retry or a second
instance never notifies the same user twice for the same event."""

import html
import json
import logging
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, delete, select

from app.api.billing.shortfall import household_shortfall, settled_window
from app.api.push.service import SendOutcome, send_one
from app.core.email import EmailSendError, send_email
from app.core.time import utc_now
from app.db.models import (
    Household,
    HouseholdCharge,
    LanguageCode,
    MeterReading,
    NotificationLog,
    PushSubscription,
    User,
)

logger = logging.getLogger(__name__)

Content = dict[str, str]


def _lang(user: User) -> LanguageCode:
    return user.language if user.language in LanguageCode else LanguageCode.UA


def _signed(amount: Decimal) -> str:
    return f"{amount:+.2f}"


def bill_ready_content(
    user: User, *, period: str, total: Decimal, estimated: bool
) -> Content:
    if _lang(user) == LanguageCode.EN:
        body = f"Your {period} bill: {total:.2f} ₴."
        if estimated:
            body += " Includes an estimate for a missed reading."
        return {"title": "Your bill is ready", "body": body}
    body = f"Ваш рахунок за {period}: {total:.2f} ₴."
    if estimated:
        body += " Включає оцінку за неподані показники."
    return {"title": "Ваш рахунок готовий", "body": body}


def correction_content(user: User, *, period: str, delta: Decimal) -> Content:
    if _lang(user) == LanguageCode.EN:
        return {
            "title": "Your bill was corrected",
            "body": f"Your {period} bill was corrected: {_signed(delta)} ₴.",
        }
    return {
        "title": "Ваш рахунок скориговано",
        "body": f"Рахунок за {period} скориговано: {_signed(delta)} ₴.",
    }


def missing_readings_content(
    user: User, *, period: str, names: Sequence[str]
) -> Content:
    listed = ", ".join(names)
    if _lang(user) == LanguageCode.EN:
        return {
            "title": "Readings are missing",
            "body": f"{len(names)} households haven't submitted {period}: {listed}",
        }
    return {
        "title": "Бракує показників",
        "body": f"{len(names)} ділянок не подали показники за {period}: {listed}",
    }


def _claim(session: Session, user_ids: set[int], period: str, variant: str) -> set[int]:
    if not user_ids:
        return set()
    rows = session.exec(
        insert(NotificationLog)
        .values(
            [
                {
                    "user_id": u,
                    "period": period,
                    "variant": variant,
                    "sent_at": utc_now(),
                }
                for u in user_ids
            ]
        )
        .on_conflict_do_nothing(index_elements=["user_id", "period", "variant"])
        .returning(col(NotificationLog.user_id))
    ).all()
    session.commit()
    return {row[0] for row in rows}


def _email_fallback(user: User, content: Content) -> bool:
    try:
        send_email(
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject=content["title"],
            html_content=f"<p>{html.escape(content['body'])}</p>",
        )
    except EmailSendError:
        return False
    return True


def notify_users(
    *,
    session: Session,
    period: str,
    variant: str,
    content_for: dict[int, Content],
) -> int:
    """Claims then delivers: push to every subscription, email when the user
    has none. A claim is released if nothing reached the user so a later run
    retries. Returns the number of users reached."""
    claimed = _claim(session, set(content_for), period, variant)
    if not claimed:
        return 0
    users = {
        u.id: u
        for u in session.exec(
            select(User).where(col(User.id).in_(claimed), User.is_active)
        )
    }
    subs: dict[int, list[PushSubscription]] = {}
    for sub in session.exec(
        select(PushSubscription).where(col(PushSubscription.user_id).in_(claimed))
    ):
        subs.setdefault(sub.user_id, []).append(sub)

    reached: set[int] = set()
    for user_id in claimed:
        user = users.get(user_id)
        if user is None:
            continue
        content = content_for[user_id]
        outcomes = []
        for sub in subs.get(user_id, []):
            outcome = send_one(sub, json.dumps({**content, "url": "/"}), ttl=86400)
            if outcome == SendOutcome.GONE:
                session.delete(sub)
            outcomes.append(outcome)
        if SendOutcome.SENT in outcomes or (
            not outcomes and _email_fallback(user, content)
        ):
            reached.add(user_id)
    unreached = claimed - reached
    if unreached:
        session.exec(
            delete(NotificationLog)
            .where(col(NotificationLog.user_id).in_(unreached))
            .where(col(NotificationLog.period) == period)
            .where(col(NotificationLog.variant) == variant)
        )
    session.commit()
    return len(reached)


def notify_bill_ready(*, session: Session, period: str) -> int:
    """One notification per resident owning charged households, summing their
    households' totals. Call after the close has committed."""
    charges = session.exec(
        select(HouseholdCharge).where(HouseholdCharge.period == period)
    ).all()
    totals: dict[int, Decimal] = {}
    estimated: set[int] = set()
    for charge in charges:
        if charge.owner_user_id is None:
            continue
        totals[charge.owner_user_id] = (
            totals.get(charge.owner_user_id, Decimal("0.00")) + charge.total_uah
        )
        if charge.is_estimated:
            estimated.add(charge.owner_user_id)
    users = {
        u.id: u for u in session.exec(select(User).where(col(User.id).in_(totals)))
    }
    content = {
        uid: bill_ready_content(
            users[uid], period=period, total=total, estimated=uid in estimated
        )
        for uid, total in totals.items()
        if uid in users
    }
    return notify_users(
        session=session, period=period, variant="billReady", content_for=content
    )


def notify_corrections(
    *,
    session: Session,
    restatement_id: int,
    period: str,
    deltas: dict[int, Decimal],
) -> int:
    """`deltas` maps owner user id to their summed adjustment; zero nets are
    skipped. Call after the restatement has committed."""
    users = {
        u.id: u for u in session.exec(select(User).where(col(User.id).in_(deltas)))
    }
    content = {
        uid: correction_content(users[uid], period=period, delta=delta)
        for uid, delta in deltas.items()
        if delta != 0 and uid in users
    }
    return notify_users(
        session=session,
        period=period,
        variant=f"corrected:{restatement_id}",
        content_for=content,
    )


def notify_missing_readings(*, session: Session, period: str) -> int:
    """Tells each active admin which active households have no reading for `period`."""
    names = list(
        session.exec(
            select(Household.name)
            .outerjoin(
                MeterReading,
                (col(MeterReading.household_id) == Household.id)
                & (col(MeterReading.period) == period),
            )
            .where(Household.is_active, col(MeterReading.household_id).is_(None))
            .order_by(Household.name)
        ).all()
    )
    if not names:
        return 0
    admins = session.exec(select(User).where(User.is_admin, User.is_active)).all()
    content = {
        a.id: missing_readings_content(a, period=period, names=names) for a in admins
    }
    return notify_users(
        session=session, period=period, variant="missingReadings", content_for=content
    )


def bank_queue_content(user: User) -> Content:
    if _lang(user) == LanguageCode.EN:
        return {
            "title": "Bank payments to review",
            "body": "A new statement has payments waiting for review.",
        }
    return {
        "title": "Платежі банку на розгляд",
        "body": "Нова виписка містить платежі, що чекають на розгляд.",
    }


def notify_bank_queue(*, session: Session, file_id: int) -> int:
    """Tells each active admin a statement added rows to the review queue."""
    admins = session.exec(select(User).where(User.is_admin, User.is_active)).all()
    return notify_users(
        session=session,
        period=f"bank-file-{file_id}",
        variant="bankQueue",
        content_for={a.id: bank_queue_content(a) for a in admins},
    )


def shortfall_content(user: User, *, period: str, owed: Decimal) -> Content:
    if _lang(user) == LanguageCode.EN:
        return {
            "title": "Payment due",
            "body": f"Your {period} bill is past due. You still owe {owed:.2f} ₴.",
        }
    return {
        "title": "Час сплатити",
        "body": f"Термін оплати за {period} минув. Ви ще винні {owed:.2f} ₴.",
    }


def ownerless_shortfall_content(
    user: User, *, period: str, names: Sequence[str]
) -> Content:
    listed = ", ".join(names)
    if _lang(user) == LanguageCode.EN:
        return {
            "title": "Unpaid households without an owner",
            "body": f"{len(names)} households owe for {period} but have no owner: {listed}",
        }
    return {
        "title": "Борг ділянок без власника",
        "body": f"{len(names)} ділянок мають борг за {period}, але не мають власника: {listed}",
    }


def notify_shortfall(*, session: Session) -> int:
    """Once the statement has covered the due date with the review queue clear,
    tells each owner who still owes their current balance (overpaid owners get
    nothing) and the admins which indebted households have no owner. Safe to
    call after every import and close: `notification_log` makes it once."""
    window = settled_window(session)
    if window is None:
        return 0
    owed_by_user: dict[int, Decimal] = {}
    ownerless: list[str] = []
    for household in session.exec(
        select(Household).where(Household.is_active).order_by(Household.name)
    ):
        owed = household_shortfall(session, window, household)
        if owed <= 0:
            continue
        if household.user_id is None:
            ownerless.append(household.name)
        else:
            owed_by_user[household.user_id] = (
                owed_by_user.get(household.user_id, Decimal("0.00")) + owed
            )
    users = {
        u.id: u
        for u in session.exec(select(User).where(col(User.id).in_(owed_by_user)))
    }
    reached = notify_users(
        session=session,
        period=window.period,
        variant="shortfall",
        content_for={
            uid: shortfall_content(users[uid], period=window.period, owed=owed)
            for uid, owed in owed_by_user.items()
            if uid in users
        },
    )
    if ownerless:
        admins = session.exec(select(User).where(User.is_admin, User.is_active)).all()
        reached += notify_users(
            session=session,
            period=window.period,
            variant="shortfallOwnerless",
            content_for={
                a.id: ownerless_shortfall_content(
                    a, period=window.period, names=ownerless
                )
                for a in admins
            },
        )
    return reached
