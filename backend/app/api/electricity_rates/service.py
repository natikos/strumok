from decimal import Decimal

from sqlmodel import Session, desc, select

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
    session.commit()
    session.refresh(rate)
    return rate
