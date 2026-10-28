from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, desc, select

from app.core import audit
from app.db.models import AuditLog, BillingPeriod, ElectricityRate, User


class NoRateConfiguredError(Exception):
    pass


class EffectiveFromAlreadyExistsError(Exception):
    pass


class RateNotFoundError(Exception):
    pass


class RateUsedByClosedPeriodError(Exception):
    pass


def get_effective_rate(*, session: Session, period: str) -> ElectricityRate:
    rate = session.exec(
        select(ElectricityRate)
        .where(ElectricityRate.effective_from <= period)
        .order_by(desc(ElectricityRate.effective_from))
    ).first()

    if rate is None:
        raise NoRateConfiguredError

    return rate


def list_rates(*, session: Session) -> list[ElectricityRate]:
    return list(
        session.exec(
            select(ElectricityRate).order_by(desc(ElectricityRate.effective_from))
        )
    )


def create_rate(
    *,
    session: Session,
    day_rate_uah: Decimal,
    night_rate_uah: Decimal,
    effective_from: str,
    actor_id: int,
) -> ElectricityRate:
    existing = session.exec(
        select(ElectricityRate).where(ElectricityRate.effective_from == effective_from)
    ).first()
    if existing is not None:
        raise EffectiveFromAlreadyExistsError

    rate = ElectricityRate(
        day_rate_uah=day_rate_uah,
        night_rate_uah=night_rate_uah,
        effective_from=effective_from,
    )
    session.add(rate)
    try:
        session.flush()
        audit.record(
            session,
            actor_user_id=actor_id,
            action="rateCreated",
            entity_type="electricity_rate",
            entity_id=rate.id,
            period=effective_from,
            after={
                "day_rate_uah": day_rate_uah,
                "night_rate_uah": night_rate_uah,
                "effective_from": effective_from,
            },
        )
        session.commit()
    except IntegrityError as exc:
        # Lost the race with a concurrent request; the unique index caught it.
        session.rollback()
        raise EffectiveFromAlreadyExistsError from exc
    session.refresh(rate)
    return rate


def closed_periods_by_rate(*, session: Session) -> dict[int, list[str]]:
    """For each rate, the closed periods it was the effective rate for
    (the latest effective_from not after the period)."""
    rates = sorted(
        session.exec(select(ElectricityRate)).all(), key=lambda r: r.effective_from
    )
    closed = session.exec(
        select(BillingPeriod.period)
        .where(BillingPeriod.status == "closed")
        .order_by(BillingPeriod.period)
    ).all()
    used: dict[int, list[str]] = {rate.id: [] for rate in rates}
    for period in closed:
        governing = None
        for rate in rates:
            if rate.effective_from <= period:
                governing = rate
        if governing is not None:
            used[governing.id].append(period)
    return used


def rate_history(
    *, session: Session, rate_id: int
) -> list[tuple[AuditLog, User | None]]:
    return list(
        session.exec(
            select(AuditLog, User)
            .join(User, col(User.id) == col(AuditLog.actor_user_id), isouter=True)
            .where(
                AuditLog.entity_type == "electricity_rate",
                AuditLog.entity_id == rate_id,
            )
            .order_by(desc(AuditLog.id))
        )
    )


def _editable_rate(*, session: Session, rate_id: int) -> ElectricityRate:
    rate = session.get(ElectricityRate, rate_id)
    if rate is None:
        raise RateNotFoundError
    if closed_periods_by_rate(session=session).get(rate_id):
        raise RateUsedByClosedPeriodError
    return rate


def update_rate(
    *,
    session: Session,
    rate_id: int,
    actor_id: int,
    day_rate_uah: Decimal | None,
    night_rate_uah: Decimal | None,
    reason: str | None,
) -> ElectricityRate:
    rate = _editable_rate(session=session, rate_id=rate_id)
    before = {"day_rate_uah": rate.day_rate_uah, "night_rate_uah": rate.night_rate_uah}
    if day_rate_uah is not None:
        rate.day_rate_uah = day_rate_uah
    if night_rate_uah is not None:
        rate.night_rate_uah = night_rate_uah
    after = {"day_rate_uah": rate.day_rate_uah, "night_rate_uah": rate.night_rate_uah}
    if before != after:
        audit.record(
            session,
            actor_user_id=actor_id,
            action="rateUpdated",
            entity_type="electricity_rate",
            entity_id=rate.id,
            period=rate.effective_from,
            before=before,
            after=after,
            reason=reason,
        )
    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate


def delete_rate(
    *, session: Session, rate_id: int, actor_id: int, reason: str | None
) -> None:
    rate = _editable_rate(session=session, rate_id=rate_id)
    audit.record(
        session,
        actor_user_id=actor_id,
        action="rateDeleted",
        entity_type="electricity_rate",
        entity_id=rate.id,
        period=rate.effective_from,
        before={
            "day_rate_uah": rate.day_rate_uah,
            "night_rate_uah": rate.night_rate_uah,
            "effective_from": rate.effective_from,
        },
        reason=reason,
    )
    session.delete(rate)
    session.commit()
