from app.api.bank.matching.matcher import household_reference, match
from app.db.models import Household


def _h(id: int, name: str, active: bool = True) -> Household:
    return Household(id=id, name=name, is_active=active)


HOUSEHOLDS = [_h(1, "Іваненко"), _h(2, "Петренко Олег"), _h(3, "Шевчук", False)]


def test_reference_in_purpose():
    found = match(f"Електроенергія {household_reference(2)}", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(2, "reference")]


def test_split_references_in_order_without_duplicates():
    found = match("STR-2, str 1 та STR-2", HOUSEHOLDS)
    assert [s.household_id for s in found] == [2, 1]


def test_unknown_or_inactive_reference_is_unmatched():
    assert match("STR-99 STR-3", HOUSEHOLDS) == []


def test_reference_is_not_a_substring_match():
    assert match("MYSTR-1", HOUSEHOLDS) == []


def test_surname_in_purpose_suggests_by_name():
    found = match("за світло Іваненко", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(1, "name")]


def test_name_match_tolerates_latin_i_and_declension():
    found = match("Свiтло, Iваненка", HOUSEHOLDS)
    assert [s.household_id for s in found] == [1]


def test_purpose_outranks_payer_name():
    found = match("Свiтло Петренко", HOUSEHOLDS, payer_name="ІВАНЕНКО ІГОР")
    assert [s.household_id for s in found] == [2]


def test_payer_name_used_when_purpose_has_none():
    found = match("оплата", HOUSEHOLDS, payer_name="Іваненко Ігор")
    assert [s.household_id for s in found] == [1]


def test_ambiguous_name_suggests_nothing():
    twins = [_h(1, "Коваль"), _h(2, "Коваль Іван")]
    assert match("Коваль", twins) == []


def test_reference_beats_name():
    found = match("Іваненко STR-2", HOUSEHOLDS)
    assert [(s.household_id, s.source) for s in found] == [(2, "reference")]


def test_unmatched():
    assert match("оплата", HOUSEHOLDS) == []


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


PLOTS = [
    _h(1, "Мельник А. Д."),
    _h(2, "Мельник В.Д."),
    _h(3, "Бук Н."),
    _h(4, "Гончаренко І.(1)"),
    _h(5, "Гончаренко І.(2)"),
    _h(6, "Савчук (Гончаренко)"),
    _h(7, "Кравець (колишній Гончаренко)"),
    _h(8, "Дубенко(Бондар, Гончаренко)"),
    _h(9, "Дуб І. Ф."),
]


def _ids(purpose: str, payer: str = "") -> list[int]:
    return [s.household_id for s in match(purpose, PLOTS, payer)]


def test_short_surname_matches():
    assert _ids("Бук Наталя", "Сидоренко Iрина Андрiївна") == [3]


def test_initial_tells_same_surname_plots_apart():
    assert _ids("Свiтло. Мельник Андрій. Квiтень 2026") == [1]


def test_shared_surname_with_same_initial_is_ambiguous():
    assert _ids("Гончаренко I.Б, оплата за квiтень") == []


def test_bracketed_names_are_only_aliases():
    assert _ids("Сплата, Кравець Олег Петрович") == [7]
    assert _ids("Дубенко Ю.В, оплата") == [8]


def test_alias_used_when_no_plot_has_that_surname():
    assert _ids("Свiтло Бондар") == [8]


def test_short_surname_is_not_a_prefix_of_another_word():
    assert _ids("Дубль про оплату") == []
    assert _ids("Свiтло Дубу I.") == [9]


def test_ordinary_purpose_words_do_not_pick_between_same_surname_plots():
    plots = [_h(1, "Мельник О."), _h(2, "Мельник Б.")]
    assert [s.household_id for s in match("Мельник оплата за е/е", plots)] == []
    assert [s.household_id for s in match("Мельник Б.Д. за світло", plots)] == [2]
    assert [s.household_id for s in match("Iгор. Мельник", [_h(1, "Мельник І.")])] == [
        1
    ]


def test_longer_surname_with_same_stem_is_suggested_when_only_one_is_a_plot():
    """Known limit of stem matching: Ковальчук's payment suggests Коваль. The
    admin confirms every name suggestion, so this is only a hint."""
    assert [s.household_id for s in match("Свiтло Ковальчук", [_h(1, "Коваль")])] == [1]
