from app.api.bank.matching.matcher import household_reference, match
from app.db.models import Household


def _h(id: int, name: str, active: bool = True) -> Household:
    return Household(id=id, name=name, is_active=active)


HOUSEHOLDS = [_h(1, "Іваненко"), _h(2, "Петренко Олег"), _h(3, "Шевчук", False)]


def test_reference_in_purpose():
    found = match(f"Електроенергія {household_reference(2)}", "", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(2, "reference")]


def test_split_references_in_order_without_duplicates():
    purpose = "STR-2, str 1 та STR-2"
    found = match(purpose, "Хтось", HOUSEHOLDS)
    assert [s.household_id for s in found] == [2, 1]


def test_unknown_or_inactive_reference_falls_through():
    assert match("STR-99 STR-3", "", HOUSEHOLDS) == []


def test_reference_is_not_a_substring_match():
    assert match("MYSTR-1", "", HOUSEHOLDS) == []


def test_fuzzy_surname():
    found = match("за світло", "Іваненко Петро Іванович", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(1, "name")]


def test_fuzzy_tolerates_typo():
    found = match("", "Петренко О.", HOUSEHOLDS)
    assert [s.household_id for s in found] == [2]


def test_ambiguous_name_is_unmatched():
    both = [_h(1, "Іваненко"), _h(2, "Іваненко")]
    assert match("", "Іваненко", both) == []


def test_unmatched():
    assert match("оплата", "Сидоренко", HOUSEHOLDS) == []


def test_reference_beats_name():
    found = match("STR-2", "Іваненко", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(2, "reference")]


def test_queue_suggests_by_reference_and_confirms_nothing(client, session) -> None:
    from sqlmodel import select

    from app.db.models import Payment
    from tests.test_bank_review import _admin, _tx

    _admin(client, session)
    from tests.factories import make_household

    household = make_household(session)
    tx = _tx(session)
    tx.purpose = f"Електрика {household_reference(household.id)}"
    session.add(tx)
    session.commit()

    row = client.get("/admin/bank-transactions").json()[0]
    assert row["suggestions"] == [{"household_id": household.id, "source": "reference"}]
    assert row["suggested_household_id"] == household.id
    assert row["suggestion_source"] == "reference"
    assert session.exec(select(Payment)).first() is None
