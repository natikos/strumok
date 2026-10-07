import logging
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.api.push.service import send_reminders
from app.db.engine import engine

logger = logging.getLogger(__name__)


def _run_reminders(variant: Literal["opening", "final"]) -> None:
    with Session(engine) as session:
        try:
            sent, removed = send_reminders(session=session, variant=variant)
            logger.info(
                "Sent %s '%s' push reminders (%s dead subscriptions removed)",
                sent,
                variant,
                removed,
            )
        except Exception:
            logger.exception(
                "Scheduled push reminder send failed (variant=%s)", variant
            )


def start_reminder_scheduler() -> AsyncIOScheduler:
    """Runs in-process: schedules the 'opening' and 'final' deadline
    reminders on a cron trigger."""

    scheduler = AsyncIOScheduler(timezone="UTC")
    for day, variant in ((1, "opening"), (5, "final")):
        scheduler.add_job(
            _run_reminders,
            CronTrigger(day=day, hour=6, minute=0),
            kwargs={"variant": variant},
            id=f"push-reminder-{variant}",
        )
    scheduler.start()
    return scheduler
