from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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
    # Optional opening meter values. They are stored as an unbilled baseline for
    # the period before the first one residents submit, so the first month is
    # measured instead of reading 0.
    starting_day_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    starting_night_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )

    @model_validator(mode="after")
    def _both_or_neither(self) -> "AdminHouseholdCreateIn":
        if (self.starting_day_meter_value is None) != (
            self.starting_night_meter_value is None
        ):
            raise ValueError("Provide both starting meter values or neither")
        return self


class HouseholdOwnerAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int | None
    confirm_reassignment: bool = False
    # Handing a plot from one owner to another needs the meter values at the
    # handover; an outgoing owner who still owes money must be acknowledged.
    handover_day_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    handover_night_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    acknowledge_balance: bool = False

    @model_validator(mode="after")
    def _handover_pair(self) -> "HouseholdOwnerAssignIn":
        if (self.handover_day_meter_value is None) != (
            self.handover_night_meter_value is None
        ):
            raise ValueError("Provide both handover meter values or neither")
        return self


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


class AdminReadingOut(BaseModel):
    id: int
    day_meter_value: Decimal
    night_meter_value: Decimal
    previous_day_meter_value: Decimal | None
    previous_night_meter_value: Decimal | None
    needs_review: bool
    review_reason: Literal["decrease", "spike"] | None


class ReadingReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]


class AdminDashboardHouseholdOut(BaseModel):
    id: int
    name: str
    owner: AdminUserSummaryOut | None = None
    submission_status: Literal["submitted", "estimated", "missing"]
    submitted_at: UtcDatetime | None = None
    reading: AdminReadingOut | None = None
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
    unreviewed_count: int = 0
    blockers: list[str]


class PeriodCloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    acknowledge_flags: bool = False


class BillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_kwh: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    night_kwh: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    total_uah: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    confirm: Literal[True]


class ReconciliationLineOut(BaseModel):
    household_id: int
    household_name: str
    usage_kwh: Decimal
    usage_share_percent: Decimal
    tariff_uah: Decimal
    loss_share_uah: Decimal
    penalty_uah: Decimal
    total_uah: Decimal
    is_estimated: bool


class ReconciliationOut(BaseModel):
    period: str
    status: Literal["open", "closed"]
    closed_at: UtcDatetime | None
    bill_day_kwh: Decimal | None
    bill_night_kwh: Decimal | None
    bill_total_uah: Decimal | None
    total_usage_kwh: Decimal
    total_tariff_uah: Decimal
    loss_uah: Decimal | None
    loss_percent: Decimal | None
    kwh_loss: Decimal | None
    kwh_loss_percent: Decimal | None
    shares_total_uah: Decimal
    variance_uah: Decimal | None
    lines: list[ReconciliationLineOut]
    remainder_household_names: list[str]


class RateCorrectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_rate_uah: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    night_rate_uah: Decimal = Field(gt=0, max_digits=12, decimal_places=4)


class ReadingCorrectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: int
    # Defaults to the period being restated; the following period is derived.
    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    day_meter_value: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    night_meter_value: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CorrectionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate: RateCorrectionIn | None = None
    bill_total_uah: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    readings: list[ReadingCorrectionIn] = []


class RestateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrections: CorrectionsIn
    reason: str | None = Field(default=None, max_length=500)
    dry_run: bool = False
    confirm: Literal[True]

    @model_validator(mode="after")
    def _reason_required_to_post(self) -> "RestateIn":
        if not self.dry_run and not (self.reason or "").strip():
            raise ValueError("A reason is required to post a restatement")
        return self


class RestatementLineOut(BaseModel):
    period: str
    household_id: int
    household_name: str
    before_uah: Decimal
    after_uah: Decimal
    delta_uah: Decimal


class RestatementOut(BaseModel):
    lines: list[RestatementLineOut]
    affected_periods: list[str]
    total_delta_uah: Decimal
    restatement_id: int | None
    posted_in_period: str
    # True when the households' changes cancel out, which is what a pure rate
    # correction does under the loss-split formula.
    is_zero_sum: bool

    @classmethod
    def from_result(cls, result: Any) -> "RestatementOut":
        """Builds the response from a billing RestatementResult."""
        return cls(
            lines=[
                RestatementLineOut.model_validate(line, from_attributes=True)
                for line in result.lines
            ],
            affected_periods=result.affected_periods,
            total_delta_uah=result.total_delta_uah,
            restatement_id=result.restatement_id,
            posted_in_period=result.posted_in_period,
            is_zero_sum=result.total_delta_uah == 0,
        )


class AdminReadingCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-07"])
    day_meter_value: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    night_meter_value: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)
    # 'baseline' sets the household's starting cumulative values; it is never
    # billed and only allowed before any other reading exists.
    kind: Literal["reading", "baseline"] = "reading"

    @model_validator(mode="after")
    def _reason_not_blank(self) -> "AdminReadingCreateIn":
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class AdminReadingUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    night_meter_value: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _reason_not_blank(self) -> "AdminReadingUpdateIn":
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class AdminReadingVoidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _reason_not_blank(self) -> "AdminReadingVoidIn":
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class AdminReadingResultOut(BaseModel):
    id: int
    household_id: int
    period: str
    day_meter_value: Decimal
    night_meter_value: Decimal
    source: str
    corrected_at: UtcDatetime | None
    correction_reason: str | None


class PaymentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_uah: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    paid_on: date
    method: Literal["cash", "transfer"]
    note: str | None = Field(default=None, max_length=500)


class PaymentVoidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _reason_not_blank(self) -> "PaymentVoidIn":
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: int
    amount_uah: Decimal
    paid_on: date
    method: Literal["cash", "transfer"]
    note: str | None
    created_at: UtcDatetime
    voided_at: UtcDatetime | None
    void_reason: str | None


class OpeningBalanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Positive: the household owes the co-op. Negative: the co-op owes it.
    amount_uah: Decimal = Field(max_digits=12, decimal_places=2)
    as_of: date
    note: str | None = Field(default=None, max_length=500)


class OpeningBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    household_id: int
    amount_uah: Decimal
    as_of: date
    note: str | None
    created_at: UtcDatetime


class HouseholdBalanceOut(BaseModel):
    household_id: int
    household_name: str
    owner_name: str | None
    balance_uah: Decimal
    unpaid_months: int


class BalancesOut(BaseModel):
    households: list[HouseholdBalanceOut]
    total_outstanding_uah: Decimal


class MeterChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-07"])
    old_final_day: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    old_final_night: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    new_start_day: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    new_start_night: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _reason_not_blank(self) -> "MeterChangeIn":
        if not self.reason.strip():
            raise ValueError("A reason is required")
        return self


class MeterChangeOut(BaseModel):
    id: int
    household_id: int
    period: str
    # Usage the household's reading for the period now derives to; None while
    # that reading hasn't been submitted.
    day_usage_kwh: Decimal | None
    night_usage_kwh: Decimal | None
