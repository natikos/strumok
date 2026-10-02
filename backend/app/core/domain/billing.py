from datetime import datetime
from zoneinfo import ZoneInfo

# Residents are in Kyiv; the submission window (day 1-5) and "the current period"
# must follow Kyiv local time, not server UTC, or a resident near midnight around
# the 1st/6th sees the wrong month (issue #141).
KYIV_TZ = ZoneInfo("Europe/Kyiv")
DEADLINE_DAY = 5


def previous_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def kyiv_now() -> datetime:
    return datetime.now(KYIV_TZ)


def current_billing_period(now: datetime | None = None) -> str:
    """The period residents currently submit a reading for (the prior calendar
    month), based on Kyiv local time. Pass `now` (a tz-aware datetime) in tests;
    live callers get the actual current Kyiv time."""
    reference = now if now is not None else kyiv_now()
    return previous_period(reference.astimezone(KYIV_TZ).strftime("%Y-%m"))


def submission_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Kyiv-local (opens_at, closes_at) for the submission window that `now` falls
    in: day 1 00:00:00 through day 5 23:59:59.999999 of `now`'s Kyiv calendar
    month."""
    reference = (now if now is not None else kyiv_now()).astimezone(KYIV_TZ)
    opens_at = datetime(reference.year, reference.month, 1, tzinfo=KYIV_TZ)
    closes_at = datetime(
        reference.year,
        reference.month,
        DEADLINE_DAY,
        23,
        59,
        59,
        999999,
        tzinfo=KYIV_TZ,
    )
    return opens_at, closes_at


def is_submission_window_open(now: datetime | None = None) -> bool:
    reference = now if now is not None else kyiv_now()
    opens_at, closes_at = submission_window(reference)
    return opens_at <= reference.astimezone(KYIV_TZ) <= closes_at
