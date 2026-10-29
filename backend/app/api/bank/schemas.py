from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StatementImportOut(BaseModel):
    already_imported: bool
    credits_new: int
    credits_duplicate: int
    debits_skipped: int
    covered_through: date


class BankStatementErrorOut(BaseModel):
    detail: str
    row: int | None = None
    column: str | None = None


class LinkCandidateOut(BaseModel):
    payment_id: int
    household_id: int
    paid_on: date


class SuggestionOut(BaseModel):
    household_id: int
    source: str


class BankTransactionOut(BaseModel):
    id: int
    operation_date: date
    amount_uah: Decimal
    payer_name: str
    purpose: str
    suggested_household_id: int | None
    suggestion_source: str | None
    suggestions: list[SuggestionOut]
    link_candidates: list[LinkCandidateOut]


class SplitLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: int
    amount_uah: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[SplitLineIn] = Field(min_length=1, max_length=50)


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_id: int


class ConfirmedPaymentOut(BaseModel):
    payment_id: int
    household_id: int
    amount_uah: Decimal


class InboxCheckOut(BaseModel):
    received: int
    imported: int
    rejected: int
    credits_new: int
