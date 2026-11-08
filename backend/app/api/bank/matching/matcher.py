"""Find the households a bank credit pays from the `STR-<id>` references in its
purpose. That reference is the only signal: payer names, tax IDs and IBANs are
never read."""

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from sqlmodel import Session, col, select

from app.db.models import BankTransaction, Household

REFERENCE_PREFIX = "STR"

_REFERENCE_RE = re.compile(rf"\b{REFERENCE_PREFIX}[\s-]?(\d{{1,9}})\b", re.IGNORECASE)

Source = Literal["reference"]


@dataclass(frozen=True)
class Suggestion:
    household_id: int
    source: Source


def household_reference(household_id: int) -> str:
    """The token residents put in the payment purpose (the frontend builds the
    same string for the Pay sheet)."""
    return f"{REFERENCE_PREFIX}-{household_id}"


def match(purpose: str, households: Iterable[Household]) -> list[Suggestion]:
    active = {h.id: h for h in households if h.is_active}

    referenced: list[int] = []
    for found in _REFERENCE_RE.finditer(purpose):
        household_id = int(found.group(1))
        if household_id in active and household_id not in referenced:
            referenced.append(household_id)
    return [Suggestion(h, "reference") for h in referenced]


def suggest_households(
    session: Session, transactions: list[BankTransaction]
) -> list[list[Suggestion]]:
    """One suggestion list per transaction, in order."""
    households = session.exec(select(Household).where(col(Household.is_active))).all()
    return [match(t.purpose, households) for t in transactions]
