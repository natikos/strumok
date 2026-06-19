from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class MeterReadingIn(BaseModel):
    period: str = Field(pattern=PERIOD_PATTERN, description="YYYY-MM")
    day_meter_value: Decimal = Field(ge=Decimal("0"), max_digits=7, decimal_places=2)
    night_meter_value: Decimal = Field(ge=Decimal("0"), max_digits=7, decimal_places=2)


class MeterReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    submitted_by_user_id: int | None
    period: str
    day_meter_value: Decimal
    night_meter_value: Decimal
    day_usage_kwh: Decimal
    night_usage_kwh: Decimal
    amount_charged_uah: Decimal
    submitted_at: datetime
