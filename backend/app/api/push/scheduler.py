import logging
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.api.push.service import send_reminders
from app.db.engine import engine

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


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
            # There's no external workflow run history to check anymore, so a
            # failed scheduled send must show up in the app's own logs.
            logger.exception(
                "Scheduled push reminder send failed (variant=%s)", variant
            )


def start_reminder_scheduler() -> AsyncIOScheduler:
    """Runs in-process: the reminder window is days 1-5, so this fires the
    'opening' reminder on day 1 and the 'final' one on day 5, both 08:00 UTC."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_reminders,
        CronTrigger(day=1, hour=8, minute=0),
        kwargs={"variant": "opening"},
        id="push-reminder-opening",
    )
    scheduler.add_job(
        _run_reminders,
        CronTrigger(day=5, hour=8, minute=0),
        kwargs={"variant": "final"},
        id="push-reminder-final",
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
