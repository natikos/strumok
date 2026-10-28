from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.time import UtcDatetime

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class RateChangeOut(BaseModel):
    action: str
    actor_name: str | None
    created_at: UtcDatetime
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None


class ElectricityRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_rate_uah: Decimal
    night_rate_uah: Decimal
    effective_from: str
    # Closed periods this rate billed; non-empty means it can no longer be
    # edited or deleted, only corrected through a restatement.
    used_by_closed_periods: list[str] = []
    history: list[RateChangeOut] = []


class ElectricityRateUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_rate_uah: Decimal | None = Field(default=None, gt=0)
    night_rate_uah: Decimal | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)
    confirm: Literal[True]


class ElectricityRateCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_rate_uah: Decimal = Field(gt=0)
    night_rate_uah: Decimal = Field(gt=0)
    effective_from: str = Field(pattern=PERIOD_PATTERN, examples=["2026-07"])


class RateCorrectIn(BaseModel):
    """Correct a rate that already billed closed periods, via a restatement."""

    model_config = ConfigDict(extra="forbid")

    day_rate_uah: Decimal = Field(gt=0)
    night_rate_uah: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)
    dry_run: bool = False
    confirm: Literal[True]

    @model_validator(mode="after")
    def _reason_required_to_post(self) -> "RateCorrectIn":
        if not self.dry_run and not (self.reason or "").strip():
            raise ValueError("A reason is required to post a correction")
        return self
