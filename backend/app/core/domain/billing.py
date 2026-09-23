from app.core.time import utc_now


def previous_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def current_billing_period() -> str:
    """The period residents currently submit a reading for (the prior calendar month)."""
    return previous_period(utc_now().strftime("%Y-%m"))
