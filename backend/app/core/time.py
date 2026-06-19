from datetime import datetime, timezone


def utc_now() -> datetime:
    """Naive UTC datetime for our `TIMESTAMP WITHOUT TIME ZONE` columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
