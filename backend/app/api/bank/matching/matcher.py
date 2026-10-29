"""Suggest households for a bank credit from its purpose text, then its payer
name. Purely textual and deterministic: the payer's tax ID and IBAN are never
read, and a suggestion only pre-fills the review dialog; an admin still has to
confirm."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Literal

from sqlmodel import Session, col, select

from app.db.models import BankTransaction, Household

REFERENCE_PREFIX = "STR"
MIN_NAME_TOKEN = 4
NAME_SIMILARITY = 0.85

_REFERENCE_RE = re.compile(rf"\b{REFERENCE_PREFIX}[\s-]?(\d{{1,9}})\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[^\W\d_]+")

Source = Literal["reference", "name"]


@dataclass(frozen=True)
class Suggestion:
    household_id: int
    source: Source


def household_reference(household_id: int) -> str:
    """The token residents put in the payment purpose (the frontend builds the
    same string for the Pay sheet)."""
    return f"{REFERENCE_PREFIX}-{household_id}"


def _tokens(text: str) -> set[str]:
    return {t.casefold() for t in _TOKEN_RE.findall(text) if len(t) >= MIN_NAME_TOKEN}


def _names_match(payer: set[str], household: set[str]) -> bool:
    return any(
        SequenceMatcher(None, a, b).ratio() >= NAME_SIMILARITY
        for a in payer
        for b in household
    )


def match(
    purpose: str, payer_name: str, households: Iterable[Household]
) -> list[Suggestion]:
    active = {h.id: h for h in households if h.is_active}

    referenced: list[int] = []
    for found in _REFERENCE_RE.finditer(purpose):
        household_id = int(found.group(1))
        if household_id in active and household_id not in referenced:
            referenced.append(household_id)
    if referenced:
        return [Suggestion(h, "reference") for h in referenced]

    payer = _tokens(payer_name)
    if not payer:
        return []
    candidates = [h.id for h in active.values() if _names_match(payer, _tokens(h.name))]
    # Several plausible households is no better than none.
    if len(candidates) == 1:
        return [Suggestion(candidates[0], "name")]
    return []


def suggest_households(
    session: Session, transactions: list[BankTransaction]
) -> list[list[Suggestion]]:
    """One suggestion list per transaction, in order."""
    households = session.exec(select(Household).where(col(Household.is_active))).all()
    return [match(t.purpose, t.payer_name, households) for t in transactions]
