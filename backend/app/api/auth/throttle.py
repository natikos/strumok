from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session

from app.core.time import utc_now

PRUNE_AFTER = timedelta(days=1)


@dataclass(frozen=True)
class Limit:
    max_attempts: int
    window: timedelta


LOGIN_EMAIL_LIMIT = Limit(max_attempts=5, window=timedelta(minutes=15))
LOGIN_IP_LIMIT = Limit(max_attempts=30, window=timedelta(minutes=15))


class TooManyAttemptsError(Exception):
    def __init__(self, *, retry_after_seconds: int):
        super().__init__("tooManyAttempts")
        self.retry_after_seconds = retry_after_seconds


def _window_start(now: datetime, window: timedelta) -> datetime:
    epoch = datetime(1970, 1, 1)
    return epoch + ((now - epoch) // window) * window


def check_not_throttled(
    *, session: Session, key: str, limit: Limit, now: datetime | None = None
) -> None:
    """Raises TooManyAttemptsError once `key` has used up its failures for the
    current window. Throttles only; the account is never locked."""
    now = now or utc_now()
    window_start = _window_start(now, limit.window)
    count = session.execute(
        text(
            "SELECT count FROM auth_throttle "
            "WHERE key = :key AND window_start = :window_start"
        ),
        {"key": key, "window_start": window_start},
    ).scalar()

    if count is not None and count >= limit.max_attempts:
        retry_after = (window_start + limit.window - now).total_seconds()
        raise TooManyAttemptsError(retry_after_seconds=max(1, int(retry_after) + 1))


def record_failure(
    *, session: Session, key: str, limit: Limit, now: datetime | None = None
) -> None:
    """Atomically counts one failure and commits right away, so the count
    survives the request failing."""
    now = now or utc_now()
    session.execute(
        text(
            "INSERT INTO auth_throttle (key, window_start, count) "
            "VALUES (:key, :window_start, 1) "
            "ON CONFLICT (key, window_start) "
            "DO UPDATE SET count = auth_throttle.count + 1"
        ),
        {"key": key, "window_start": _window_start(now, limit.window)},
    )
    session.execute(
        text("DELETE FROM auth_throttle WHERE window_start < :cutoff"),
        {"cutoff": now - PRUNE_AFTER},
    )
    session.commit()
