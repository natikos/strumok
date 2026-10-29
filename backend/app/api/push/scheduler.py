import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.api.bank.inbox import (
    InboxNotConfiguredError,
    InboxUnavailableError,
    check_inbox,
)
from app.api.push.billing_notifications import notify_missing_readings
from app.api.push.service import send_reminders
from app.core.domain import SUBMISSION_DEADLINE_DAY, current_billing_period
from app.core.domain.billing import kyiv_now
from app.db.engine import engine

MISSING_READINGS_DAY = SUBMISSION_DEADLINE_DAY + 1

logger = logging.getLogger(__name__)


def _run_reminders() -> None:
    with Session(engine) as session:
        try:
            now = kyiv_now()
            if now.day == MISSING_READINGS_DAY and now.hour >= 9:
                notify_missing_readings(
                    session=session, period=current_billing_period(now)
                )
            sent, removed = send_reminders(session=session, now=now)
            if sent or removed:
                logger.info(
                    "Sent %s push reminders (%s dead subscriptions removed)",
                    sent,
                    removed,
                )
        except Exception:
            logger.exception("Scheduled push reminder send failed")


def _run_inbox_check() -> None:
    with Session(engine) as session:
        try:
            result = check_inbox(session)
            if result.received:
                logger.info(
                    "Bank inbox: %s received, %s imported, %s rejected",
                    result.received,
                    result.imported,
                    result.rejected,
                )
        except InboxNotConfiguredError, InboxUnavailableError:
            pass
        except Exception:
            logger.exception("Scheduled bank inbox check failed")


def start_reminder_scheduler() -> AsyncIOScheduler:
    """Runs in-process: an hourly inbox check for the accountant's bank
    statement (a no-op until IMAP is configured), and an hourly job that sends the day-1 'opening' and
    day-5 'final' reminders to users whose chosen Kyiv hour has arrived.
    Kyiv's UTC offset is a whole number of hours, so minute 0 UTC is minute
    0 Kyiv."""

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_reminders,
        CronTrigger(minute=0),
        id="push-reminders-hourly",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_inbox_check,
        CronTrigger(minute=30),
        id="bank-inbox-hourly",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
