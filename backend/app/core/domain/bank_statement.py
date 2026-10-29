"""Parse the accountant's bank statement CSV into incoming credits.

Pure: bytes in, rows out, no database. Debits (negative amounts) are the
co-op's own outgoing payments and are dropped here, so they are never stored.
Errors name the row and column only, never the cell value, because cells hold
residents' names and account numbers.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.domain.billing import kyiv_now

COL_ACCOUNT = "Рахунок"
COL_CURRENCY = "Валюта"
COL_DOCUMENT = "Номер документу"
COL_DATE = "Дата операції"
COL_PAYER_IBAN = "Рахунок кореспондента"
COL_PAYER_NAME = "Кореспондент"
COL_AMOUNT = "Сума"
COL_PURPOSE = "Призначення платежу"

REQUIRED_COLUMNS = (
    COL_ACCOUNT,
    COL_CURRENCY,
    COL_DOCUMENT,
    COL_DATE,
    COL_PAYER_IBAN,
    COL_PAYER_NAME,
    COL_AMOUNT,
    COL_PURPOSE,
)

MAX_ROWS = 5000
MAX_AMOUNT = Decimal(10) ** 10

_AMOUNT_RE = re.compile(r"^-?\d+\.\d{2}$")
_SPACES = (" ", " ", " ")


class BankStatementError(Exception):
    """A statement that cannot be imported. `code` is a stable camelCase code."""

    def __init__(
        self, code: str, row: int | None = None, column: str | None = None
    ) -> None:
        super().__init__(code)
        self.code = code
        self.row = row
        self.column = column


@dataclass(frozen=True)
class ParsedCredit:
    document_number: str
    operation_date: date
    amount_uah: Decimal
    payer_iban: str
    payer_name: str
    purpose: str


@dataclass(frozen=True)
class ParsedStatement:
    encoding: str
    account_iban: str
    credits: list[ParsedCredit]
    debits_skipped: int
    rows_total: int
    first_operation_date: date
    last_operation_date: date


def _decode(data: bytes) -> tuple[str, str]:
    # Strict UTF-8 first: cp1251 maps almost every byte, so it must come second.
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1251", errors="strict"), "cp1251"


def _parse_amount(raw: str, row: int) -> Decimal:
    text = raw.strip()
    for space in _SPACES:
        text = text.replace(space, "")
    if not _AMOUNT_RE.match(text):
        raise BankStatementError("bankStatementInvalid", row, COL_AMOUNT)
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise BankStatementError("bankStatementInvalid", row, COL_AMOUNT) from None
    # amount_uah is Numeric(12, 2); anything larger would fail at insert.
    if abs(amount) >= MAX_AMOUNT:
        raise BankStatementError("bankStatementInvalid", row, COL_AMOUNT)
    return amount


def _parse_date(raw: str, row: int) -> date:
    try:
        parsed = datetime.strptime(raw.strip(), "%d.%m.%Y").date()
    except ValueError:
        raise BankStatementError("bankStatementInvalid", row, COL_DATE) from None
    if parsed > kyiv_now().date():
        raise BankStatementError("bankStatementInvalid", row, COL_DATE)
    return parsed


def parse_statement(data: bytes, expected_iban: str | None = None) -> ParsedStatement:
    """Parse a statement. Raises `BankStatementError` on the first bad row.

    `expected_iban`, when given, must equal every row's own account, so a
    statement for another account is refused before anything is stored.
    """
    try:
        text, encoding = _decode(data)
    except UnicodeDecodeError:
        raise BankStatementError("bankStatementInvalid") from None

    reader = csv.reader(io.StringIO(text), delimiter=";")
    try:
        header = next(reader)
    except StopIteration:
        raise BankStatementError("bankStatementInvalid") from None

    index = {name.strip(): i for i, name in enumerate(header)}
    for column in REQUIRED_COLUMNS:
        if column not in index:
            raise BankStatementError("bankStatementInvalid", None, column)

    def cell(record: list[str], column: str) -> str:
        i = index[column]
        return record[i].strip() if i < len(record) else ""

    credits: list[ParsedCredit] = []
    debits_skipped = 0
    rows_total = 0
    accounts: set[str] = set()
    dates: list[date] = []

    # Row numbers are 1-based file lines, so the head can find them in the CSV.
    for row, record in enumerate(reader, start=2):
        if not any(c.strip() for c in record):
            continue
        rows_total += 1
        if rows_total > MAX_ROWS:
            raise BankStatementError("bankStatementTooManyRows")

        if cell(record, COL_CURRENCY) != "UAH":
            raise BankStatementError("bankStatementInvalid", row, COL_CURRENCY)
        account = cell(record, COL_ACCOUNT)
        if not account:
            raise BankStatementError("bankStatementInvalid", row, COL_ACCOUNT)
        if expected_iban is not None and account != expected_iban:
            raise BankStatementError("bankStatementWrongAccount", row, COL_ACCOUNT)
        accounts.add(account)

        operation_date = _parse_date(cell(record, COL_DATE), row)
        dates.append(operation_date)
        amount = _parse_amount(cell(record, COL_AMOUNT), row)
        if amount < 0:
            debits_skipped += 1
            continue
        if amount == 0:
            raise BankStatementError("bankStatementInvalid", row, COL_AMOUNT)

        document_number = cell(record, COL_DOCUMENT)
        if not document_number:
            raise BankStatementError("bankStatementInvalid", row, COL_DOCUMENT)
        credits.append(
            ParsedCredit(
                document_number=document_number,
                operation_date=operation_date,
                amount_uah=amount,
                payer_iban=cell(record, COL_PAYER_IBAN),
                payer_name=cell(record, COL_PAYER_NAME),
                purpose=cell(record, COL_PURPOSE),
            )
        )

    if not dates:
        raise BankStatementError("bankStatementInvalid")
    if len(accounts) != 1:
        raise BankStatementError("bankStatementInvalid", None, COL_ACCOUNT)

    return ParsedStatement(
        encoding=encoding,
        account_iban=next(iter(accounts)),
        credits=credits,
        debits_skipped=debits_skipped,
        rows_total=rows_total,
        first_operation_date=min(dates),
        last_operation_date=max(dates),
    )
