import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session

from app.api.bank.inbox import (
    InboxNotConfiguredError,
    InboxUnavailableError,
    check_inbox,
)
from app.api.cron.schemas import CronTickOut, InboxOut
from app.api.push.billing_notifications import notify_missing_readings
from app.api.push.service import send_reminders
from app.core.domain import SUBMISSION_DEADLINE_DAY, current_billing_period
from app.core.domain.billing import kyiv_now
from app.db.engine import engine

MISSING_READINGS_DAY = SUBMISSION_DEADLINE_DAY + 1

_REMINDERS_LOCK = 357_001
_INBOX_LOCK = 357_002

logger = logging.getLogger(__name__)


@contextmanager
def _job_lock(key: int) -> Iterator[bool]:
    """Postgres advisory lock held on its own connection (jobs commit, so a
    transaction-scoped lock would be released midway). Yields False when another
    run holds it."""
    with engine.connect() as conn:
        got = bool(
            conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar()
        )
        try:
            yield got
        finally:
            if got:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            conn.commit()


def run_reminders(out: CronTickOut) -> None:
    with _job_lock(_REMINDERS_LOCK) as got:
        if not got:
            out.reminders_status = "busy"
            return
        with Session(engine) as session:
            now = kyiv_now()
            if now.day == MISSING_READINGS_DAY and now.hour >= 9:
                notify_missing_readings(
                    session=session, period=current_billing_period(now)
                )
            sent, removed = send_reminders(session=session, now=now)
        out.reminders_sent, out.reminders_removed = sent, removed
        out.reminders_status = "ok"


def run_inbox_check(out: CronTickOut) -> None:
    with _job_lock(_INBOX_LOCK) as got:
        if not got:
            out.inbox_status = "busy"
            return
        with Session(engine) as session:
            try:
                result = check_inbox(session)
            except InboxNotConfiguredError:
                out.inbox_status = "notConfigured"
                return
            except InboxUnavailableError:
                out.inbox_status = "unavailable"
                return
        out.inbox = InboxOut(
            received=result.received,
            imported=result.imported,
            rejected=result.rejected,
        )
        out.inbox_status = "ok"


def run_tick() -> CronTickOut:
    """Runs both jobs, each isolated from the other's failure. A reminder
    failure is re-raised after the inbox check so the caller can report it."""
    out = CronTickOut(reminders_status="failed", inbox_status="failed")
    reminders_error: Exception | None = None
    try:
        run_reminders(out)
    except Exception as exc:
        logger.exception("Cron reminder run failed")
        reminders_error = exc
    try:
        run_inbox_check(out)
    except Exception:
        logger.exception("Cron bank inbox check failed")
    if reminders_error is not None:
        raise reminders_error
    return out


def run_inbox_only() -> CronTickOut:
    """Only the bank inbox check, for the Gmail Apps Script trigger."""
    out = CronTickOut(reminders_status="skipped", inbox_status="failed")
    try:
        run_inbox_check(out)
    except Exception:
        logger.exception("Cron bank inbox check failed")
        raise
    return out
