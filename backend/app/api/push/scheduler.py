import logging
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.api.push.service import send_reminders
from app.db.engine import engine

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Kyiv morning (UTC+2/+3). Several runs per reminder day so a restart, deploy
# or sleeping instance at one of them is covered by the next.
_RUN_HOURS_UTC = (6, 7, 9)


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
    """Runs in-process: fires the 'opening' reminder on day 1 and the 'final'
    one on day 5, at each of _RUN_HOURS_UTC. send_reminders is idempotent per
    (period, variant), so repeated runs and multiple instances never
    double-send."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    for day, variant in ((1, "opening"), (5, "final")):
        for hour in _RUN_HOURS_UTC:
            scheduler.add_job(
                _run_reminders,
                CronTrigger(day=day, hour=hour, minute=0),
                kwargs={"variant": variant},
                id=f"push-reminder-{variant}-{hour:02d}",
            )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_reminder_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
