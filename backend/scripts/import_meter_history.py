"""Parse csv file with meter history and import it into the database

Usage:
    cd backend
    uv run python scripts/import_meter_history.py ./scripts/meters/December_24.csv
"""

import csv
import sys
from datetime import datetime
from difflib import SequenceMatcher

from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from app.db.engine import engine
from app.db.models import Household, MeterReading
from sqlmodel import Session, select


def parse_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def parse_decimal(val):
    """Parse decimal value, handling Ukrainian format (comma as decimal separator)"""
    if not val or not isinstance(val, str):
        return 0
    # Remove spaces and convert comma to period
    val = val.strip().replace(" ", "").replace(",", ".")
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0


def get_file_path() -> str:
    if len(sys.argv) != 2:
        print(
            "Check the usage of this script. You need to provide the path to the csv file as an argument."
        )
        sys.exit(1)
    return sys.argv[1]


def parse_csv(file_path: str):
    with open(file_path, "r", encoding="utf-8") as meterFile:
        reader = csv.reader(meterFile)
        rows = []

        for row in reader:
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
            if not name:
                continue

            if "сума" in name.lower():
                continue

            meter_id = parse_int(row[0]) if has_id else None
            amount_charged = parse_decimal(row[amount_idx]) if amount_idx < len(row) else 0

            rows.append(
                {
                    "household_id": meter_id,
                    "household_name": row[name_idx],
                    "day_meter": parse_int(row[day_idx]) if day_idx < len(row) else 0,
                    "night_meter": parse_int(row[night_idx]) if night_idx < len(row) else 0,
                    "day_usage": parse_int(row[day_usage_idx]) if day_usage_idx < len(row) else 0,
                    "night_usage": parse_int(row[night_usage_idx]) if night_usage_idx < len(row) else 0,
                    "amount_charged_uah": amount_charged,
                }
            )

        return rows


def get_households():
    with Session(engine) as session:
        return session.exec(select(Household)).all()


def find_household_match(meter, households):
    meter_id = meter.get("household_id")
    meter_lower = meter["household_name"].lower().strip()

    # Step 1: exact match by ID first
    if meter_id is not None:
        matched = next(
            (h for h in households if h.id == meter_id),
            None,
        )
        if matched is not None:
            return matched

    # Step 2: exact match by name
    matched_household = next(
        (h for h in households if h.name.lower().strip() == meter_lower),
        None,
    )
    if matched_household is not None:
        return matched_household

    # Step 3: surname match or meter_lower in household name
    meter_surname = meter["household_name"].split()[0].lower()
    surname_match = next(
        (
            h
            for h in households
            if h.name.split()[0].lower() == meter_surname
            or meter_lower in h.name.lower()
        ),
        None,
    )
    if surname_match is not None:
        return surname_match

    # Step 4: similarity match
    best_match = None
    best_ratio = 0
    for h in households:
        ratio = SequenceMatcher(None, meter_lower, h.name.lower().strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = h

    return best_match if best_ratio >= 0.85 else None


def get_unmatched_households(parsed_meters, households):
    unmatched = []
    for meter in parsed_meters:
        match = find_household_match(meter, households)
        if match is None:
            unmatched.append(meter["household_name"])
    return unmatched


def get_period() -> str:
    filename = get_file_path().split("/")[-1].replace(".csv", "")
    month, year = filename.split("_")
    month_num = datetime.strptime(month, "%B").month
    return f"20{year}-{month_num:02d}"


def insert_meter_history(parsed_meters):
    period = get_period()

    readings = []
    for meter in parsed_meters:
        if meter["household_id"] is None:
            continue

        readings.append({
            "household_id": meter["household_id"],
            "period": period,
            "day_meter_value": meter["day_meter"],
            "night_meter_value": meter["night_meter"],
            "day_usage_kwh": meter["day_usage"],
            "night_usage_kwh": meter["night_usage"],
            "amount_charged_uah": Decimal(str(meter["amount_charged_uah"])),
        })

    if not readings:
        return

    with Session(engine) as session:
        stmt = (
            insert(MeterReading)
            .values(readings)
            .on_conflict_do_update(
                index_elements=["household_id", "period"],
                set_={
                    "day_meter_value": insert(MeterReading).excluded.day_meter_value,
                    "night_meter_value": insert(MeterReading).excluded.night_meter_value,
                    "day_usage_kwh": insert(MeterReading).excluded.day_usage_kwh,
                    "night_usage_kwh": insert(MeterReading).excluded.night_usage_kwh,
                    "amount_charged_uah": insert(MeterReading).excluded.amount_charged_uah,
                }
            )
        )
        session.exec(stmt)
        session.commit()


def validate_parsed_data(parsed_meters, households):
    for meter in parsed_meters:
        matched_household = find_household_match(meter, households)
        meter["household_id"] = matched_household.id if matched_household else None


def main() -> int:
    file_path = get_file_path()
    parsed_meters = parse_csv(file_path)
    households = get_households()
    unmatched_households = get_unmatched_households(parsed_meters, households)

    print("\nUnmatched Households:")
    for name in unmatched_households:
        print(f" - {name}")

    validate_parsed_data(parsed_meters, households)
    insert_meter_history(parsed_meters)

    return 0


if __name__ == "__main__":
    sys.exit(main())
