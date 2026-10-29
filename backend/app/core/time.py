from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

# How far the app clock runs ahead of the real one. Always zero outside e2e:
# only the e2e router (mounted when ENVIRONMENT=e2e) calls set_clock_offset.
_offset = timedelta(0)


def set_clock_offset(offset: timedelta) -> None:
    global _offset
    _offset = offset


def now_utc_aware() -> datetime:
    """The app's current instant, tz-aware UTC. Every clock read goes through
    here or `utc_now`, so the e2e offset reaches all of them."""
    return datetime.now(timezone.utc) + _offset


def utc_now() -> datetime:
    """Naive UTC datetime for our `TIMESTAMP WITHOUT TIME ZONE` columns."""
    return now_utc_aware().replace(tzinfo=None)


def to_utc_iso(value: datetime) -> str:
    """ISO 8601 in UTC with a `Z` suffix; naive values are taken to already be UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Use for every datetime in an API response schema. Without an offset, browsers
# parse the value as local time and shift it by the client's UTC offset.
UtcDatetime = Annotated[
    datetime,
    PlainSerializer(to_utc_iso, return_type=str, when_used="json"),
]
