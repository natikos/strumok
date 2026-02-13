from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HouseholdUserRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class ChargeStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class FundEntryType(StrEnum):
    RESERVE_IN = "reserve_in"
    DEBT_COVER_OUT = "debt_cover_out"
    MANUAL_ADJUSTMENT = "manual_adjustment"


class User(SQLModel, table=True):
    """System user account that can belong to one or more households."""

    __tablename__ = "users"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    full_name: str
    password_hash: str
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


class Household(SQLModel, table=True):
    """Cooperative household/plot that reports electricity usage."""

    __tablename__ = "households"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


class HouseholdUser(SQLModel, table=True):
    """Membership link between a user and household with role metadata."""

    __tablename__ = "household_users"  # type: ignore
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    role: HouseholdUserRole = Field(default=HouseholdUserRole.MEMBER)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


class MeterReading(SQLModel, table=True):
    """Monthly meter reading submitted for a household."""

    __tablename__ = "meter_readings"  # type: ignore
    __table_args__ = (
        UniqueConstraint("household_id", "period", name="uq_household_period"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    submitted_by_user_id: int = Field(foreign_key="users.id", index=True)
    period: str = Field(index=True)  # YYYY-MM
    meter_value: Decimal = Field(default=Decimal("0"), decimal_places=2, max_digits=7)
    usage_kwh: Decimal = Field(default=Decimal("0"), decimal_places=2, max_digits=7)
    submitted_at: datetime = Field(default_factory=utcnow)


class BillingCharge(SQLModel, table=True):
    """Monthly household charge including energy and reserve fee."""

    __tablename__ = "billing_charges"  # type: ignore
    __table_args__ = (
        UniqueConstraint("household_id", "period", name="uq_charge_household_period"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    period: str = Field(index=True)  # YYYY-MM
    energy_amount_uah: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=7
    )
    reserve_fee_uah: Decimal = Field(
        default=Decimal("100"), decimal_places=2, max_digits=7
    )
    total_due_uah: Decimal = Field(
        default=Decimal("0"), decimal_places=2, max_digits=7
    )
    status: ChargeStatus = Field(default=ChargeStatus.UNPAID, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


class Payment(SQLModel, table=True):
    """Recorded payment made by a household."""

    __tablename__ = "payments"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(foreign_key="households.id", index=True)
    period: Optional[str] = Field(
        default=None, index=True
    )  # optional allocation to YYYY-MM
    amount_uah: Decimal = Field(decimal_places=2, max_digits=7)
    paid_at: datetime = Field(default_factory=utcnow, index=True)
    note: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})


class CooperativeFundLedger(SQLModel, table=True):
    """Reserve/cooperative fund ledger movement."""

    __tablename__ = "cooperative_fund_ledger_entries"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_type: FundEntryType = Field(index=True)
    amount_uah: Decimal = Field(decimal_places=2, max_digits=7)
    household_id: Optional[int] = Field(
        default=None, foreign_key="households.id", index=True
    )
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow, index=True)


class TariffPeriod(SQLModel, table=True):
    """Electricity tariff value effective from a specific date."""

    __tablename__ = "tariff_periods"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    valid_from: datetime = Field(index=True)
    price_per_kwh: Decimal = Field(decimal_places=2, max_digits=7)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow})
