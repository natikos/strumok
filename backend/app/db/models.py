from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import UniqueConstraint, text
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
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
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


class PushSubscription(SQLModel, table=True):
    """A browser's Web Push (VAPID) subscription for a user's device."""

    __tablename__ = "push_subscriptions"  # type: ignore
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),
    )

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    endpoint: str
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=utc_now)


class ReminderDispatch(SQLModel, table=True):
    """One row per (period, variant) reminder run, so a reminder trigger that
    fires more than once for the same period/variant (e.g. an external cron
    retrying, or two overlapping runs) is visible and idempotent -- see
    NotificationLog for the per-user dedup this coordinates with."""

    __tablename__ = "reminder_dispatches"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "period", "variant", name="uq_reminder_dispatch_period_variant"
        ),
    )

    id: int = Field(default=None, primary_key=True)
    period: str
    variant: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = Field(default=None)
    # Distinct residents newly notified / dead subscriptions removed,
    # accumulated across every call for this (period, variant).
    sent: int = Field(default=0)
    removed: int = Field(default=0)


class NotificationLog(SQLModel, table=True):
    """One row per (user, period, variant, channel) actually notified.
    A repeated reminder trigger consults this to skip anyone already sent
    to, so calling the trigger endpoint more than once for the same period
    and variant delivers at most one notification per user per channel."""

    __tablename__ = "notification_log"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period",
            "variant",
            "channel",
            name="uq_notification_log_user_period_variant_channel",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    period: str
    variant: str
    channel: str = Field(default="push")
    status: str = Field(default="sent")
    sent_at: datetime = Field(default_factory=utc_now)


class ElectricityRate(SQLModel, table=True):
    """Day/night per-kWh rate effective from a given billing period onward."""

    __tablename__ = "electricity_rates"  # type: ignore

    id: int = Field(default=None, primary_key=True)
    day_rate_uah: Decimal = Field(decimal_places=4, max_digits=12)
    night_rate_uah: Decimal = Field(decimal_places=4, max_digits=12)
    effective_from: str = Field(index=True)  # YYYY-MM
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )
