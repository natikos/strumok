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
