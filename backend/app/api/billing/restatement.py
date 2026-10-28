"""Correcting a closed period without rewriting it.

The stored household_charges rows never change. A restatement recomputes the
period with the corrected inputs, compares each household with what it
currently owes for that period (stored charge plus earlier adjustments) and
posts the signed differences as charge_adjustments in the current open period.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from sqlmodel import Session, col, desc, func, select

from app.api.billing.service import ensure_period
from app.core import audit
from app.core.time import utc_now
from app.core.domain import (
    ChargeInput,
    current_billing_period,
    derive_usage,
    money,
    next_period,
    reconcile_period,
)
from app.db.models import (
    BillingPeriod,
    ChargeAdjustment,
    ElectricityRate,
    Household,
    HouseholdCharge,
    MeterReading,
    PeriodRestatement,
)

REASON_CODES = {
    "rate": "rateCorrection",
    "readings": "readingCorrection",
    "bill": "billCorrection",
}


class PeriodNotClosedError(Exception):
    pass


class NothingToCorrectError(Exception):
    pass


@dataclass(frozen=True)
class Corrections:
    rate: tuple[Decimal, Decimal] | None = None  # (day, night) UAH per kWh
    bill_total_uah: Decimal | None = None
    # (household_id, period) -> (day, night) meter values
    readings: dict[tuple[int, str], tuple[Decimal, Decimal]] = field(
        default_factory=dict
    )

    def is_empty(self) -> bool:
        return self.rate is None and self.bill_total_uah is None and not self.readings

    def reason_code(self) -> str:
        kinds = [
            kind
            for kind, present in (
                ("rate", self.rate is not None),
                ("bill", self.bill_total_uah is not None),
                ("readings", bool(self.readings)),
            )
            if present
        ]
        return REASON_CODES[kinds[0]] if len(kinds) == 1 else "manual"


@dataclass(frozen=True)
class RestatementLine:
    period: str
    household_id: int
    household_name: str
    before_uah: Decimal
    after_uah: Decimal
    delta_uah: Decimal


@dataclass(frozen=True)
class RestatementResult:
    lines: list[RestatementLine]
    affected_periods: list[str]
    total_delta_uah: Decimal
    restatement_id: int | None
    posted_in_period: str


def _closed_row(*, session: Session, period: str) -> BillingPeriod:
    row = session.get(BillingPeriod, period)
    if row is None or row.status != "closed":
        raise PeriodNotClosedError
    return row


def _is_closed(*, session: Session, period: str) -> bool:
    row = session.get(BillingPeriod, period)
    return row is not None and row.status == "closed"


def posting_period(*, session: Session) -> str:
    """The first period, from the current billing period on, that is still open."""
    period = current_billing_period()
    while _is_closed(session=session, period=period):
        period = next_period(period)
    return period


def _period_rate(*, session: Session, row: BillingPeriod) -> tuple[Decimal, Decimal]:
    rate = session.get(ElectricityRate, row.rate_id) if row.rate_id else None
    if rate is None:
        rate = session.exec(
            select(ElectricityRate)
            .where(ElectricityRate.effective_from <= row.period)
            .order_by(desc(ElectricityRate.effective_from))
        ).first()
    if rate is None:
        return Decimal("0"), Decimal("0")
    return rate.day_rate_uah, rate.night_rate_uah


def _inputs_with_overrides(
    *, session: Session, period: str, corrections: Corrections
) -> list[ChargeInput]:
    readings = {
        r.household_id: r
        for r in session.exec(select(MeterReading).where(MeterReading.period == period))
    }
    household_ids = set(readings) | {
        hid for (hid, p) in corrections.readings if p == period
    }
    owners = {
        h.id: h.user_id
        for h in session.exec(
            select(Household).where(col(Household.id).in_(household_ids))
        )
    }
    inputs = []
    for household_id in sorted(household_ids):
        reading = readings.get(household_id)
        override = corrections.readings.get((household_id, period))
        if override is not None:
            day, night = override
        elif reading is not None:
            day, night = reading.day_meter_value, reading.night_meter_value
        else:
            continue
        previous = session.exec(
            select(MeterReading)
            .where(MeterReading.household_id == household_id)
            .where(MeterReading.period < period)
            .order_by(desc(MeterReading.period))
        ).first()
        prev_values = None
        if previous is not None:
            prev_values = corrections.readings.get(
                (household_id, previous.period),
                (previous.day_meter_value, previous.night_meter_value),
            )
        inputs.append(
            ChargeInput(
                household_id=household_id,
                owner_user_id=owners.get(household_id),
                reading_id=reading.id if reading else None,
                day_usage_kwh=derive_usage(
                    prev_values[0] if prev_values else None, day
                ),
                night_usage_kwh=derive_usage(
                    prev_values[1] if prev_values else None, night
                ),
            )
        )
    return inputs


def _currently_owed(*, session: Session, period: str) -> dict[int, Decimal]:
    owed: dict[int, Decimal] = {}
    for charge in session.exec(
        select(HouseholdCharge).where(HouseholdCharge.period == period)
    ):
        owed[charge.household_id] = charge.total_uah
    rows = session.exec(
        select(ChargeAdjustment.household_id, func.sum(ChargeAdjustment.amount_uah))
        .where(ChargeAdjustment.applies_to_period == period)
        .group_by(col(ChargeAdjustment.household_id))
    ).all()
    for household_id, total in rows:
        owed[household_id] = owed.get(household_id, Decimal("0.00")) + (total or 0)
    return owed


def _diff_period(
    *, session: Session, period: str, corrections: Corrections, is_target: bool
) -> list[RestatementLine]:
    row = _closed_row(session=session, period=period)
    day_rate, night_rate = _period_rate(session=session, row=row)
    bill = row.bill_total_uah
    if is_target:
        if corrections.rate is not None:
            day_rate, night_rate = corrections.rate
        if corrections.bill_total_uah is not None:
            bill = corrections.bill_total_uah

    inputs = _inputs_with_overrides(
        session=session, period=period, corrections=corrections
    )
    result = reconcile_period(
        inputs, day_rate_uah=day_rate, night_rate_uah=night_rate, bill_total_uah=bill
    )
    after = {line.household_id: line.total_uah for line in result.lines}
    before = _currently_owed(session=session, period=period)
    names = {
        h.id: h.name
        for h in session.exec(
            select(Household).where(col(Household.id).in_(set(after) | set(before)))
        )
    }
    lines = []
    for household_id in sorted(set(after) | set(before)):
        old = before.get(household_id, Decimal("0.00"))
        new = after.get(household_id, Decimal("0.00"))
        if money(new - old) != 0:
            lines.append(
                RestatementLine(
                    period=period,
                    household_id=household_id,
                    household_name=names.get(household_id, ""),
                    before_uah=old,
                    after_uah=new,
                    delta_uah=money(new - old),
                )
            )
    return lines


def restate_period(
    *,
    session: Session,
    period: str,
    corrections: Corrections,
    reason: str,
    actor_id: int,
    dry_run: bool,
    extra_inputs: dict | None = None,
    commit: bool = True,
) -> RestatementResult:
    """Posts (or, with `dry_run`, previews) the adjustments for correcting
    `period`. A reading correction also reaches the following period's usage."""
    if corrections.is_empty():
        raise NothingToCorrectError
    _closed_row(session=session, period=period)

    affected = [period]
    if corrections.readings and _is_closed(session=session, period=next_period(period)):
        affected.append(next_period(period))

    lines: list[RestatementLine] = []
    for index, affected_period in enumerate(affected):
        lines.extend(
            _diff_period(
                session=session,
                period=affected_period,
                corrections=corrections,
                is_target=index == 0,
            )
        )

    posted_in = posting_period(session=session)
    total = sum((line.delta_uah for line in lines), Decimal("0.00"))
    if dry_run:
        return RestatementResult(
            lines=lines,
            affected_periods=affected,
            total_delta_uah=total,
            restatement_id=None,
            posted_in_period=posted_in,
        )

    ensure_period(session=session, period=posted_in)
    inputs_record = {
        "rate": (
            {"day_rate_uah": corrections.rate[0], "night_rate_uah": corrections.rate[1]}
            if corrections.rate
            else None
        ),
        "bill_total_uah": corrections.bill_total_uah,
        "readings": [
            {"household_id": hid, "period": p, "day": day, "night": night}
            for (hid, p), (day, night) in sorted(corrections.readings.items())
        ],
        **(extra_inputs or {}),
    }
    restatement = PeriodRestatement(
        period=period,
        reason=reason,
        inputs=audit.jsonable(inputs_record),
        created_by_user_id=actor_id,
    )
    session.add(restatement)
    session.flush()

    owners = {
        c.household_id: c.owner_user_id
        for c in session.exec(
            select(HouseholdCharge).where(col(HouseholdCharge.period).in_(affected))
        )
    }
    current_owners = {
        h.id: h.user_id
        for h in session.exec(
            select(Household).where(
                col(Household.id).in_({line.household_id for line in lines})
            )
        )
    }
    for line in lines:
        session.add(
            ChargeAdjustment(
                household_id=line.household_id,
                owner_user_id=owners.get(line.household_id)
                or current_owners.get(line.household_id),
                applies_to_period=line.period,
                posted_in_period=posted_in,
                amount_uah=line.delta_uah,
                reason_code=corrections.reason_code(),
                reason=reason,
                restatement_id=restatement.id,
                created_by_user_id=actor_id,
            )
        )

    _apply_corrections(
        session=session,
        period=period,
        corrections=corrections,
        actor_id=actor_id,
        reason=reason,
    )
    audit.record(
        session,
        actor_user_id=actor_id,
        action="restatementPosted",
        entity_type="period_restatement",
        entity_id=restatement.id,
        period=period,
        after={
            "affected_periods": affected,
            "households_adjusted": len({line.household_id for line in lines}),
            "total_delta_uah": total,
            "posted_in_period": posted_in,
        },
        reason=reason,
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return RestatementResult(
        lines=lines,
        affected_periods=affected,
        total_delta_uah=total,
        restatement_id=restatement.id,
        posted_in_period=posted_in,
    )


def _apply_corrections(
    *,
    session: Session,
    period: str,
    corrections: Corrections,
    actor_id: int,
    reason: str,
) -> None:
    """The corrected facts become the new truth (raw readings, the bill), while
    the closed charges stay as they were."""
    if corrections.bill_total_uah is not None:
        row = session.get(BillingPeriod, period)
        assert row is not None
        audit.record(
            session,
            actor_user_id=actor_id,
            action="billCorrected",
            entity_type="billing_period",
            period=period,
            before={"total_uah": row.bill_total_uah},
            after={"total_uah": corrections.bill_total_uah},
            reason=reason,
        )
        row.bill_total_uah = corrections.bill_total_uah
        session.add(row)

    for (household_id, reading_period), (day, night) in corrections.readings.items():
        reading = session.exec(
            select(MeterReading)
            .where(MeterReading.household_id == household_id)
            .where(MeterReading.period == reading_period)
        ).first()
        before = (
            {"day": reading.day_meter_value, "night": reading.night_meter_value}
            if reading
            else None
        )
        if reading is None:
            reading = MeterReading(
                household_id=household_id,
                submitted_by_user_id=actor_id,
                period=reading_period,
                source="admin",
            )
        reading.day_meter_value = day
        reading.night_meter_value = night
        reading.needs_review = False
        reading.corrected_at = utc_now()
        reading.correction_reason = reason
        session.add(reading)
        session.flush()
        audit.record(
            session,
            actor_user_id=actor_id,
            action="readingCorrected" if before else "readingSubmittedOnBehalf",
            entity_type="meter_reading",
            entity_id=reading.id,
            household_id=household_id,
            period=reading_period,
            before=before,
            after={"day": day, "night": night},
            reason=reason,
        )


def correct_rate(
    *,
    session: Session,
    rate_id: int,
    day_rate_uah: Decimal,
    night_rate_uah: Decimal,
    reason: str,
    actor_id: int,
    dry_run: bool,
) -> RestatementResult:
    """Fixes a rate that already billed closed periods: restates each of them
    with the corrected values and then updates the rate itself, in one
    transaction. Under the loss-split formula a pure rate change nets to zero
    across households; it only moves money between tariff and loss share."""
    from app.api.electricity_rates.service import (
        RateNotFoundError,
        closed_periods_by_rate,
    )

    rate = session.get(ElectricityRate, rate_id)
    if rate is None:
        raise RateNotFoundError
    periods = closed_periods_by_rate(session=session).get(rate_id, [])

    lines: list[RestatementLine] = []
    affected: list[str] = []
    restatement_id = None
    posted_in = posting_period(session=session)
    for period in periods:
        result = restate_period(
            session=session,
            period=period,
            corrections=Corrections(rate=(day_rate_uah, night_rate_uah)),
            reason=reason,
            actor_id=actor_id,
            dry_run=dry_run,
            extra_inputs={"rate_id": rate_id},
            commit=False,
        )
        lines.extend(result.lines)
        affected.extend(result.affected_periods)
        restatement_id = result.restatement_id or restatement_id
        posted_in = result.posted_in_period

    if not dry_run:
        audit.record(
            session,
            actor_user_id=actor_id,
            action="rateUpdated",
            entity_type="electricity_rate",
            entity_id=rate.id,
            period=rate.effective_from,
            before={
                "day_rate_uah": rate.day_rate_uah,
                "night_rate_uah": rate.night_rate_uah,
            },
            after={"day_rate_uah": day_rate_uah, "night_rate_uah": night_rate_uah},
            reason=reason,
        )
        rate.day_rate_uah = day_rate_uah
        rate.night_rate_uah = night_rate_uah
        session.add(rate)
        session.commit()

    return RestatementResult(
        lines=lines,
        affected_periods=affected,
        total_delta_uah=sum((line.delta_uah for line in lines), Decimal("0.00")),
        restatement_id=restatement_id,
        posted_in_period=posted_in,
    )
