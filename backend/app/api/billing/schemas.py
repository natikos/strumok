from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import UtcDatetime


class StatementLineOut(BaseModel):
    """One household's charge for one period. `provisional` lines are computed
    at read time for the open period and never stored."""

    model_config = ConfigDict(from_attributes=True)

    period: str = Field(examples=["2026-07"])
    status: Literal["closed", "provisional"]
    day_usage_kwh: Decimal = Field(max_digits=12, decimal_places=2)
    night_usage_kwh: Decimal = Field(max_digits=12, decimal_places=2)
    is_estimated: bool
    tariff_uah: Decimal = Field(max_digits=12, decimal_places=2)
    loss_share_uah: Decimal = Field(max_digits=12, decimal_places=2)
    penalty_uah: Decimal = Field(max_digits=12, decimal_places=2)
    penalty_credit_uah: Decimal = Field(max_digits=12, decimal_places=2)
    total_uah: Decimal = Field(max_digits=12, decimal_places=2)


class AdjustmentOut(BaseModel):
    """A correction posted to a household's bill: positive is an extra charge,
    negative a refund."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    applies_to_period: str
    posted_in_period: str
    amount_uah: Decimal = Field(max_digits=12, decimal_places=2)
    reason_code: str
    reason: str


class CurrentPeriodOut(BaseModel):
    """Where the period residents are submitting for stands: `closed` once the
    head has closed it, after which submissions get periodClosed."""

    period: str = Field(examples=["2026-07"])
    status: Literal["open", "closed"]


class PeriodBalanceOut(BaseModel):
    period: str
    due_uah: Decimal
    paid_uah: Decimal
    status: Literal["paid", "partial", "unpaid"]


class BalanceOut(BaseModel):
    """What a household owes in total. Negative `balance_uah` is a credit."""

    household_id: int
    total_due_uah: Decimal
    total_paid_uah: Decimal
    balance_uah: Decimal
    unpaid_months: int
    periods: list[PeriodBalanceOut]


class HouseholdStatementsOut(BaseModel):
    """One household's bills as the current user was billed for them, including
    plots they no longer own."""

    household_id: int
    household_name: str
    is_current_owner: bool
    owned_since: UtcDatetime | None
    owned_until: UtcDatetime | None
    # Someone else owned the plot before this user's tenure began, so records
    # older than `owned_since` belong to them.
    has_previous_owner: bool
    balance: BalanceOut
    statements: list[StatementLineOut]


class PaymentDetailsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    iban: str = Field(examples=["UA213223130000026007233566001"])
    recipient_name: str


class BankCoverageOut(BaseModel):
    """How far imported bank statements reach. `awaiting_statement` is true
    when none was imported or the newest is stale; `last_imported_at` is only
    filled for admins."""

    covered_through: date | None
    awaiting_statement: bool
    last_imported_at: UtcDatetime | None = None


class ShortfallOut(BaseModel):
    """`active` once the statement has covered the due date, nothing dated
    before it is awaiting review, and the household still owes."""

    active: bool
    due_date: date | None = None
    owed_uah: Decimal = Decimal("0.00")


class PaymentDetailsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iban: str = Field(max_length=40)
    recipient_name: str = Field(min_length=1, max_length=120)
