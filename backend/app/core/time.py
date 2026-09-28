from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def utc_now() -> datetime:
    """Naive UTC datetime for our `TIMESTAMP WITHOUT TIME ZONE` columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
