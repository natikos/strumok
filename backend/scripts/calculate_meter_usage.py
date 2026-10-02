"""Recalculate day_usage_kwh, night_usage_kwh, and amount_charged_uah for all
meter readings.

For each household, readings are sorted by period and usage is computed as
current meter value minus the previous month's value, clamped to 0.
amount_charged_uah is recomputed from that usage and the rate effective for
the reading's period, so it can't drift out of sync with usage the way it
used to when only usage was recalculated here (issue #145). A period with no
effective rate is skipped and reported, not zeroed out.

Usage:
    cd backend
    uv run python scripts/calculate_meter_usage.py
"""

import sys
from decimal import Decimal

from app.api.electricity_rates.service import NoRateConfiguredError, get_effective_rate
from app.db.engine import engine
from app.db.models import MeterReading
from sqlmodel import Session, col, select


def main() -> int:
    with Session(engine) as session:
        readings = session.exec(
            select(MeterReading).order_by(
                col(MeterReading.household_id), col(MeterReading.period)
            )
        ).all()

        prev_by_household: dict[int, MeterReading] = {}
        updated = 0
        skipped_periods: set[str] = set()

        for reading in readings:
            prev = prev_by_household.get(reading.household_id)
            if prev is not None:
                reading.day_usage_kwh = max(
                    reading.day_meter_value - prev.day_meter_value, Decimal(0)
                )
                reading.night_usage_kwh = max(
                    reading.night_meter_value - prev.night_meter_value, Decimal(0)
                )

                try:
                    rate = get_effective_rate(session=session, period=reading.period)
                except NoRateConfiguredError:
                    skipped_periods.add(reading.period)
                    prev_by_household[reading.household_id] = reading
                    continue

                reading.amount_charged_uah = (
                    reading.day_usage_kwh * rate.day_rate_uah
                    + reading.night_usage_kwh * rate.night_rate_uah
                ).quantize(Decimal("0.01"))

                session.add(reading)
                updated += 1
            prev_by_household[reading.household_id] = reading

        session.commit()
        print(f"Updated {updated} readings.")
        if skipped_periods:
            print(f"Skipped periods with no effective rate: {sorted(skipped_periods)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
