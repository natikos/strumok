"""Bank statement CSV parsing (issue #251). Fixtures are synthetic: real
statements hold residents' personal data and are never used in tests."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.domain.bank_statement import (
    MAX_ROWS,
    BankStatementError,
    parse_statement,
)
from app.db.models import BankStatementFile, BankTransaction

D = Decimal

OWN = "UA000000000000000000000000001"
HEADER = (
    "ЄДРПОУ;МФО;Рахунок;Валюта;Номер документу;Дата операції;МФО банку;"
    "Назва банку;Рахунок кореспондента;ЄДРПОУ кореспондента;Кореспондент;"
    "Сума;Призначення платежу;"
)


def _row(
    doc="100.",
    day="15.05.2025",
    amount="500.00",
    payer_iban="UA111",
    payer="Test Payer",
    purpose="plot 7",
    account=OWN,
    currency="UAH",
) -> str:
    return (
        f"1;305299;{account};{currency};{doc};{day};1;Bank;{payer_iban};2;"
        f"{payer};{amount};{purpose};"
    )


def _csv(*rows: str, encoding="cp1251") -> bytes:
    return ("\n".join([HEADER, *rows]) + "\n").encode(encoding)


class TestParseStatement:
    @pytest.mark.parametrize("encoding", ["cp1251", "utf-8"])
    def test_reads_both_encodings(self, encoding: str) -> None:
        result = parse_statement(_csv(_row(payer="Іван Петренко"), encoding=encoding))

        assert result.encoding == ("utf-8" if encoding == "utf-8" else "cp1251")
        assert result.credits[0].payer_name == "Іван Петренко"

    def test_space_thousands_separator_parses_to_decimal(self) -> None:
        result = parse_statement(_csv(_row(amount="3 620.00")))

        assert result.credits[0].amount_uah == D("3620.00")

    def test_non_breaking_space_separator(self) -> None:
        result = parse_statement(_csv(_row(amount="1 234.50")))

        assert result.credits[0].amount_uah == D("1234.50")

    def test_debits_are_dropped_and_counted(self) -> None:
        result = parse_statement(
            _csv(_row(doc="1."), _row(doc="2.", amount="-9 999.00"))
        )

        assert [c.document_number for c in result.credits] == ["1."]
        assert result.debits_skipped == 1
        assert result.rows_total == 2

    def test_reports_the_date_range_over_all_rows(self) -> None:
        result = parse_statement(
            _csv(
                _row(doc="1.", day="03.05.2025"),
                _row(doc="2.", day="20.05.2025", amount="-1.00"),
            )
        )

        assert result.first_operation_date == date(2025, 5, 3)
        assert result.last_operation_date == date(2025, 5, 20)

    def test_document_number_is_kept_verbatim_apart_from_whitespace(self) -> None:
        result = parse_statement(_csv(_row(doc=" @123. ")))

        assert result.credits[0].document_number == "@123."

    def test_header_is_matched_by_name_not_position(self) -> None:
        columns = HEADER.rstrip(";").split(";")
        order = list(reversed(range(len(columns))))
        header = ";".join(columns[i] for i in order)
        fields = _row().rstrip(";").split(";")
        body = ";".join(fields[i] for i in order)

        result = parse_statement((header + "\n" + body + "\n").encode("cp1251"))

        assert result.credits[0].amount_uah == D("500.00")

    def test_blank_lines_are_ignored(self) -> None:
        result = parse_statement(_csv(_row(), "", ";;;"))

        assert len(result.credits) == 1


class TestRejections:
    def test_wrong_account_is_refused(self) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(_row()), expected_iban="UA999")

        assert err.value.code == "bankStatementWrongAccount"

    def test_matching_account_is_accepted(self) -> None:
        assert parse_statement(_csv(_row()), expected_iban=OWN).account_iban == OWN

    @pytest.mark.parametrize(
        "amount", ["abc", "12", "12.5", "1,000.00", "1 2.00.00", ""]
    )
    def test_bad_amount_names_row_and_column_only(self, amount: str) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(_row(), _row(amount=amount)))

        assert (err.value.code, err.value.row, err.value.column) == (
            "bankStatementInvalid",
            3,
            "Сума",
        )
        assert amount not in str(err.value) or amount == ""

    def test_zero_amount_is_invalid(self) -> None:
        with pytest.raises(BankStatementError):
            parse_statement(_csv(_row(amount="0.00")))

    @pytest.mark.parametrize("day", ["2025-05-15", "31.02.2025", "", "15.05.2999"])
    def test_bad_or_future_date_is_invalid(self, day: str) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(_row(day=day)))

        assert err.value.column == "Дата операції"

    def test_non_uah_currency_is_invalid(self) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(_row(currency="USD")))

        assert err.value.column == "Валюта"

    def test_credit_without_document_number_is_invalid(self) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(_row(doc="")))

        assert err.value.column == "Номер документу"

    def test_missing_column_is_invalid(self) -> None:
        with pytest.raises(BankStatementError) as err:
            parse_statement(HEADER.replace("Сума;", "").encode("cp1251"))

        assert err.value.column == "Сума"

    def test_mixed_accounts_in_one_file_are_invalid(self) -> None:
        with pytest.raises(BankStatementError):
            parse_statement(_csv(_row(), _row(account="UA222")))

    def test_empty_and_header_only_files_are_invalid(self) -> None:
        for data in (b"", _csv()):
            with pytest.raises(BankStatementError):
                parse_statement(data)

    def test_undecodable_bytes_are_invalid(self) -> None:
        # 0x98 is unassigned in cp1251 and is not valid UTF-8.
        with pytest.raises(BankStatementError):
            parse_statement(HEADER.encode("cp1251") + b"\n\x98\xff\n")

    def test_too_many_rows_is_refused(self) -> None:
        rows = [_row(doc=f"{i}.") for i in range(MAX_ROWS + 1)]

        with pytest.raises(BankStatementError) as err:
            parse_statement(_csv(*rows))

        assert err.value.code == "bankStatementTooManyRows"


def _file(
    session: Session,
    sha: str = "a" * 64,
    covered_through: date = date(2025, 5, 15),
) -> BankStatementFile:
    file = BankStatementFile(
        sha256=sha,
        original_filename="s.csv",
        encoding="cp1251",
        account_iban=OWN,
        first_operation_date=date(2025, 5, 1),
        last_operation_date=date(2025, 5, 15),
        covered_through=covered_through,
        rows_total=1,
        credits_new=1,
        credits_duplicate=0,
        debits_skipped=0,
    )
    session.add(file)
    session.commit()
    return file


def _transaction(
    session: Session,
    file_id: int,
    document_number: str = "1.",
    amount_uah: Decimal = D("10.00"),
) -> BankTransaction:
    row = BankTransaction(
        document_number=document_number,
        operation_date=date(2025, 5, 15),
        amount_uah=amount_uah,
        payer_iban="UA111",
        first_file_id=file_id,
    )
    session.add(row)
    session.commit()
    return row


class TestImportTables:
    def test_same_file_hash_cannot_be_stored_twice(self, session: Session) -> None:
        _file(session)

        with pytest.raises(IntegrityError):
            _file(session)
        session.rollback()

    def test_coverage_cannot_end_before_the_last_operation(
        self, session: Session
    ) -> None:
        with pytest.raises(IntegrityError):
            _file(session, covered_through=date(2025, 5, 14))
        session.rollback()

    def test_overlapping_row_is_rejected_by_the_dedupe_key(
        self, session: Session
    ) -> None:
        file = _file(session)
        _transaction(session, file.id)

        with pytest.raises(IntegrityError):
            _transaction(session, file.id)
        session.rollback()

    def test_differing_document_number_is_a_separate_payment(
        self, session: Session
    ) -> None:
        file = _file(session)
        _transaction(session, file.id, document_number="1.")

        _transaction(session, file.id, document_number="2.")

    def test_non_positive_amount_is_rejected(self, session: Session) -> None:
        file = _file(session)

        with pytest.raises(IntegrityError):
            _transaction(session, file.id, amount_uah=D("0.00"))
        session.rollback()
