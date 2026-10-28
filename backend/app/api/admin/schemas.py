from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.time import UtcDatetime
from app.db.models import Household, LanguageCode, User


class AdminUserSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool


class AdminUserOut(AdminUserSummaryOut):
    is_admin: bool
    household_count: int
    invite_pending: bool = False


class AdminInviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    first_name: str = Field(min_length=2, max_length=255)
    last_name: str = Field(min_length=2, max_length=255)
    language: LanguageCode = LanguageCode.UA
    household_id: int | None = None


class AdminInviteOut(BaseModel):
    user: AdminUserOut
    invite_link: str
    email_sent: bool


class AdminUserUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    is_admin: bool | None = None
    unassign_households: bool = False
    confirm: Literal[True]


class AdminHouseholdCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    user_id: int


class HouseholdOwnerAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int | None
    confirm_reassignment: bool = False


class AdminHouseholdUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    confirm: Literal[True]


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
    submitted_at: UtcDatetime | None = None
    latest_period: str | None = None
    latest_usage_kwh: Decimal | None = Field(default=None, decimal_places=2)
    latest_amount_charged_uah: Decimal | None = Field(default=None, decimal_places=2)


class AdminDashboardOut(BaseModel):
    current_period: str
    households: list[AdminDashboardHouseholdOut]


class AuditLogEntryOut(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int | None
    household_id: int | None
    period: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    created_at: UtcDatetime
    actor: AdminUserSummaryOut | None


class AuditLogPageOut(BaseModel):
    items: list[AuditLogEntryOut]
    next_cursor: int | None


class PeriodOverviewOut(BaseModel):
    period: str
    status: Literal["open", "closed"]
    closed_at: UtcDatetime | None
    closed_by_name: str | None
    readings_count: int
    missing_count: int
    blockers: list[str]


class PeriodCloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    acknowledge_flags: bool = False
