"""Coverage for the historical-import scripts (issue #145).

`import_meter_history.py` opens its own
`Session(engine)` against the application's configured database rather than
using the test suite's rolled-back-transaction `session` fixture -- so a row
created only in that fixture's transaction would be invisible to them (it
lives on a different Postgres connection/transaction). `conftest.py` points
`app.db.engine.engine` at the same throwaway per-run database the rest of the
suite uses (env vars are set before any `app.*` import), so it *is* safe to
let the scripts read/write through it directly; tests that do so use a
separately-committing session for setup and clean up the rows they create in
a `finally` block, since nothing rolls those back automatically.

Pure parsing/matching logic (`parse_decimal`, `parse_csv`, `match_rows`,
`load_mapping`) touches no database at all and is tested directly.
"""

import unicodedata
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.domain import current_billing_period
from app.db.engine import engine as real_engine
from app.db.models import (
    BillingPeriod,
    ElectricityRate,
    Household,
    HouseholdCharge,
    MeterReading,
)
from scripts.import_meter_history import (
    CsvValidationError,
    ImportValidationError,
    ParsedRow,
    get_period,
    insert_meter_history,
    main as import_main,
    match_rows,
    parse_csv,
    parse_decimal,
)
from tests.factories import make_household, make_meter_reading

pytestmark = pytest.mark.usefixtures("engine")  # ensures schema exists


# --- helpers for tests that go through the script's own real-DB session -------


@pytest.fixture
def real_session():
    """A session bound to the real (throwaway test) database, separate from
    the rolled-back `session` fixture, because the scripts under test open
    their own connection and would never see uncommitted work on another
    one. Tracks nothing automatically -- callers must clean up what they
    commit."""
    with Session(real_engine) as db:
        yield db


def _cleanup(
    real_session: Session,
    *,
    household_ids: list[int],
    rate_ids: list[int],
    periods: list[str] | None = None,
) -> None:
    # household_charges rejects DELETE and TRUNCATE by trigger; only this
    # test's committed charges exist (every other test rolls back), so lift the
    # TRUNCATE guard for this transaction.
    real_session.exec(text("ALTER TABLE household_charges DISABLE TRIGGER household_charges_no_truncate"))  # type: ignore[call-overload]
    real_session.exec(text("TRUNCATE household_charges"))  # type: ignore[call-overload]
    real_session.exec(text("ALTER TABLE household_charges ENABLE TRIGGER household_charges_no_truncate"))  # type: ignore[call-overload]
    for period in periods or []:
        billing_period = real_session.get(BillingPeriod, period)
        if billing_period is not None:
            real_session.delete(billing_period)
    real_session.commit()
    for hid in household_ids:
        for reading in real_session.exec(
            select(MeterReading).where(MeterReading.household_id == hid)
        ).all():
            real_session.delete(reading)
    real_session.commit()
    for hid in household_ids:
        household = real_session.get(Household, hid)
        if household is not None:
            real_session.delete(household)
    for rid in rate_ids:
        rate = real_session.get(ElectricityRate, rid)
        if rate is not None:
            real_session.delete(rate)
    real_session.commit()


# --- parse_decimal --------------------------------------------------------


class TestParseDecimal:
    def test_comma_decimal_separator_parses_to_exact_decimal(self) -> None:
        result = parse_decimal("3205,50", row_num=2, column="day_meter")
        assert result == Decimal("3205.50")
        assert str(result) == "3205.50"

    def test_blank_cell_parses_as_zero(self) -> None:
        assert parse_decimal("", row_num=7, column="night_usage") == Decimal(0)
        assert parse_decimal("  ", row_num=7, column="night_usage") == Decimal(0)

    def test_non_numeric_cell_raises_naming_row_and_column(self) -> None:
        with pytest.raises(ImportValidationError) as exc_info:
            parse_decimal("abc", row_num=4, column="day_meter")
        assert exc_info.value.row_num == 4
        assert exc_info.value.column == "day_meter"


# --- parse_csv: malformed rows abort before any write ---------------------


