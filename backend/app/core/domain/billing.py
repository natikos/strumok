from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

# Residents are in Kyiv; "the current period" must follow Kyiv local time, not
# server UTC, or a resident near midnight on the 1st sees the wrong month (issue
# #141).
KYIV_TZ = ZoneInfo("Europe/Kyiv")

# Submission window: days 1-5 of the month, Kyiv time. Mirrors DEADLINE_DAY in
# frontend/src/shared/utils/deadline.ts; keep the two in sync.
SUBMISSION_OPEN_DAY = 1
SUBMISSION_DEADLINE_DAY = 5


def previous_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def kyiv_now() -> datetime:
    return datetime.now(KYIV_TZ)


def current_billing_period(now: datetime | None = None) -> str:
    """The period residents currently submit a reading for (the prior calendar
    month), based on Kyiv local time. Pass `now` (a tz-aware datetime) in tests;
    live callers get the actual current Kyiv time."""
    reference = now if now is not None else kyiv_now()
    return previous_period(reference.astimezone(KYIV_TZ).strftime("%Y-%m"))


CENT = Decimal("0.01")


def derive_usage(previous_value: Decimal | None, value: Decimal) -> Decimal:
    """kWh used since the previous reading. The first reading is a baseline
    (no usage), and a meter that reads lower than before counts as zero."""
    if previous_value is None:
        return Decimal("0")
    return max(value - previous_value, Decimal("0"))


def money(amount: Decimal) -> Decimal:
    """Final rounding for a UAH amount. ROUND_HALF_UP so a resident can
    reproduce it with a calculator."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ChargeInput:
    household_id: int
    owner_user_id: int | None
    reading_id: int | None
    day_usage_kwh: Decimal
    night_usage_kwh: Decimal
    is_estimated: bool = False


@dataclass(frozen=True)
class ChargeLine:
    household_id: int
    owner_user_id: int | None
    reading_id: int | None
    day_usage_kwh: Decimal
    night_usage_kwh: Decimal
    is_estimated: bool
    tariff_uah: Decimal
    loss_share_uah: Decimal
    penalty_uah: Decimal
    penalty_credit_uah: Decimal
    total_uah: Decimal


def compute_period_statement(
    inputs: Sequence[ChargeInput],
    *,
    day_rate_uah: Decimal,
    night_rate_uah: Decimal,
) -> list[ChargeLine]:
    """Pure: no database, no clock. Slice 1 is tariff-only (usage × rate); the
    loss share, estimates and penalties plug into the same lines later.
    Lines come back ordered by household_id."""
    lines = []
    for item in sorted(inputs, key=lambda i: i.household_id):
        tariff = money(
            item.day_usage_kwh * day_rate_uah + item.night_usage_kwh * night_rate_uah
        )
        lines.append(
            ChargeLine(
                household_id=item.household_id,
                owner_user_id=item.owner_user_id,
                reading_id=item.reading_id,
                day_usage_kwh=item.day_usage_kwh,
                night_usage_kwh=item.night_usage_kwh,
                is_estimated=item.is_estimated,
                tariff_uah=tariff,
                loss_share_uah=Decimal("0.00"),
                penalty_uah=Decimal("0.00"),
                penalty_credit_uah=Decimal("0.00"),
                total_uah=tariff,
            )
        )
    return lines
