"""Builders for test data.

Each factory takes an explicit session and flushes (not commits) so rows get their
primary keys while staying inside the test's rolled-back transaction.
"""

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from itertools import count

from sqlmodel import Session

from app.api.auth.service import create_access_token, pwd_context
from app.core.config import settings
from app.db.models import Household, MeterReading, User

DEFAULT_PASSWORD = "correct-horse-battery-staple"

_email_counter = count(1)


@lru_cache(maxsize=1)
def _default_password_hash() -> str:
    """bcrypt is intentionally slow; hash the shared test password only once."""
    return pwd_context.hash(DEFAULT_PASSWORD)


def make_user(
    session: Session,
    *,
    email: str | None = None,
    password: str | None = None,
    first_name: str = "Test",
    last_name: str = "User",
    is_admin: bool = False,
    is_active: bool = True,
    email_verified: bool = True,
) -> User:
    user = User(
        email=email or f"user{next(_email_counter)}@example.com",
        first_name=first_name,
        last_name=last_name,
        password_hash=(
            pwd_context.hash(password) if password else _default_password_hash()
        ),
        is_admin=is_admin,
        is_active=is_active,
        email_verified=email_verified,
    )
    session.add(user)
    session.flush()
    return user


def make_household(
    session: Session,
    *,
    name: str = "Plot 1",
    user_id: int | None = None,
    is_active: bool = True,
    created_at: datetime | None = None,
) -> Household:
    household = Household(name=name, user_id=user_id, is_active=is_active)
    if created_at is not None:
        # Explicit ordering matters: get_user_household_id picks the oldest
        # household when no id is supplied.
        household.created_at = created_at
    session.add(household)
    session.flush()
    return household


def make_meter_reading(
    session: Session,
    *,
    household_id: int,
    period: str,
    submitted_by_user_id: int | None = None,
    day_meter_value: Decimal | str = Decimal("0"),
    night_meter_value: Decimal | str = Decimal("0"),
    day_usage_kwh: Decimal | str = Decimal("0"),
    night_usage_kwh: Decimal | str = Decimal("0"),
    amount_charged_uah: Decimal | str = Decimal("0"),
) -> MeterReading:
    reading = MeterReading(
        household_id=household_id,
        submitted_by_user_id=submitted_by_user_id,
        period=period,
        day_meter_value=Decimal(day_meter_value),
        night_meter_value=Decimal(night_meter_value),
        day_usage_kwh=Decimal(day_usage_kwh),
        night_usage_kwh=Decimal(night_usage_kwh),
        amount_charged_uah=Decimal(amount_charged_uah),
    )
    session.add(reading)
    session.flush()
    return reading


def authenticate(client, user: User) -> None:
    """Attach a real signed auth cookie for ``user`` to the client's cookie jar.

    Uses the production token factory, so an expiry or claim change breaks tests
    rather than silently diverging from what the app accepts.
    """
    client.cookies.set(settings.auth.auth_cookie_name, create_access_token(user))