class TestParseCsv:
    def test_malformed_numeric_cell_raises_naming_exact_row_and_column(
        self, tmp_path
    ) -> None:
        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text(
            "1,Petrenko Ivan,100,50,10,5,300\n"
            "2,Sydorenko Olha,abc,60,12,6,320\n",  # row 2, day_meter is malformed
            encoding="utf-8",
        )

        with pytest.raises(CsvValidationError) as exc_info:
            parse_csv(str(csv_path))

        [error] = exc_info.value.errors
        assert error.row_num == 2
        assert error.column == "day_meter"

    def test_amount_charged_is_rounded_to_two_decimals(self, tmp_path) -> None:
        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text(
            "1,Petrenko Ivan,100,50,10,5,2524.135000000005\n", encoding="utf-8"
        )

        [row] = parse_csv(str(csv_path))

        assert row.amount_charged == Decimal("2524.14")

    def test_valid_rows_parse_all_fields(self, tmp_path) -> None:
        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text("1,Petrenko Ivan,100,50,10,5,300\n", encoding="utf-8")

        rows = parse_csv(str(csv_path))

        assert len(rows) == 1
        assert rows[0] == ParsedRow(
            row_num=1,
            csv_id="1",
            household_name="Petrenko Ivan",
            day_meter=Decimal("100"),
            night_meter=Decimal("50"),
            day_usage=Decimal("10"),
            night_usage=Decimal("5"),
            amount_charged=Decimal("300"),
        )


class TestGetPeriod:
    def test_derives_period_from_filename_across_year_boundary(self, tmp_path) -> None:
        assert get_period(str(tmp_path / "Грудень24.csv")) == "2024-12"
        assert get_period(str(tmp_path / "Січень25.csv")) == "2025-01"

    def test_accepts_decomposed_unicode_filename(self, tmp_path) -> None:
        decomposed = unicodedata.normalize("NFD", "Лютий26.csv")
        assert get_period(str(tmp_path / decomposed)) == "2026-02"

    def test_unrecognised_filename_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="cannot read period"):
            get_period(str(tmp_path / "March_26.csv"))


# --- match_rows: mapping-only, no fuzzy fallback ---------------------------


class TestMatchRows:
    def test_row_with_no_mapping_entry_is_unmatched_even_with_similar_household_names(
        self,
    ) -> None:
        # Two households sharing a surname exist in the "database" (valid ids),
        # and the CSV row's name looks just like one of them -- but its csv_id
        # has no mapping entry, so the deleted fuzzy-matching path must not
        # silently resolve it to either.
        rows = [
            ParsedRow(
                row_num=2,
                csv_id="99",  # not present in mapping
                household_name="Petrenko Ivan",
                day_meter=Decimal("100"),
                night_meter=Decimal("50"),
                day_usage=Decimal("10"),
                night_usage=Decimal("5"),
                amount_charged=Decimal("300"),
            )
        ]
        mapping = {
            "1": 4,
            "2": 5,
        }  # household 4 = "Petrenko Ivan", 5 = "Petrenko Olena"
        valid_household_ids = {4, 5}

        matched, unmatched = match_rows(rows, mapping, valid_household_ids)

        assert matched == []
        assert unmatched == rows

    def test_row_with_mapping_entry_to_nonexistent_household_is_unmatched(self) -> None:
        rows = [
            ParsedRow(
                row_num=2,
                csv_id="1",
                household_name="Petrenko Ivan",
                day_meter=Decimal("100"),
                night_meter=Decimal("50"),
                day_usage=Decimal("10"),
                night_usage=Decimal("5"),
                amount_charged=Decimal("300"),
            )
        ]
        mapping = {"1": 999}  # mapped, but household 999 doesn't exist
        matched, unmatched = match_rows(rows, mapping, valid_household_ids=set())

        assert matched == []
        assert unmatched == rows

    def test_row_with_valid_mapping_entry_matches(self) -> None:
        row = ParsedRow(
            row_num=2,
            csv_id="1",
            household_name="Petrenko Ivan",
            day_meter=Decimal("100"),
            night_meter=Decimal("50"),
            day_usage=Decimal("10"),
            night_usage=Decimal("5"),
            amount_charged=Decimal("300"),
        )
        matched, unmatched = match_rows([row], {"1": 4}, valid_household_ids={4})

        assert matched == [(row, 4)]
        assert unmatched == []


# --- insert_meter_history: never overwrites an existing reading -----------


