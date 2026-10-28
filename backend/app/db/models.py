from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    DDL,
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    __table_args__ = (
        CheckConstraint(
            "reminder_hour BETWEEN 0 AND 23", name="ck_users_reminder_hour"
        ),
    )

    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    first_name: str
    last_name: str
    # NULL until an invited user sets a password; such accounts cannot log in.
    password_hash: Optional[str] = None
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    email_verified: bool = Field(default=False)
    # Bumped on logout to invalidate all of the user's outstanding tokens.
    token_version: int = Field(default=0)
    theme: ThemeMode = Field(default=ThemeMode.LIGHT, max_length=16)
    language: LanguageCode = Field(default=LanguageCode.UA, max_length=16)
    # Hour of day (Europe/Kyiv) at which deadline push reminders are sent.
    reminder_hour: int = Field(
        default=9, sa_type=SmallInteger, sa_column_kwargs={"server_default": "9"}
    )
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
        CheckConstraint(
            "review_reason IN ('decrease', 'spike')",
            name="ck_meter_readings_review_reason",
        ),
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
    # Where the values came from. Readings are raw facts; charges live in
    # household_charges once the period closes.
    source: str = Field(
        default="resident", sa_column_kwargs={"server_default": "resident"}
    )
    # Set when the reading looks off (a decrease or a spike). It is accepted
    # either way; the head clears the flag after looking.
    needs_review: bool = Field(
        default=False, sa_column_kwargs={"server_default": "false"}
    )
    review_reason: Optional[str] = Field(default=None)  # 'decrease' | 'spike'
    # Set when the head entered or changed the values; shown to the resident so
    # a correction is never a silent overwrite.
    corrected_at: Optional[datetime] = Field(default=None)
    correction_reason: Optional[str] = Field(default=None)
    reviewed_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    reviewed_at: Optional[datetime] = Field(default=None)


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


class NotificationLog(SQLModel, table=True):
    """One row per (user, period, variant) actually notified. The reminder
    job consults this to skip anyone already sent to, so a repeated or
    overlapping run delivers at most one notification per user."""

    __tablename__ = "notification_log"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period",
            "variant",
            name="uq_notification_log_user_period_variant",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    period: str
    variant: str
    sent_at: datetime = Field(default_factory=utc_now)


class ElectricityRate(SQLModel, table=True):
    """Day/night per-kWh rate effective from a given billing period onward."""

    __tablename__ = "electricity_rates"  # type: ignore

    id: int = Field(default=None, primary_key=True)
    day_rate_uah: Decimal = Field(decimal_places=4, max_digits=12)
    night_rate_uah: Decimal = Field(decimal_places=4, max_digits=12)
    effective_from: str = Field(index=True, unique=True)  # YYYY-MM
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )


class AuthThrottle(SQLModel, table=True):
    """Fixed-window counter of failed auth attempts, keyed by what is throttled
    (e.g. ``login:email:<address>``). Lives in the database, not in memory, so
    the limit holds across app instances."""

    __tablename__ = "auth_throttle"  # type: ignore

    key: str = Field(primary_key=True)
    window_start: datetime = Field(primary_key=True)
    count: int = Field(default=0)


AUDIT_LOG_APPEND_ONLY_SQL = """
CREATE FUNCTION audit_log_reject_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_reject_change();
"""


class AuditLog(SQLModel, table=True):
    """Append-only record of who changed what. Rows are written in the same
    transaction as the change itself (see ``app.core.audit.record``); a
    database trigger rejects UPDATE and DELETE."""

    __tablename__ = "audit_log"  # type: ignore

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    actor_user_id: int | None = Field(default=None, foreign_key="users.id")
    action: str = Field(index=True)
    entity_type: str
    entity_id: int | None = None
    household_id: int | None = Field(
        default=None, foreign_key="households.id", index=True
    )
    period: str | None = Field(default=None, index=True)
    before: dict | None = Field(default=None, sa_column=Column(JSONB))
    after: dict | None = Field(default=None, sa_column=Column(JSONB))
    reason: str | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )


# create_all (used by the test suite) builds the trigger too; Alembic's 0002
# migration runs the same SQL, so both paths enforce append-only.
event.listen(AuditLog.__table__, "after_create", DDL(AUDIT_LOG_APPEND_ONLY_SQL))  # type: ignore[attr-defined]


class BillingPeriod(SQLModel, table=True):
    """One row per billing period, created lazily. `closed` is final: charges
    exist and corrections happen as adjustments, never by reopening."""

    __tablename__ = "billing_periods"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'closed')", name="ck_billing_periods_status"
        ),
    )

    period: str = Field(sa_column=Column(String(7), primary_key=True))
    status: str = Field(default="open", sa_column_kwargs={"server_default": "open"})
    bill_day_kwh: Optional[Decimal] = Field(
        default=None, decimal_places=2, max_digits=12
    )
    bill_night_kwh: Optional[Decimal] = Field(
        default=None, decimal_places=2, max_digits=12
    )
    bill_total_uah: Optional[Decimal] = Field(
        default=None, decimal_places=2, max_digits=12
    )
    rate_id: Optional[int] = Field(default=None, foreign_key="electricity_rates.id")
    closed_at: Optional[datetime] = None
    closed_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")


