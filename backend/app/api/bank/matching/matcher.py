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
_SHORT = 4
_ENDINGS = "аеиіоуюя"


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.translate(_FOLD).lower().translate(_FOLD))


def _is_form_of(word: str, surname: str) -> bool:
    """Whether `word` is the surname in some case. Long surnames lose up to two
    trailing letters so -ий/-а endings agree; short ones ("Бук", "Дуб") must match
    exactly or take one vowel, so "Дуб" never matches "дубль"."""
    if len(surname) <= _SHORT:
        return word == surname or (
            len(word) == len(surname) + 1
            and word.startswith(surname)
            and word[-1] in _ENDINGS
        )
    return word.startswith(surname[: max(_MIN_STEM, len(surname) - 2)])


@dataclass(frozen=True)
class _PlotName:
    surname: str
    initials: tuple[str, ...]
    aliases: tuple[str, ...]


def _plot_name(name: str) -> _PlotName | None:
    """ "Гончаренко І.(1)" is surname Гончаренко, initial і; the names in
    brackets ("Савчук (Гончаренко)", the previous holder, a relative) are
    only aliases."""
    head, _, rest = name.partition("(")
    words = _words(head)
    if not words:
        return None
    surname = next((w for w in words if len(w) > 1), None)
    if surname is None:
        return None
    initials = tuple(w for w in words if len(w) == 1)
    aliases = tuple(w for w in _words(rest) if len(w) >= _SHORT - 1)
    return _PlotName(surname, initials, aliases)


def _narrow(found: list[tuple[int, _PlotName]], words: list[str]) -> list[int]:
    """Several plots share the surname: keep those whose first initial starts
    some other word of the text ("Мельник Андрій" is А. Д., not В. Д.)."""
    if len(found) > 1:
        initialed = [
            h
            for h, plot in found
            if plot.initials
            and any(
                w[0] == plot.initials[0]
                for w in words
                if not _is_form_of(w, plot.surname)
            )
        ]
        if initialed:
            return initialed
    return [h for h, _ in found]


def _by_name(text: str, households: list[Household]) -> list[int]:
    words = _words(text)
    plots = [(h.id, p) for h in households if (p := _plot_name(h.name))]
    primary = [
        (h, p) for h, p in plots if any(_is_form_of(w, p.surname) for w in words)
    ]
    if primary:
        narrowed = _narrow(primary, words)
        return narrowed if len(narrowed) == 1 else []
    alias = [
        h for h, p in plots if any(_is_form_of(w, a) for a in p.aliases for w in words)
    ]
    return alias if len(alias) == 1 else []


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
