"""Recalculate day_usage_kwh and night_usage_kwh for all meter readings.

For each household, readings are sorted by period and usage is computed as
current meter value minus the previous month's value, clamped to 0.

Usage:
    cd backend
    uv run python scripts/calculate_meter_usage.py
"""

import sys
from decimal import Decimal

from app.db.engine import engine
from app.db.models import MeterReading
from sqlmodel import Session, col, select


def main() -> int:
    with Session(engine) as session:
        readings = session.exec(
            select(MeterReading).order_by(col(MeterReading.household_id), col(MeterReading.period))
        ).all()

        prev_by_household: dict[int, MeterReading] = {}
        updated = 0

        for reading in readings:
            prev = prev_by_household.get(reading.household_id)
            if prev is not None:
                reading.day_usage_kwh = max(reading.day_meter_value - prev.day_meter_value, Decimal(0))
                reading.night_usage_kwh = max(reading.night_meter_value - prev.night_meter_value, Decimal(0))
                session.add(reading)
                updated += 1
            prev_by_household[reading.household_id] = reading

        session.commit()
        print(f"Updated {updated} readings.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
