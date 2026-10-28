from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, desc, select

from app.core import audit
from app.db.models import ElectricityRate


class NoRateConfiguredError(Exception):
    pass


class EffectiveFromAlreadyExistsError(Exception):
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
