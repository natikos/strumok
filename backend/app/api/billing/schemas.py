from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
