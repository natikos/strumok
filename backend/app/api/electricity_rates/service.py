from sqlmodel import Session, desc, select

from app.db.models import ElectricityRate


class NoRateConfiguredError(Exception):
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
