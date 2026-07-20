from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class MeterReadingIn(BaseModel):
    period: str = Field(pattern=PERIOD_PATTERN, description="YYYY-MM", examples=["2026-07"])
    day_meter_value: Decimal = Field(
        ge=Decimal("0"), max_digits=7, decimal_places=2, examples=["3205.00"]
    )
    night_meter_value: Decimal = Field(
        ge=Decimal("0"), max_digits=7, decimal_places=2, examples=["1820.00"]
    )


class MeterReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(examples=[1])
    household_id: int = Field(examples=[1])
    submitted_by_user_id: int | None = Field(examples=[1])
    period: str = Field(examples=["2026-07"])
    day_meter_value: Decimal = Field(max_digits=12, decimal_places=2, examples=["3205.00"])
    night_meter_value: Decimal = Field(max_digits=12, decimal_places=2, examples=["1820.00"])
    day_usage_kwh: Decimal = Field(max_digits=12, decimal_places=2, examples=["145.50"])
    night_usage_kwh: Decimal = Field(max_digits=12, decimal_places=2, examples=["98.20"])
    amount_charged_uah: Decimal = Field(max_digits=12, decimal_places=2, examples=["987.65"])
    submitted_at: datetime = Field(examples=["2026-07-20T08:40:50.453Z"])
