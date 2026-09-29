"""Coverage for the historical-import scripts (issue #145).

`import_meter_history.py` and `calculate_meter_usage.py` open their own
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

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.api.electricity_rates.service import get_effective_rate
from app.db.engine import engine as real_engine
from app.db.models import ElectricityRate, Household, MeterReading
from scripts import calculate_meter_usage
from scripts.import_meter_history import (
    ImportValidationError,
    ParsedRow,
    get_period,
    insert_meter_history,
    main as import_main,
    match_rows,
    parse_csv,
    parse_decimal,
)
from tests.factories import make_electricity_rate, make_household, make_meter_reading

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
    real_session: Session, *, household_ids: list[int], rate_ids: list[int]
) -> None:
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

    def test_empty_cell_raises_naming_row_and_column(self) -> None:
        with pytest.raises(ImportValidationError) as exc_info:
            parse_decimal("", row_num=7, column="night_usage")
        assert exc_info.value.row_num == 7
        assert exc_info.value.column == "night_usage"

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
        csv_path = tmp_path / "December_24.csv"
        csv_path.write_text(
            "1,Petrenko Ivan,100,50,10,5,300\n"
            "2,Sydorenko Olha,abc,60,12,6,320\n",  # row 2, day_meter is malformed
            encoding="utf-8",
        )

        with pytest.raises(ImportValidationError) as exc_info:
            parse_csv(str(csv_path))

        assert exc_info.value.row_num == 2
        assert exc_info.value.column == "day_meter"

    def test_valid_rows_parse_all_fields(self, tmp_path) -> None:
        csv_path = tmp_path / "December_24.csv"
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
        assert get_period(str(tmp_path / "December_24.csv")) == "2024-12"
        assert get_period(str(tmp_path / "January_25.csv")) == "2025-01"


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
            day_usage_kwh="20.00",
            night_usage_kwh="10.00",
            amount_charged_uah="150.00",
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
            assert existing.amount_charged_uah == Decimal("150.00")

            # DEFECT (see report): `result.rowcount` from psycopg for this
            # ON CONFLICT DO NOTHING multi-row insert is always -1, not the
            # real affected-row count, so `insert_meter_history` reports
            # -1 instead of 0 here even though the write behavior above
            # (existing row left untouched) is correct.
            assert inserted == 0
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])

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
            assert stored.amount_charged_uah == Decimal("300.00")

            # DEFECT (see report): same rowcount==-1 issue as above -- the
            # write above is correct (one row landed), but the reported
            # count is -1, not 1.
            assert inserted == 1
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])


# --- main(): end-to-end abort on malformed input, no partial writes -------


class TestMainEndToEnd:
    def test_malformed_cell_aborts_with_nonzero_exit_and_writes_nothing(
        self, tmp_path, monkeypatch, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot C")
        real_session.commit()

        csv_path = tmp_path / "December_24.csv"
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

        csv_path = tmp_path / "December_24.csv"
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


# --- calculate_meter_usage: amount recomputation --------------------------


class TestCalculateMeterUsage:
    def test_amount_charged_reflects_usage_times_effective_rate(
        self, real_session: Session
    ) -> None:
        household = make_household(real_session, name="Plot F")
        real_session.commit()

        make_meter_reading(
            real_session,
            household_id=household.id,
            period="2024-11",
            day_meter_value="1000.00",
            night_meter_value="500.00",
        )
        second = make_meter_reading(
            real_session,
            household_id=household.id,
            period="2024-12",
            day_meter_value="1120.00",  # +120 day usage
            night_meter_value="540.00",  # +40 night usage
            amount_charged_uah="0.00",  # stale/wrong before recalculation
        )
        rate = make_electricity_rate(
            real_session,
            day_rate_uah="4.32",
            night_rate_uah="2.16",
            effective_from="2024-12",
        )
        real_session.commit()

        try:
            exit_code = calculate_meter_usage.main()
            assert exit_code == 0

            real_session.refresh(second)
            assert second.day_usage_kwh == Decimal(
                "120.00"
            ) or second.day_usage_kwh == Decimal("120")
            assert second.night_usage_kwh == Decimal(
                "40.00"
            ) or second.night_usage_kwh == Decimal("40")
            expected_amount = (
                Decimal("120.00") * Decimal("4.32") + Decimal("40.00") * Decimal("2.16")
            ).quantize(Decimal("0.01"))
            assert second.amount_charged_uah == expected_amount
            # sanity: the rate lookup used really is the one seeded for this period
            effective = get_effective_rate(session=real_session, period="2024-12")
            assert effective.id == rate.id
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[rate.id])

    def test_period_with_no_effective_rate_recalculates_usage_but_leaves_charge_and_is_reported_skipped(
        self, real_session: Session, capsys
    ) -> None:
        household = make_household(real_session, name="Plot G")
        real_session.commit()

        make_meter_reading(
            real_session,
            household_id=household.id,
            period="2031-01",
            day_meter_value="2000.00",
            night_meter_value="1000.00",
        )
        second = make_meter_reading(
            real_session,
            household_id=household.id,
            period="2031-02",  # no ElectricityRate covers this far-future period
            day_meter_value="2200.00",  # +200 day usage
            night_meter_value="1080.00",  # +80 night usage
            amount_charged_uah="42.00",  # must be left alone
        )
        real_session.commit()

        try:
            exit_code = calculate_meter_usage.main()
            assert exit_code == 0

            real_session.refresh(second)
            assert second.day_usage_kwh == Decimal(
                "200.00"
            ) or second.day_usage_kwh == Decimal("200")
            assert second.night_usage_kwh == Decimal(
                "80.00"
            ) or second.night_usage_kwh == Decimal("80")
            # the charge is untouched, not zeroed out
            assert second.amount_charged_uah == Decimal("42.00")

            output = capsys.readouterr().out
            assert "2031-02" in output
        finally:
            _cleanup(real_session, household_ids=[household.id], rate_ids=[])
