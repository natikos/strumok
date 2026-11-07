"""Balance cutovers: a later sheet balance that supersedes the opening balance."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.api.billing.payments import get_balance
from app.db.models import (
    AuditLog,
    BalanceCutover,
    BillingPeriod,
    HouseholdCharge,
    OpeningBalance,
    OpeningBalanceCorrection,
    Payment,
)
from scripts import set_balance_cutover
from tests.factories import make_household, make_user
from tests.test_bank_review import _admin, _confirm, _tx

D = Decimal
T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _charge(session, household_id, period, total, owner_id=None) -> None:
    if session.get(BillingPeriod, period) is None:
        session.add(BillingPeriod(period=period, status="closed"))
        session.flush()
    session.add(
        HouseholdCharge(
            period=period,
            household_id=household_id,
            owner_user_id=owner_id,
            day_usage_kwh=D("0"),
            night_usage_kwh=D("0"),
            tariff_uah=D(total),
            total_uah=D(total),
        )
    )
    session.flush()


def _pay(session, household_id, amount, paid_on, owner_id=None) -> None:
    session.add(
        Payment(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            paid_on=paid_on,
            method="cash",
        )
    )
    session.flush()


def _opening(session, household_id, amount, as_of, owner_id=None) -> None:
    session.add(
        OpeningBalance(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            as_of=as_of,
        )
    )
    session.flush()


def _cutover(session, household_id, amount, as_of, owner_id=None, created=T0) -> None:
    session.add(
        BalanceCutover(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            as_of=as_of,
            created_at=created,
        )
    )
    session.flush()


def _correction(session, household_id, amount, created, owner_id=None) -> None:
    session.add(
        OpeningBalanceCorrection(
            household_id=household_id,
            owner_user_id=owner_id,
            amount_uah=D(amount),
            reason="r",
            created_at=created,
        )
    )
    session.flush()


def _backfilled(session, household_id, owner_id=None) -> None:
    for month in ("2025-01", "2025-02", "2025-03", "2025-04", "2025-05"):
        _charge(session, household_id, month, "100.10", owner_id)


def test_without_a_cutover_everything_since_the_opening_balance_counts(
    session: Session,
) -> None:
    household = make_household(session)
    _opening(session, household.id, "100.05", date(2024, 12, 31))
    _backfilled(session, household.id)
    _pay(session, household.id, "10.01", date(2025, 2, 1))

    balance = get_balance(session=session, household_id=household.id)

    assert len(balance.periods) == 5
    assert balance.total_due_uah == D("600.55")
    assert balance.balance_uah == D("590.54")


def test_cutover_drops_settled_months_and_payments_and_keeps_later_ones_payable(
    session: Session,
) -> None:
    household = make_household(session)
    _opening(session, household.id, "100.05", date(2024, 12, 31))
    _backfilled(session, household.id)
    _pay(session, household.id, "999.00", date(2025, 2, 10))
    _pay(session, household.id, "50.00", date(2025, 3, 31))  # on as_of: inside it
    _pay(session, household.id, "60.05", date(2025, 4, 1))  # day after: counts
    _cutover(session, household.id, "250.35", date(2025, 3, 31))

    balance = get_balance(session=session, household_id=household.id)

    assert [p.period for p in balance.periods] == ["2025-04", "2025-05"]
    assert balance.unpaid_months == 2  # 60.05 only dents the carried-over 250.35
    assert balance.total_due_uah == D("450.55")  # 250.35 + 2 * 100.10
    assert balance.total_paid_uah == D("60.05")
    assert balance.balance_uah == D("390.50")


def test_payment_after_a_cutover_settles_carried_debt_then_oldest_later_month(
    session: Session,
) -> None:
    household = make_household(session)
    _backfilled(session, household.id)
    _cutover(session, household.id, "250.35", date(2025, 3, 31))
    _pay(session, household.id, "300.35", date(2025, 4, 15))

    balance = get_balance(session=session, household_id=household.id)

    assert [(p.period, p.status) for p in balance.periods] == [
        ("2025-04", "partial"),
        ("2025-05", "unpaid"),
    ]
    assert balance.balance_uah == D("150.20")


def test_cutover_covers_a_month_only_when_it_ends_on_or_before_as_of(
    session: Session,
) -> None:
    household = make_household(session)
    _backfilled(session, household.id)
    _cutover(session, household.id, "0.00", date(2025, 3, 30))  # March not over yet

    balance = get_balance(session=session, household_id=household.id)

    assert [p.period for p in balance.periods] == ["2025-03", "2025-04", "2025-05"]


def test_latest_as_of_wins_over_an_older_cutover_even_if_written_earlier(
    session: Session,
) -> None:
    household = make_household(session)
    _backfilled(session, household.id)
    _cutover(session, household.id, "999.00", date(2025, 2, 28), created=T0)
    _cutover(
        session,
        household.id,
        "10.00",
        date(2025, 4, 30),
        created=T0 - timedelta(days=9),
    )

    balance = get_balance(session=session, household_id=household.id)

    assert [p.period for p in balance.periods] == ["2025-05"]
    assert balance.balance_uah == D("110.10")


def test_corrections_before_the_cutover_are_ignored_and_later_ones_apply(
    session: Session,
) -> None:
    household = make_household(session)
    _opening(session, household.id, "100.00", date(2024, 12, 31))
    _correction(session, household.id, "77.77", T0 - timedelta(days=1))
    _cutover(session, household.id, "50.00", date(2025, 3, 31), created=T0)
    _correction(session, household.id, "-5.25", T0 + timedelta(days=1))

    balance = get_balance(session=session, household_id=household.id)

    assert balance.balance_uah == D("44.75")  # 50.00 cutover - 5.25 later fix


def test_previous_owner_with_charges_before_the_cutover_owes_only_their_carried_amount(
    session: Session,
) -> None:
    old, new = make_user(session), make_user(session)
    household = make_household(session, user_id=new.id)
    for month in ("2025-01", "2025-02", "2025-03"):
        _charge(session, household.id, month, "100.10", owner_id=old.id)
    _charge(session, household.id, "2025-04", "40.00", owner_id=new.id)
    _pay(session, household.id, "5.00", date(2025, 4, 20), owner_id=old.id)
    _cutover(session, household.id, "70.00", date(2025, 3, 31), owner_id=old.id)

    old_balance = get_balance(
        session=session, household_id=household.id, owner_user_id=old.id
    )
    new_balance = get_balance(
        session=session, household_id=household.id, owner_user_id=new.id
    )

    assert old_balance.periods == []
    assert old_balance.balance_uah == D("65.00")
    assert [p.period for p in new_balance.periods] == ["2025-04"]
    assert new_balance.balance_uah == D("40.00")


def test_bank_credit_on_or_before_the_cutover_date_is_rejected_and_next_day_accepted(
    client, session: Session
) -> None:
    _admin(client, session)
    household = make_household(session)
    _opening(session, household.id, "10.00", date(2025, 1, 31))
    _cutover(session, household.id, "10.00", date(2025, 5, 31))
    on_date = _tx(session, day=date(2025, 5, 31))
    next_day = _tx(session, day=date(2025, 6, 1))

    rejected = _confirm(client, on_date, (household.id, "500.00"))
    accepted = _confirm(client, next_day, (household.id, "500.00"))

    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "beforeOpeningBalance"
    assert accepted.status_code == 200


class TestSetBalanceCutoverScript:
    @pytest.fixture
    def run(self, session: Session, monkeypatch, tmp_path, capsys):
        session.commit()

        class Shared:
            def __init__(self, _engine) -> None:
                pass

            def __enter__(self):
                return session

            def __exit__(self, *_exc) -> None:
                return None

        monkeypatch.setattr(set_balance_cutover, "Session", Shared)

        def go(rows: dict[int, str], *flags: str) -> str:
            csv_file = tmp_path / "b.csv"
            csv_file.write_text(
                "csv_id,balance\n" + "".join(f"{k},{v}\n" for k, v in rows.items()),
                encoding="utf-8",
            )
            mapping = tmp_path / "m.csv"
            mapping.write_text(
                "csv_id,household_id\n" + "".join(f"{k},{k}\n" for k in rows),
                encoding="utf-8",
            )
            monkeypatch.setattr(
                "sys.argv",
                [
                    "x",
                    str(csv_file),
                    "--mapping",
                    str(mapping),
                    "--as-of",
                    "2025-09-30",
                    *flags,
                ],
            )
            assert set_balance_cutover.main() == 0
            return capsys.readouterr().out

        return go

    def test_dry_run_writes_nothing(self, session: Session, run) -> None:
        household = make_household(session)

        out = run({household.id: "-120.50"})

        assert "Dry run: 1" in out
        assert session.exec(select(BalanceCutover)).all() == []
        assert session.exec(select(AuditLog)).all() == []

    def test_apply_writes_cutover_with_flipped_sign_and_skips_already_settled(
        self, session: Session, run
    ) -> None:
        owner = make_user(session)
        fresh = make_household(session, user_id=owner.id)
        settled_by_opening = make_household(session)
        settled_by_cutover = make_household(session)
        _opening(session, settled_by_opening.id, "1.00", date(2025, 9, 30))
        _cutover(session, settled_by_cutover.id, "1.00", date(2025, 10, 31))
        session.commit()

        run(
            {
                fresh.id: "-120.50",
                settled_by_opening.id: "0",
                settled_by_cutover.id: "0",
            },
            "--apply",
        )

        rows = session.exec(select(BalanceCutover)).all()
        by_house = {r.household_id: r for r in rows}
        assert set(by_house) == {fresh.id, settled_by_cutover.id}
        assert by_house[fresh.id].amount_uah == D("120.50")  # owes, sheet sign flipped
        assert by_house[fresh.id].as_of == date(2025, 9, 30)
        assert by_house[fresh.id].owner_user_id == owner.id
        actions = session.exec(
            select(AuditLog.action).where(AuditLog.household_id == fresh.id)
        ).all()
        assert actions == ["balanceCutoverSet"]
