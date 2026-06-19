from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.time import utc_now


class ThemeMode(StrEnum):
    LIGHT = "light"
    DARK = "dark"


class LanguageCode(StrEnum):
    EN = "en"
    UA = "ua"


class User(SQLModel, table=True):
    """System user account that can belong to one or more households."""

    __tablename__ = "users"  # type: ignore

    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    first_name: str
    last_name: str
    password_hash: str
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    email_verified: bool = Field(default=False)
    theme: ThemeMode = Field(default=ThemeMode.LIGHT, max_length=16)
    language: LanguageCode = Field(default=LanguageCode.UA, max_length=16)
    verification_email_last_sent_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now}
    )


class Household(SQLModel, table=True):
    """Cooperative household/plot that reports electricity usage."""

    __tablename__ = "households"  # type: ignore

    id: int = Field(default=None, primary_key=True)
    name: str
    user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", index=True
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(
        default_factory=utc_now, sa_column_kwargs={"onupdate": utc_now}
    )


class MeterReading(SQLModel, table=True):
    """Monthly meter reading submitted for a household."""

    __tablename__ = "meter_readings"  # type: ignore
    __table_args__ = (
        UniqueConstraint("household_id", "period", name="uq_household_period"),
    )

    id: int = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    submitted_by_user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", index=True
    )
    period: str = Field(index=True)  # YYYY-MM
    day_meter_value: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    night_meter_value: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    day_usage_kwh: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    night_usage_kwh: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    amount_charged_uah: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    submitted_at: datetime = Field(default_factory=utc_now)
