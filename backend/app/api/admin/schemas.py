from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Household, User


class AdminUserSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool


class AdminHouseholdCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    user_id: int


class HouseholdOwnerAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int | None
    confirm_reassignment: bool = False


class AdminHouseholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int | None
    is_active: bool
    owner: AdminUserSummaryOut | None = None

    @classmethod
    def from_household(
        cls, household: Household, *, owner: User | None = None
    ) -> "AdminHouseholdOut":
        return cls.model_validate(
            {
                **household.model_dump(),
                "owner": AdminUserSummaryOut.model_validate(owner) if owner else None,
            }
        )


class AdminDashboardHouseholdOut(BaseModel):
    id: int
    name: str
    owner: AdminUserSummaryOut | None = None
    submission_status: Literal["submitted", "missing"]
    submitted_at: datetime | None = None
    latest_period: str | None = None
    latest_usage_kwh: Decimal | None = Field(default=None, decimal_places=2)
    latest_amount_charged_uah: Decimal | None = Field(default=None, decimal_places=2)


class AdminDashboardOut(BaseModel):
    current_period: str
    households: list[AdminDashboardHouseholdOut]
