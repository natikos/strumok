"""Payments and balances. A balance is always derived from the ledgers:
charges + adjustments - non-voided payments, so a late adjustment or a voided
payment just changes the sum."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlmodel import Session, col, desc, func, select

from app.core import audit
from app.core.time import utc_now
from app.db.models import (
    ChargeAdjustment,
    Household,
    HouseholdCharge,
    Payment,
    User,
)

ZERO = Decimal("0.00")


class PaymentNotFoundError(Exception):
    pass


class PaymentAlreadyVoidedError(Exception):
    pass


class HouseholdMissingError(Exception):
    pass


@dataclass(frozen=True)
class PeriodBalance:
    period: str
    due_uah: Decimal
    paid_uah: Decimal
    status: str  # 'paid' | 'partial' | 'unpaid'


@dataclass(frozen=True)
class Balance:
    household_id: int
    total_due_uah: Decimal
    total_paid_uah: Decimal
    balance_uah: Decimal  # negative is a credit
    unpaid_months: int
    periods: list[PeriodBalance]


def record_payment(
    *,
    session: Session,
    household_id: int,
    amount_uah: Decimal,
    paid_on: date,
    method: str,
    note: str | None,
    actor_id: int,
) -> Payment:
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdMissingError
    payment = Payment(
        household_id=household_id,
        owner_user_id=household.user_id,
        amount_uah=amount_uah,
        paid_on=paid_on,
        method=method,
        note=note,
        recorded_by_user_id=actor_id,
    )
    session.add(payment)
    session.flush()
    audit.record(
        session,
        actor_user_id=actor_id,
        action="paymentRecorded",
        entity_type="payment",
        entity_id=payment.id,
        household_id=household_id,
        after={
            "amount_uah": amount_uah,
            "paid_on": paid_on,
            "method": method,
            "note": note,
        },
    )
    session.commit()
    session.refresh(payment)
    return payment


def void_payment(
    *, session: Session, payment_id: int, reason: str, actor_id: int
) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise PaymentNotFoundError
    if payment.voided_at is not None:
        raise PaymentAlreadyVoidedError
    payment.voided_at = utc_now()
    payment.voided_by_user_id = actor_id
    payment.void_reason = reason
    session.add(payment)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="paymentVoided",
        entity_type="payment",
        entity_id=payment.id,
        household_id=payment.household_id,
        before={"amount_uah": payment.amount_uah, "paid_on": payment.paid_on},
        reason=reason,
    )
    session.commit()
    session.refresh(payment)
    return payment


def list_payments(*, session: Session, household_id: int) -> list[Payment]:
    return list(
        session.exec(
            select(Payment)
            .where(Payment.household_id == household_id)
            .order_by(desc(Payment.paid_on), desc(Payment.id))
        )
    )


def _dues_by_period(*, session: Session, household_id: int) -> dict[str, Decimal]:
    dues: dict[str, Decimal] = {}
    for charge in session.exec(
        select(HouseholdCharge).where(HouseholdCharge.household_id == household_id)
    ):
        dues[charge.period] = dues.get(charge.period, ZERO) + charge.total_uah
    for adjustment in session.exec(
        select(ChargeAdjustment).where(ChargeAdjustment.household_id == household_id)
    ):
        key = adjustment.applies_to_period
        dues[key] = dues.get(key, ZERO) + adjustment.amount_uah
    return dues


def _paid_total(*, session: Session, household_id: int) -> Decimal:
    return (
        session.exec(
            select(func.coalesce(func.sum(Payment.amount_uah), 0)).where(
                Payment.household_id == household_id, col(Payment.voided_at).is_(None)
            )
        ).one()
        or ZERO
    )


def get_balance(*, session: Session, household_id: int) -> Balance:
    """Oldest periods are settled first, so a partial payment covers the early
    months and the status of each period reads naturally."""
    dues = _dues_by_period(session=session, household_id=household_id)
    paid_total = Decimal(_paid_total(session=session, household_id=household_id))
    remaining = paid_total

    periods = []
    for period in sorted(dues):
        due = dues[period]
        applied = ZERO
        if due > 0 and remaining > 0:
            applied = min(due, remaining)
            remaining -= applied
        if due <= 0 or applied >= due:
            status = "paid"
        elif applied > 0:
            status = "partial"
        else:
            status = "unpaid"
        periods.append(
            PeriodBalance(period=period, due_uah=due, paid_uah=applied, status=status)
        )

    total_due = sum(dues.values(), ZERO)
    return Balance(
        household_id=household_id,
        total_due_uah=total_due,
        total_paid_uah=paid_total,
        balance_uah=total_due - paid_total,
        unpaid_months=sum(1 for p in periods if p.status != "paid"),
        periods=periods,
    )


@dataclass(frozen=True)
class HouseholdBalanceRow:
    household_id: int
    household_name: str
    owner_name: str | None
    balance_uah: Decimal
    unpaid_months: int


def list_balances(*, session: Session) -> list[HouseholdBalanceRow]:
    households = session.exec(select(Household)).all()
    owners = {
        u.id: f"{u.first_name} {u.last_name}"
        for u in session.exec(
            select(User).where(
                col(User.id).in_([h.user_id for h in households if h.user_id])
            )
        )
    }
    rows = []
    for household in households:
        balance = get_balance(session=session, household_id=household.id)
        rows.append(
            HouseholdBalanceRow(
                household_id=household.id,
                household_name=household.name,
                owner_name=owners.get(household.user_id) if household.user_id else None,
                balance_uah=balance.balance_uah,
                unpaid_months=balance.unpaid_months,
            )
        )
    return sorted(rows, key=lambda r: (-r.balance_uah, r.household_name))