class TestInsertMeterHistory:
    def test_existing_reading_for_period_is_reported_as_conflict_and_left_unchanged(
        self, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot A")
        real_session.commit()

        existing = make_meter_reading(
            real_session,
            household_id=household.id,
            period="2024-12",
            day_meter_value="500.00",
            night_meter_value="300.00",
        )
        real_session.commit()

        row = ParsedRow(
            row_num=2,
            csv_id="1",
            household_name="Plot A",
            day_meter=Decimal("999.99"),  # would-be overwrite, must not land
            night_meter=Decimal("888.88"),
            day_usage=Decimal("50"),
            night_usage=Decimal("40"),
            amount_charged=Decimal("777.77"),
        )

        try:
            inserted, conflicts = insert_meter_history([(row, household.id)], "2024-12")

            assert conflicts == [(row, household.id)]

            real_session.refresh(existing)
            assert existing.day_meter_value == Decimal("500.00")
            assert existing.night_meter_value == Decimal("300.00")
            assert inserted == 0
            # No new reading, so no charge either.
            assert real_session.exec(select(HouseholdCharge)).all() == []
        finally:
            _cleanup(
                real_session,
                household_ids=[household.id],
                rate_ids=[],
                periods=["2024-12"],
            )

    def test_new_reading_for_unseen_period_is_inserted(
        self, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot B")
        real_session.commit()

        row = ParsedRow(
            row_num=2,
            csv_id="1",
            household_name="Plot B",
            day_meter=Decimal("100.00"),
            night_meter=Decimal("50.00"),
            day_usage=Decimal("10.00"),
            night_usage=Decimal("5.00"),
            amount_charged=Decimal("300.00"),
        )

        try:
            inserted, conflicts = insert_meter_history([(row, household.id)], "2024-11")

            assert conflicts == []

            stored = real_session.exec(
                select(MeterReading).where(
                    MeterReading.household_id == household.id,
                    MeterReading.period == "2024-11",
                )
            ).one()
            assert stored.day_meter_value == Decimal("100.00")
            assert inserted == 1

            # The sheet's exact amount lands in the ledger, not recomputed.
            charge = real_session.exec(select(HouseholdCharge)).one()
            assert charge.reading_id == stored.id
            assert charge.household_id == household.id
            assert charge.total_uah == Decimal("300.00")
            assert charge.tariff_uah == Decimal("300.00")
            assert charge.day_usage_kwh == Decimal("10.00")
            assert charge.night_usage_kwh == Decimal("5.00")
            assert real_session.get(BillingPeriod, "2024-11").status == "closed"
        finally:
            _cleanup(
                real_session,
                household_ids=[household.id],
                rate_ids=[],
                periods=["2024-11"],
            )


# --- main(): end-to-end abort on malformed input, no partial writes -------


class TestMainEndToEnd:
    def test_malformed_cell_aborts_with_nonzero_exit_and_writes_nothing(
        self, tmp_path, monkeypatch, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot C")
        real_session.commit()

        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text(
            "1,Plot C,100,50,10,5,300\n"
            "2,Plot D,abc,60,12,6,320\n",  # malformed day_meter
            encoding="utf-8",
        )
        mapping_path = tmp_path / "mapping.csv"
        mapping_path.write_text(
            f"csv_id,household_id\n1,{household.id}\n2,999999\n", encoding="utf-8"
        )

        monkeypatch.setattr(
            "sys.argv",
            [
                "import_meter_history.py",
                str(csv_path),
                "--mapping",
                str(mapping_path),
                "--apply",
            ],
        )

        try:
            exit_code = import_main()

            assert exit_code != 0

            remaining = real_session.exec(
                select(MeterReading).where(
                    MeterReading.household_id == household.id,
                    MeterReading.period == "2024-12",
                )
            ).all()
            assert remaining == []
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])

    def test_dry_run_without_apply_writes_nothing(
        self, tmp_path, monkeypatch, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot E")
        real_session.commit()

        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text("1,Plot E,100,50,10,5,300\n", encoding="utf-8")
        mapping_path = tmp_path / "mapping.csv"
        mapping_path.write_text(
            f"csv_id,household_id\n1,{household.id}\n", encoding="utf-8"
        )

        monkeypatch.setattr(
            "sys.argv",
            ["import_meter_history.py", str(csv_path), "--mapping", str(mapping_path)],
        )

        try:
            exit_code = import_main()

            assert exit_code == 0

            remaining = real_session.exec(
                select(MeterReading).where(
                    MeterReading.household_id == household.id,
                    MeterReading.period == "2024-12",
                )
            ).all()
            assert remaining == []
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])

    def test_current_period_is_refused_and_writes_nothing(
        self, tmp_path, monkeypatch, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot H")
        real_session.commit()

        current = current_billing_period()
        csv_path = tmp_path / "Грудень24.csv"
        csv_path.write_text("1,Plot H,100,50,10,5,300\n", encoding="utf-8")
        mapping_path = tmp_path / "mapping.csv"
        mapping_path.write_text(
            f"csv_id,household_id\n1,{household.id}\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "scripts.import_meter_history.get_period", lambda _path: current
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "import_meter_history.py",
                str(csv_path),
                "--mapping",
                str(mapping_path),
                "--apply",
            ],
        )

        try:
            assert import_main() != 0
            assert real_session.exec(select(BillingPeriod)).all() == []
            assert real_session.exec(select(MeterReading)).all() == []
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])
