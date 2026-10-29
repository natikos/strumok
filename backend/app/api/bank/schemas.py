from datetime import date

from pydantic import BaseModel


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
