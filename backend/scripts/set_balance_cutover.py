"""Settle each household's history up to a date from the spreadsheet balance.

Usage:
    cd backend
    uv run python scripts/set_balance_cutover.py <csv_path> --mapping <mapping.csv> --as-of YYYY-MM-DD [--apply]

The CSV and mapping are the same as for `import_opening_balances.py`
(`csv_id,balance` with the sheet's "Стан рахунку", negative = owes). `--as-of`
is the day the sheet balance was struck, e.g. 2026-09-30 to leave only October
onward payable. Months ending on or before it and payments dated on or before
it stop counting: the sheet balance already contains them.

Without --apply this is a dry run that prints each household's balance before
and after, and writes nothing. A household whose current cutover or opening
balance is already as late as `--as-of` is skipped.
"""

import argparse
import sys
from datetime import date

from app.api.billing.payments import get_balance, settled_through
from app.core import audit
from app.db.engine import engine
from app.db.models import BalanceCutover, Household
from sqlmodel import Session

from scripts.import_meter_history import ImportValidationError, load_mapping
from scripts.import_opening_balances import parse_balances

NOTE = "Cutover from spreadsheet"


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

    written = 0
    with Session(engine) as session:
        for household_id, amount in sorted(balances.items()):
            household = session.get(Household, household_id)
            if household is None:
                print(f"  household {household_id}: does not exist, skipped")
                continue
            current = settled_through(session=session, household_id=household_id)
            if current is not None and current >= args.as_of:
                print(
                    f"  household {household_id}: already settled through {current}, skipped"
                )
                continue
            before = get_balance(session=session, household_id=household_id)
            cutover = BalanceCutover(
                household_id=household_id,
                owner_user_id=household.user_id,
                amount_uah=amount,
                as_of=args.as_of,
                note=NOTE,
            )
            session.add(cutover)
            session.flush()
            audit.record(
                session,
                actor_user_id=None,
                action="balanceCutoverSet",
                entity_type="balance_cutover",
                entity_id=cutover.id,
                household_id=household_id,
                after={"amount_uah": amount, "as_of": args.as_of, "note": NOTE},
            )
            after = get_balance(session=session, household_id=household_id)
            print(
                f"  household {household_id}: owed {before.balance_uah} "
                f"({before.unpaid_months} unpaid months) -> {after.balance_uah} "
                f"({after.unpaid_months} unpaid months)"
            )
            written += 1

        if args.apply:
            session.commit()
            print(f"\nWrote {written} cutover(s).")
        else:
            session.rollback()
            print(
                f"\nDry run: {written} cutover(s) would be written. Pass --apply to write."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
