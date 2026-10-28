"""Import each household's opening balance from the spreadsheet's account column.

Usage:
    cd backend
    uv run python scripts/import_opening_balances.py <csv_path> --mapping <mapping.csv> --as-of YYYY-MM-DD [--apply]

The CSV needs a header row `csv_id,balance`. `balance` is the sheet's
"Стан рахунку" for that household, written as the sheet shows it: negative when
the household owes money, positive when it is in credit. The app stores the
opposite sign (positive = owes), so the sign is flipped here.

`--mapping` is the same csv_id,household_id file `import_meter_history.py`
uses; there is no name matching. Without --apply this is a dry run. A household
that already has an opening balance is reported and left unchanged. Any
malformed row or unmapped csv_id aborts before anything is written.
"""

import argparse
import csv
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

from app.api.billing.payments import (
    HouseholdMissingError,
    OpeningBalanceAlreadySetError,
    set_opening_balance,
)
from app.db.engine import engine
from sqlmodel import Session

from scripts.import_meter_history import ImportValidationError, load_mapping

NOTE = "Imported from spreadsheet"


def parse_balances(csv_path: str, mapping: dict[str, int]) -> dict[int, Decimal]:
    """household_id -> amount owed (positive = owes). Raises ValueError listing
    every bad row."""
    balances: dict[int, Decimal] = {}
    problems: list[str] = []
    with open(csv_path, encoding="utf-8", newline="") as handle:
        for row_num, row in enumerate(csv.DictReader(handle), start=2):
            csv_id = (row.get("csv_id") or "").strip()
            raw = (row.get("balance") or "").strip().replace(",", ".")
            if not csv_id and not raw:
                continue
            household_id = mapping.get(csv_id)
            if household_id is None:
                problems.append(
                    f"row {row_num}: csv_id {csv_id!r} has no mapping entry"
                )
                continue
            try:
                sheet_balance = Decimal(raw)
            except InvalidOperation:
                problems.append(f"row {row_num}: invalid balance {raw!r}")
                continue
            if household_id in balances:
                problems.append(f"row {row_num}: household {household_id} listed twice")
                continue
            balances[household_id] = (-sheet_balance).quantize(Decimal("0.01"))
    if problems:
        raise ValueError("\n".join(problems))
    return balances


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    try:
        balances = parse_balances(args.csv_path, load_mapping(args.mapping))
    except (ValueError, ImportValidationError) as exc:
        print(f"Aborting:\n{exc}", file=sys.stderr)
        return 1

    for household_id, amount in sorted(balances.items()):
        print(f"  household {household_id}: owes {amount} UAH")
    print(f"Total owed: {sum(balances.values(), Decimal('0.00'))} UAH")

    if not args.apply:
        print("\nDry run: no changes written. Pass --apply to write.")
        return 0

    written = 0
    with Session(engine) as session:
        for household_id, amount in balances.items():
            try:
                set_opening_balance(
                    session=session,
                    household_id=household_id,
                    amount_uah=amount,
                    as_of=args.as_of,
                    note=NOTE,
                    actor_id=None,
                )
                written += 1
            except OpeningBalanceAlreadySetError:
                session.rollback()
                print(f"  household {household_id}: already has one, left unchanged")
            except HouseholdMissingError:
                session.rollback()
                print(f"  household {household_id}: does not exist, skipped")
    print(f"\nWrote {written} opening balance(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
