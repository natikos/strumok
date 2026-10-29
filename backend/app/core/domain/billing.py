from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.core.time import now_utc_aware

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


def next_period(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    if month == 12:
        return f"{year + 1}-01"
    return f"{year}-{month + 1:02d}"


def period_window_closed(period: str, now: datetime | None = None) -> bool:
    """Whether the submission window for `period` is over: it runs through day
    SUBMISSION_DEADLINE_DAY of the following month, Kyiv time. Only then may
    the head close the period."""
    reference = (now if now is not None else kyiv_now()).astimezone(KYIV_TZ)
    year, month = (int(part) for part in next_period(period).split("-"))
    first_day_after_window = datetime(
        year, month, SUBMISSION_DEADLINE_DAY + 1, tzinfo=KYIV_TZ
    )
    return reference >= first_day_after_window


def kyiv_now() -> datetime:
    return now_utc_aware().astimezone(KYIV_TZ)


def current_billing_period(now: datetime | None = None) -> str:
    """The period residents currently submit a reading for (the prior calendar
    month), based on Kyiv local time. Pass `now` (a tz-aware datetime) in tests;
    live callers get the actual current Kyiv time."""
    reference = now if now is not None else kyiv_now()
    return previous_period(reference.astimezone(KYIV_TZ).strftime("%Y-%m"))


CENT = Decimal("0.01")
LATE_PENALTY_RATE = Decimal("0.30")


def derive_usage(
    previous_value: Decimal | None,
    value: Decimal,
    *,
    previous_is_estimate: bool = False,
) -> Decimal:
    """kWh used since the previous reading. The first reading is a baseline
    (no usage), and a meter that reads lower than before counts as zero.

    Measured against an *estimate*, a lower real reading is a true-up, not a
    meter fault: the difference stays negative so the over-estimate comes back
    as a credit instead of being clamped away."""
    if previous_value is None:
        return Decimal("0")
    if previous_is_estimate:
        return value - previous_value
    return max(value - previous_value, Decimal("0"))


def derive_usage_across_replacement(
    previous_value: Decimal | None,
    value: Decimal,
    *,
    old_final: Decimal,
    new_start: Decimal,
    previous_is_estimate: bool = False,
) -> Decimal:
    """kWh in a period where the meter was replaced: what the old meter
    recorded after the previous reading, plus what the new one recorded since
    its starting value."""
    return derive_usage(
        previous_value, old_final, previous_is_estimate=previous_is_estimate
    ) + max(value - new_start, Decimal("0"))


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


@dataclass(frozen=True)
class Reconciliation:
    lines: list[ChargeLine]
    total_tariff_uah: Decimal
    # bill_total - Σ tariff; negative when the meters read high. None until the
    # bill is known.
    loss_uah: Decimal | None
    # Households that received the extra kopeck(s) from largest-remainder
    # rounding, lowest id first.
    remainder_household_ids: list[int]


def allocate_by_largest_remainder(
    total: Decimal, weights: dict[int, Decimal]
) -> tuple[dict[int, Decimal], list[int]]:
    """Splits `total` (a whole number of kopecks, positive or negative) across
    households pro-rata by `weights`, so the parts sum to `total` exactly.
    Fractions go to the largest remainders, ties to the lowest household id.
    With no weight at all the split is equal. Returns the shares and the ids
    that received a remainder kopeck."""
    kopecks = int((total / CENT).to_integral_value())
    if not weights:
        return {}, []
    sign = -1 if kopecks < 0 else 1
    magnitude = abs(kopecks)

    effective = {h: max(w, Decimal("0")) for h, w in weights.items()}
    if sum(effective.values()) == 0:
        effective = {h: Decimal("1") for h in weights}
    weight_sum = sum(effective.values())

    exact = {h: Decimal(magnitude) * w / weight_sum for h, w in effective.items()}
    floors = {h: int(v) for h, v in exact.items()}
    leftover = magnitude - sum(floors.values())
    by_remainder = sorted(exact, key=lambda h: (-(exact[h] - floors[h]), h))
    recipients = sorted(by_remainder[:leftover])
    for household_id in recipients:
        floors[household_id] += 1

    return {h: Decimal(sign * k) * CENT for h, k in floors.items()}, recipients


def reconcile_period(
    inputs: Sequence[ChargeInput],
    *,
    day_rate_uah: Decimal,
    night_rate_uah: Decimal,
    bill_total_uah: Decimal | None = None,
) -> Reconciliation:
    """Pure: no database, no clock. tariff = usage × rate; with the bill known,
    the gap between the bill and Σ tariff (line losses, common lighting, meter
    drift; possibly negative) is split pro-rata by usage so that
    Σ (tariff + loss share) equals the bill exactly."""
    ordered = sorted(inputs, key=lambda i: i.household_id)
    tariffs = {
        item.household_id: money(
            item.day_usage_kwh * day_rate_uah + item.night_usage_kwh * night_rate_uah
        )
        for item in ordered
    }
    total_tariff = sum(tariffs.values(), Decimal("0.00"))

    shares: dict[int, Decimal] = {
        item.household_id: Decimal("0.00") for item in ordered
    }
    recipients: list[int] = []
    loss = None
    if bill_total_uah is not None:
        loss = money(bill_total_uah) - total_tariff
        shares, recipients = allocate_by_largest_remainder(
            loss,
            {i.household_id: i.day_usage_kwh + i.night_usage_kwh for i in ordered},
        )

    # A household that didn't submit pays a late fee on its estimated tariff
    # (not on its loss share). The fees are handed back pro-rata by usage to the
    # households that did submit, so the charges still add up to the bill.
    on_time = [i for i in ordered if not i.is_estimated]
    penalties = {
        item.household_id: (
            money(tariffs[item.household_id] * LATE_PENALTY_RATE)
            if item.is_estimated and tariffs[item.household_id] > 0 and on_time
            else Decimal("0.00")
        )
        for item in ordered
    }
    total_penalty = sum(penalties.values(), Decimal("0.00"))
    credits: dict[int, Decimal] = {
        item.household_id: Decimal("0.00") for item in ordered
    }
    if total_penalty:
        shared, _ = allocate_by_largest_remainder(
            total_penalty,
            {i.household_id: i.day_usage_kwh + i.night_usage_kwh for i in on_time},
        )
        credits.update(shared)

    lines = [
        ChargeLine(
            household_id=item.household_id,
            owner_user_id=item.owner_user_id,
            reading_id=item.reading_id,
            day_usage_kwh=item.day_usage_kwh,
            night_usage_kwh=item.night_usage_kwh,
            is_estimated=item.is_estimated,
            tariff_uah=tariffs[item.household_id],
            loss_share_uah=shares[item.household_id],
            penalty_uah=penalties[item.household_id],
            penalty_credit_uah=credits[item.household_id],
            total_uah=(
                tariffs[item.household_id]
                + shares[item.household_id]
                + penalties[item.household_id]
                - credits[item.household_id]
            ),
        )
        for item in ordered
    ]
    return Reconciliation(
        lines=lines,
        total_tariff_uah=total_tariff,
        loss_uah=loss,
        remainder_household_ids=recipients,
    )


def compute_period_statement(
    inputs: Sequence[ChargeInput],
    *,
    day_rate_uah: Decimal,
    night_rate_uah: Decimal,
    bill_total_uah: Decimal | None = None,
) -> list[ChargeLine]:
    """The charge lines of `reconcile_period`, ordered by household_id."""
    return reconcile_period(
        inputs,
        day_rate_uah=day_rate_uah,
        night_rate_uah=night_rate_uah,
        bill_total_uah=bill_total_uah,
    ).lines


SPIKE_FACTOR = Decimal("3")
SPIKE_FLOOR_KWH = Decimal("50")


def median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def detect_review_reason(
    *,
    previous: tuple[Decimal, Decimal] | None,
    recent_usages_kwh: Sequence[Decimal],
    day_meter_value: Decimal,
    night_meter_value: Decimal,
) -> str | None:
    """Why a freshly submitted reading deserves the head's eye, or None.

    `previous` is the household's last real (non-estimate) reading; the recent
    usages are its last up-to-3 real usages. A decrease might be a typo or a
    replaced meter; a spike is usage over 3x the recent median and over 50 kWh
    (the floor keeps tiny baselines from tripping it). The reading is always
    accepted; this only flags it."""
    if previous is None:
        return None
    previous_day, previous_night = previous
    if day_meter_value < previous_day or night_meter_value < previous_night:
        return "decrease"
    usage = (day_meter_value - previous_day) + (night_meter_value - previous_night)
    if (
        recent_usages_kwh
        and usage > SPIKE_FLOOR_KWH
        and usage > SPIKE_FACTOR * median(recent_usages_kwh)
    ):
        return "spike"
    return None
