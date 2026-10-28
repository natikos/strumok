import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.api.push.service import send_reminders
from app.core.domain.billing import kyiv_now
from app.db.engine import engine

logger = logging.getLogger(__name__)


def _run_reminders() -> None:
    with Session(engine) as session:
        try:
            sent, removed = send_reminders(session=session, now=kyiv_now())
            if sent or removed:
                logger.info(
                    "Sent %s push reminders (%s dead subscriptions removed)",
                    sent,
                    removed,
                )
        except Exception:
            logger.exception("Scheduled push reminder send failed")


def start_reminder_scheduler() -> AsyncIOScheduler:
    """Runs in-process: an hourly job that sends the day-1 'opening' and
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
    scheduler.start()
    return scheduler
