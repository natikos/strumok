from datetime import datetime
from zoneinfo import ZoneInfo

# Residents are in Kyiv; "the current period" must follow Kyiv local time, not
# server UTC, or a resident near midnight on the 1st sees the wrong month (issue
# #141). The day 1-5 submission window itself is computed only in the frontend.
KYIV_TZ = ZoneInfo("Europe/Kyiv")


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
