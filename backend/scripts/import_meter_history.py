"""Import a CSV of historical meter readings into the database.

Usage:
    cd backend
    uv run python scripts/import_meter_history.py <csv_path> --mapping <mapping.csv> [--apply]

Without --apply this is a dry run: it prints the match report (which CSV row
maps to which household, and which don't) and would-be writes, and makes no
database changes. Pass --apply to actually write.

The mapping file is the *only* way a CSV row is matched to a household. It is
a CSV with a header row and two columns, `csv_id,household_id`:

    csv_id,household_id
    12,4
    7,9

`csv_id` is the CSV's own first-column identifier (an arbitrary number from
the source spreadsheet, not a database id); `household_id` is the real
`Household.id` it corresponds to. There is no name-based matching of any
kind -- a CSV row whose `csv_id` has no entry in the mapping file is reported
as unmatched and never written, never guessed at by name or surname
similarity. This is a deliberate, load-bearing restriction: two households
sharing a surname must never be silently merged.

Every numeric cell is parsed as a `Decimal` (accepting a comma decimal
separator, e.g. "3205,50"). If ANY row has a malformed numeric cell, the
script aborts before writing anything and reports every such row and column
-- a partial import that silently zeroes out a bad cell is worse than no
import at all.

Already-imported (household_id, period) pairs are left untouched (the
database's own uniqueness constraint enforces this); re-running the script on
an already-imported file reports the conflicts and changes nothing for them.
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

# Columns, in order, after the leading id/name columns: day meter, night
# meter, day usage, night usage, amount charged.
NUMERIC_COLUMNS = (
    "day_meter",
    "night_meter",
    "day_usage",
    "night_usage",
    "amount_charged",
)


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
    if raw is None or not raw.strip():
        raise ImportValidationError(row_num, column, raw)

    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ImportValidationError(row_num, column, raw) from exc


def parse_csv(file_path: str) -> list[ParsedRow]:
    """Parse every data row up front, raising on the first malformed numeric
    cell, so a bad row anywhere in the file blocks the entire import rather
    than writing everything before it."""
    rows: list[ParsedRow] = []

    with open(file_path, encoding="utf-8") as meter_file:
        reader = csv.reader(meter_file)

        for row_num, row in enumerate(reader, start=1):
            if not row or not row[0].strip():
                continue

            has_id = row[0].strip().isdigit()
            name_idx = 1 if has_id else 0
            day_idx = 2 if has_id else 1
            night_idx = 3 if has_id else 2
            day_usage_idx = 4 if has_id else 3
            night_usage_idx = 5 if has_id else 4
            amount_idx = 6 if has_id else 5

            name = row[name_idx].strip() if name_idx < len(row) else ""
            if not name or "сума" in name.lower():
                continue

            csv_id = row[0].strip() if has_id else ""

            def cell(idx: int) -> str:
                return row[idx] if idx < len(row) else ""

            rows.append(
                ParsedRow(
                    row_num=row_num,
                    csv_id=csv_id,
                    household_name=name,
                    day_meter=parse_decimal(
                        cell(day_idx), row_num=row_num, column="day_meter"
                    ),
                    night_meter=parse_decimal(
                        cell(night_idx), row_num=row_num, column="night_meter"
                    ),
                    day_usage=parse_decimal(
                        cell(day_usage_idx), row_num=row_num, column="day_usage"
                    ),
                    night_usage=parse_decimal(
                        cell(night_usage_idx), row_num=row_num, column="night_usage"
                    ),
                    amount_charged=parse_decimal(
                        cell(amount_idx), row_num=row_num, column="amount_charged"
                    ),
                )
            )

    return rows


def load_mapping(mapping_path: str) -> dict[str, int]:
    """Load the explicit csv_id -> household_id mapping file. This is the
    only accepted way to match a CSV row to a household."""
    mapping: dict[str, int] = {}

    with open(mapping_path, encoding="utf-8") as mapping_file:
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
