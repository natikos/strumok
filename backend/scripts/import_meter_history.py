"""Import a CSV of historical meter readings into the database.

Usage:
    cd backend
    uv run python scripts/import_meter_history.py <csv_path> --mapping <mapping.csv> [--apply]

Without --apply this is a dry run: it prints the match report and would-be
writes, and changes nothing.

The mapping file is the only way a CSV row is matched to a household: a CSV
with a header row `csv_id,household_id`, where `csv_id` is the source
spreadsheet's own first-column number (not a database id) and `household_id`
is the real `Household.id`. Rows with no mapping entry are reported and
skipped. There is deliberately no name matching: two households sharing a
surname must never be silently merged.

Numeric cells parse as `Decimal` (comma separator accepted). If any cell is
malformed the script aborts before writing anything and lists every bad row
and column.
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.db.engine import engine
from app.db.models import Household, MeterReading
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select


class ImportValidationError(Exception):
    """A malformed cell was found. Carries enough detail to name the exact
    row and column in the report; raising it aborts the whole import before
    any database write."""

    def __init__(self, row_num: int, column: str, raw_value: str) -> None:
        self.row_num = row_num
        self.column = column
        self.raw_value = raw_value
        super().__init__(
            f"row {row_num}, column {column!r}: invalid value {raw_value!r}"
        )


class CsvValidationError(Exception):
    """Every malformed cell found in the CSV, reported together."""

    def __init__(self, errors: list[ImportValidationError]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} invalid cell(s)")


# Spreadsheet summary rows are labelled "Сума" ("total") and must not be imported.
TOTAL_ROW_MARKER = "сума"
NUMERIC_COLUMNS = (
    "day_meter",
    "night_meter",
    "day_usage",
    "night_usage",
    "amount_charged",
)


@dataclass
class ParsedRow:
    row_num: int
    csv_id: str
    household_name: str
    day_meter: Decimal
    night_meter: Decimal
    day_usage: Decimal
    night_usage: Decimal
    amount_charged: Decimal


def parse_decimal(raw: str, *, row_num: int, column: str) -> Decimal:
    """Parse a numeric cell as Decimal, accepting a comma decimal separator.
    Raises ImportValidationError rather than silently defaulting to 0 -- the
    behavior this replaces is exactly what corrupted historical charges."""
    if not raw.strip():
        raise ImportValidationError(row_num, column, raw)

    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportValidationError(row_num, column, raw) from exc


def parse_csv(file_path: str) -> list[ParsedRow]:
    """Parse every data row up front and collect every malformed numeric
    cell, so a bad row anywhere in the file blocks the entire import rather
    than writing everything before it. Raises CsvValidationError listing all
    bad cells."""
    rows: list[ParsedRow] = []
    errors: list[ImportValidationError] = []

    with open(file_path, encoding="utf-8", newline="") as meter_file:
        for row_num, row in enumerate(csv.reader(meter_file), start=1):
            if not row or not row[0].strip():
                continue

            # Some sheets lead with a numeric ID column, some don't.
            has_id = row[0].strip().isdigit()
            offset = 1 if has_id else 0

            def cell(idx: int) -> str:
                return row[offset + idx] if offset + idx < len(row) else ""

            name = cell(0).strip()
            if not name or TOTAL_ROW_MARKER in name.lower():
                continue

            values: dict[str, Decimal] = {}
            for idx, column in enumerate(NUMERIC_COLUMNS, start=1):
                try:
                    values[column] = parse_decimal(
                        cell(idx), row_num=row_num, column=column
                    )
                except ImportValidationError as exc:
                    errors.append(exc)

            if not errors:
                rows.append(
                    ParsedRow(
                        row_num=row_num,
                        csv_id=row[0].strip() if has_id else "",
                        household_name=name,
                        **values,
                    )
                )

    if errors:
        raise CsvValidationError(errors)
    return rows


def load_mapping(mapping_path: str) -> dict[str, int]:
    """Load the explicit csv_id -> household_id mapping file. This is the
    only accepted way to match a CSV row to a household."""
    mapping: dict[str, int] = {}

    with open(mapping_path, encoding="utf-8", newline="") as mapping_file:
        reader = csv.DictReader(mapping_file)
        for row_num, row in enumerate(reader, start=2):
            csv_id = (row.get("csv_id") or "").strip()
            household_id_raw = (row.get("household_id") or "").strip()
            if not csv_id or not household_id_raw:
                continue
            try:
                mapping[csv_id] = int(household_id_raw)
            except ValueError as exc:
                raise ImportValidationError(
                    row_num, "household_id", household_id_raw
                ) from exc

    return mapping


def get_valid_household_ids() -> set[int]:
    with Session(engine) as session:
        return set(session.exec(select(Household.id)).all())


def get_period(file_path: str) -> str:
    filename = Path(file_path).stem
    month, year = filename.split("_")
    month_num = datetime.strptime(month, "%B").month
    return f"20{year}-{month_num:02d}"


def match_rows(
    rows: list[ParsedRow], mapping: dict[str, int], valid_household_ids: set[int]
) -> tuple[list[tuple[ParsedRow, int]], list[ParsedRow]]:
    """Splits rows into (row, household_id) matches and unmatched rows. A row
    with no mapping entry, or whose mapped household_id doesn't exist, is
    unmatched -- never guessed at by name."""
    matched: list[tuple[ParsedRow, int]] = []
    unmatched: list[ParsedRow] = []

    for row in rows:
        household_id = mapping.get(row.csv_id)
        if household_id is not None and household_id in valid_household_ids:
            matched.append((row, household_id))
        else:
            unmatched.append(row)

    return matched, unmatched


def print_match_report(
    matched: list[tuple[ParsedRow, int]], unmatched: list[ParsedRow]
) -> None:
    print("\nMatched rows:")
    for row, household_id in matched:
        print(
            f"  row {row.row_num}: csv_id={row.csv_id!r} ({row.household_name!r}) -> household {household_id}"
        )

    print("\nUnmatched rows (will NOT be written):")
    for row in unmatched:
        print(
            f"  row {row.row_num}: csv_id={row.csv_id!r} ({row.household_name!r}) -- no mapping entry"
        )


def insert_meter_history(
    matched: list[tuple[ParsedRow, int]], period: str
) -> tuple[int, list[tuple[ParsedRow, int]]]:
    """Writes matched rows with ON CONFLICT DO NOTHING -- an existing
    (household_id, period) reading is never overwritten. Returns
    (inserted_count, conflicts)."""
    if not matched:
        return 0, []

    # A period's reading is due days 1-5 of the following month.
    year, month = (int(part) for part in period.split("-"))
    due_year, due_month = (year, month + 1) if month < 12 else (year + 1, 1)
    submitted_at = datetime(due_year, due_month, 1, tzinfo=timezone.utc)

    values = [
        {
            "household_id": household_id,
            "period": period,
            "day_meter_value": row.day_meter,
            "night_meter_value": row.night_meter,
            "day_usage_kwh": row.day_usage,
            "night_usage_kwh": row.night_usage,
            "amount_charged_uah": row.amount_charged,
            "submitted_at": submitted_at,
        }
        for row, household_id in matched
    ]

    with Session(engine) as session:
        existing_household_ids = set(
            session.exec(
                select(MeterReading.household_id).where(MeterReading.period == period)
            ).all()
        )
        conflicts = [
            (row, household_id)
            for row, household_id in matched
            if household_id in existing_household_ids
        ]

        stmt = (
            insert(MeterReading)
            .values(values)
            .on_conflict_do_nothing(index_elements=["household_id", "period"])
        )
        session.exec(stmt)
        session.commit()
        # psycopg3 reports rowcount as -1 ("not determined") for a batched
        # INSERT ... ON CONFLICT DO NOTHING, so the actual inserted count has
        # to be derived from what we already know rather than trusted from
        # the driver: every matched row not already flagged as a conflict.
        inserted = len(matched) - len(conflicts)

    return inserted, conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="Path to the historical meter-readings CSV")
    parser.add_argument(
        "--mapping", required=True, help="Path to the csv_id,household_id mapping CSV"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the database (default: dry run)",
    )
    args = parser.parse_args()

    try:
        rows = parse_csv(args.csv_path)
        mapping = load_mapping(args.mapping)
    except CsvValidationError as exc:
        print("Aborting, invalid cells:", file=sys.stderr)
        for error in exc.errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    except ImportValidationError as exc:
        print(f"Aborting: {exc}", file=sys.stderr)
        return 1

    period = get_period(args.csv_path)
    valid_household_ids = get_valid_household_ids()
    matched, unmatched = match_rows(rows, mapping, valid_household_ids)

    print(f"Period: {period}")
    print_match_report(matched, unmatched)

    if not args.apply:
        print("\nDry run: no changes written. Pass --apply to write.")
        return 0

    inserted, conflicts = insert_meter_history(matched, period)

    print(f"\nInserted {inserted} reading(s).")
    if conflicts:
        print("Conflicts (already imported, left unchanged):")
        for row, household_id in conflicts:
            print(
                f"  row {row.row_num}: household {household_id} already has a {period} reading"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