HOUSEHOLD_CHARGES_APPEND_ONLY_SQL = """
CREATE FUNCTION household_charges_reject_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'household_charges is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER household_charges_append_only
BEFORE UPDATE OR DELETE ON household_charges
FOR EACH ROW EXECUTE FUNCTION household_charges_reject_change();
"""


class HouseholdCharge(SQLModel, table=True):
    """What one household owes for one closed period. Inserted at close and
    never updated; a trigger enforces it."""

    __tablename__ = "household_charges"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "period", "household_id", name="uq_household_charges_period_household"
        ),
    )

    id: int = Field(default=None, primary_key=True)
    period: str = Field(
        sa_column=Column(
            String(7), ForeignKey("billing_periods.period"), nullable=False, index=True
        )
    )
    household_id: int = Field(foreign_key="households.id", index=True)
    owner_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    reading_id: Optional[int] = Field(default=None, foreign_key="meter_readings.id")
    day_usage_kwh: Decimal = Field(decimal_places=2, max_digits=12)
    night_usage_kwh: Decimal = Field(decimal_places=2, max_digits=12)
    is_estimated: bool = Field(default=False)
    tariff_uah: Decimal = Field(decimal_places=2, max_digits=12)
    loss_share_uah: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    penalty_uah: Decimal = Field(default=Decimal("0"), decimal_places=2, max_digits=12)
    penalty_credit_uah: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=12
    )
    total_uah: Decimal = Field(decimal_places=2, max_digits=12)


event.listen(
    HouseholdCharge.__table__,  # type: ignore[attr-defined]
    "after_create",
    DDL(HOUSEHOLD_CHARGES_APPEND_ONLY_SQL),
)


class PeriodRestatement(SQLModel, table=True):
    """One correction of a closed period (wrong rate, reading or bill). The
    closed charges are never touched; the per-household differences are posted
    as ChargeAdjustment rows into the current open period."""

    __tablename__ = "period_restatements"  # type: ignore

    id: int = Field(default=None, primary_key=True)
    period: str = Field(
        sa_column=Column(
            String(7), ForeignKey("billing_periods.period"), nullable=False, index=True
        )
    )
    reason: str
    inputs: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )


CHARGE_ADJUSTMENTS_APPEND_ONLY_SQL = """
CREATE FUNCTION charge_adjustments_reject_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'charge_adjustments is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER charge_adjustments_append_only
BEFORE UPDATE OR DELETE ON charge_adjustments
FOR EACH ROW EXECUTE FUNCTION charge_adjustments_reject_change();
"""


class ChargeAdjustment(SQLModel, table=True):
    """A signed correction to what a household owes for `applies_to_period`,
    shown on the bill of `posted_in_period`. Positive is an extra charge,
    negative a refund."""

    __tablename__ = "charge_adjustments"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "reason_code IN ('rateCorrection', 'readingCorrection', 'billCorrection', 'manual')",
            name="ck_charge_adjustments_reason_code",
        ),
    )

    id: int = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    owner_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    applies_to_period: str = Field(
        sa_column=Column(
            String(7), ForeignKey("billing_periods.period"), nullable=False, index=True
        )
    )
    posted_in_period: str = Field(
        sa_column=Column(
            String(7), ForeignKey("billing_periods.period"), nullable=False, index=True
        )
    )
    amount_uah: Decimal = Field(decimal_places=2, max_digits=12)
    reason_code: str
    reason: str
    restatement_id: int = Field(foreign_key="period_restatements.id", index=True)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )


event.listen(
    ChargeAdjustment.__table__,  # type: ignore[attr-defined]
    "after_create",
    DDL(CHARGE_ADJUSTMENTS_APPEND_ONLY_SQL),
)


class Payment(SQLModel, table=True):
    """Money a household handed over. Never deleted, only voided, so the balance
    can always be explained from the rows."""

    __tablename__ = "payments"  # type: ignore
    __table_args__ = (
        CheckConstraint("amount_uah > 0", name="ck_payments_amount_positive"),
        CheckConstraint("method IN ('cash', 'transfer')", name="ck_payments_method"),
    )

    id: int = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    owner_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    amount_uah: Decimal = Field(decimal_places=2, max_digits=12)
    paid_on: date
    method: str
    note: Optional[str] = Field(default=None)
    recorded_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )
    voided_at: Optional[datetime] = Field(default=None)
    voided_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    void_reason: Optional[str] = Field(default=None)
