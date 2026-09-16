from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class ElectricityRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_rate_uah: Decimal
    night_rate_uah: Decimal
    effective_from: str


class ElectricityRateCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_rate_uah: Decimal = Field(gt=0)
    night_rate_uah: Decimal = Field(gt=0)
    effective_from: str = Field(pattern=PERIOD_PATTERN, examples=["2026-07"])
