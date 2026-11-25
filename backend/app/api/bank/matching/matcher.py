"""Find the households a bank credit pays from the `STR-<id>` references in its
purpose. A credit with no reference gets a temporary fallback: a household whose
name appears in the purpose, else in the payer name. Tax IDs and IBANs are never
read."""

import re
from dataclasses import dataclass
from typing import Iterable, Literal

from sqlmodel import Session, col, select

from app.db.models import BankTransaction, Household

REFERENCE_PREFIX = "STR"

_REFERENCE_RE = re.compile(rf"\b{REFERENCE_PREFIX}[\s-]?(\d{{1,9}})\b", re.IGNORECASE)

Source = Literal["reference", "name"]


@dataclass(frozen=True)
class Suggestion:
    household_id: int
    source: Source


def household_reference(household_id: int) -> str:
    """The token residents put in the payment purpose (the frontend builds the
    same string for the Pay sheet)."""
    return f"{REFERENCE_PREFIX}-{household_id}"


# Banks write the Ukrainian "і" as a Latin "i"/"I" in these statements.
_FOLD = str.maketrans({"i": "і", "I": "і", "ї": "і", "'": "", "’": "", "ʼ": ""})
_WORD_RE = re.compile(r"[^\W\d_]+")
_MIN_STEM = 4


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.translate(_FOLD).lower().translate(_FOLD))


def _stems(name: str) -> list[str]:
    # Drop up to two trailing letters so declensions and -ий/-а endings agree.
    return [
        w[: max(_MIN_STEM, len(w) - 2)] for w in _words(name) if len(w) >= _MIN_STEM
    ]


def _by_name(text: str, households: list[Household]) -> list[int]:
    words = _words(text)
    found = [
        h.id
        for h in households
        if any(w.startswith(stem) for stem in _stems(h.name) for w in words)
    ]
    return found if len(found) == 1 else []


def match(
    purpose: str, households: Iterable[Household], payer_name: str = ""
) -> list[Suggestion]:
    active = {h.id: h for h in households if h.is_active}

    referenced: list[int] = []
    for found in _REFERENCE_RE.finditer(purpose):
        household_id = int(found.group(1))
        if household_id in active and household_id not in referenced:
            referenced.append(household_id)
    if referenced:
        return [Suggestion(h, "reference") for h in referenced]

    # Temporary: the purpose names the plot holder, who is often not the payer,
    # so it outranks the payer. An ambiguous tier suggests nothing.
    candidates = list(active.values())
    for text in (purpose, payer_name):
        by_name = _by_name(text, candidates)
        if by_name:
            return [Suggestion(by_name[0], "name")]
    return []


def suggest_households(
    session: Session, transactions: list[BankTransaction]
) -> list[list[Suggestion]]:
    """One suggestion list per transaction, in order."""
    households = session.exec(select(Household).where(col(Household.is_active))).all()
    return [match(t.purpose, households, t.payer_name) for t in transactions]
