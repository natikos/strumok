from datetime import datetime
from zoneinfo import ZoneInfo

# Residents are in Kyiv; "the current period" must follow Kyiv local time, not
# server UTC, or a resident near midnight on the 1st sees the wrong month (issue
# #141).
KYIV_TZ = ZoneInfo("Europe/Kyiv")

# Submission window: days 1-5 of the month, Kyiv time. Mirrors DEADLINE_DAY in
# frontend/src/shared/utils/deadline.ts; keep the two in sync.
SUBMISSION_OPEN_DAY = 1
SUBMISSION_DEADLINE_DAY = 5


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
