"""Billing ledger: the pure statement function, the history backfill, the
append-only charges table and the statements endpoint."""

import importlib.util
import random
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, select

from app.core.domain import (
    ChargeInput,
    compute_period_statement,
    current_billing_period,
    derive_usage,
    money,
    previous_period,
)
from app.db.models import BillingPeriod, HouseholdCharge
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal


class TestDeriveUsage:
    def test_first_reading_is_a_baseline(self) -> None:
        assert derive_usage(None, D("1500")) == D("0")

    def test_difference_between_consecutive_readings(self) -> None:
        assert derive_usage(D("1500"), D("1620.5")) == D("120.5")

    def test_meter_decrease_counts_as_zero(self) -> None:
        assert derive_usage(D("1500"), D("20")) == D("0")


class TestMoney:
    def test_rounds_half_up_so_a_calculator_agrees(self) -> None:
        assert money(D("0.125")) == D("0.13")
        assert money(D("0.135")) == D("0.14")
        assert money(D("2.675")) == D("2.68")


class TestComputePeriodStatement:
    def _line(self, household_id: int, day: str, night: str) -> ChargeInput:
        return ChargeInput(
            household_id=household_id,
            owner_user_id=None,
            reading_id=None,
            day_usage_kwh=D(day),
            night_usage_kwh=D(night),
        )

    def test_tariff_is_usage_times_rate_and_total_equals_tariff(self) -> None:
        (line,) = compute_period_statement(
            [self._line(1, "100", "50")],
            day_rate_uah=D("4.32"),
            night_rate_uah=D("2.16"),
        )

        assert line.tariff_uah == D("540.00")
        assert line.total_uah == line.tariff_uah
        assert line.loss_share_uah == D("0.00")

    def test_zero_usage_household_is_charged_nothing(self) -> None:
        (line,) = compute_period_statement(
            [self._line(1, "0", "0")], day_rate_uah=D("4.32"), night_rate_uah=D("2.16")
        )
        assert line.total_uah == D("0.00")

    def test_lines_are_ordered_by_household_and_deterministic(self) -> None:
        rng = random.Random(1)
        inputs = [
            self._line(i, str(rng.randint(0, 900)), str(rng.randint(0, 900)))
            for i in range(1, 30)
        ]
        shuffled = rng.sample(inputs, len(inputs))
        args = {"day_rate_uah": D("4.32"), "night_rate_uah": D("2.16")}

        first = compute_period_statement(inputs, **args)
        second = compute_period_statement(shuffled, **args)

        assert first == second
        assert [line.household_id for line in first] == sorted(
            line.household_id for line in first
        )

    def test_every_amount_is_a_whole_kopeck_for_arbitrary_inputs(self) -> None:
        rng = random.Random(7)
        for _ in range(200):
            inputs = [
                self._line(
                    i,
                    f"{rng.randint(0, 5000)}.{rng.randint(0, 99):02d}",
                    f"{rng.randint(0, 5000)}.{rng.randint(0, 99):02d}",
                )
                for i in range(1, rng.randint(1, 8))
            ]
            for line in compute_period_statement(
                inputs,
                day_rate_uah=D(f"{rng.randint(1, 9)}.{rng.randint(0, 9999):04d}"),
                night_rate_uah=D(f"{rng.randint(1, 9)}.{rng.randint(0, 9999):04d}"),
            ):
                assert line.total_uah == line.total_uah.quantize(D("0.01"))
                assert line.total_uah >= 0


def _load_migration():
    path = Path(__file__).parent.parent / "alembic/versions/0004_billing_ledger.py"
    spec = importlib.util.spec_from_file_location("migration_0004", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHistoryBackfill:
    def test_closed_history_sums_match_and_open_period_is_left_alone(
        self, session: Session
    ) -> None:
        make_electricity_rate(session, effective_from="2000-01")
        a = make_household(session, name="A", user_id=make_user(session).id)
        b = make_household(session, name="B")
        for household, period, amount in (
            (a, "2026-03", "100.10"),
            (a, "2026-04", "200.20"),
            (b, "2026-04", "50.05"),
            (a, "2026-05", "999.00"),  # not before the cutoff
        ):
            make_meter_reading(
                session,
                household_id=household.id,
                period=period,
                day_usage_kwh="10",
                amount_charged_uah=amount,
            )

        _load_migration().backfill_closed_history(
            session.connection(), before_period="2026-05"
        )

        charges = session.exec(select(HouseholdCharge)).all()
        assert sum(c.total_uah for c in charges) == D("350.35")
        assert {c.period for c in charges} == {"2026-03", "2026-04"}
        assert all(c.tariff_uah == c.total_uah for c in charges)
        periods = {p.period: p.status for p in session.exec(select(BillingPeriod))}
        assert periods == {"2026-03": "closed", "2026-04": "closed"}
        owned = next(c for c in charges if c.household_id == a.id)
        assert owned.owner_user_id == a.user_id

    def test_rerunning_does_not_duplicate(self, session: Session) -> None:
        make_electricity_rate(session)
        household = make_household(session)
        make_meter_reading(
            session, household_id=household.id, period="2026-03", amount_charged_uah="5"
        )
        migration = _load_migration()

        migration.backfill_closed_history(session.connection(), before_period="2026-05")
        migration.backfill_closed_history(session.connection(), before_period="2026-05")

        assert len(session.exec(select(HouseholdCharge)).all()) == 1


class TestChargesAreAppendOnly:
    @pytest.mark.parametrize(
        "statement",
        ["UPDATE household_charges SET total_uah = 1", "DELETE FROM household_charges"],
    )
    def test_update_and_delete_fail_in_the_database(
        self, session: Session, statement: str
    ) -> None:
        household = make_household(session)
        session.add(BillingPeriod(period="2026-03", status="closed"))
        session.flush()
        session.add(
            HouseholdCharge(
                period="2026-03",
                household_id=household.id,
                day_usage_kwh=D("0"),
                night_usage_kwh=D("0"),
                tariff_uah=D("1"),
                total_uah=D("1"),
            )
        )
        session.flush()

        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(statement))


class TestStatementsEndpoint:
    def test_returns_closed_charges_and_a_provisional_current_line(
        self, client, session: Session
    ) -> None:
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        make_electricity_rate(session, day_rate_uah="2", night_rate_uah="1")
        current = current_billing_period()
        before = previous_period(current)
        session.add(BillingPeriod(period=before, status="closed"))
        session.flush()
        session.add(
            HouseholdCharge(
                period=before,
                household_id=household.id,
                day_usage_kwh=D("5"),
                night_usage_kwh=D("0"),
                tariff_uah=D("10"),
                total_uah=D("10"),
            )
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period=before,
            day_meter_value="100",
            night_meter_value="50",
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period=current,
            day_meter_value="130",
            night_meter_value="60",
        )
        authenticate(client, user)

        body = client.get("/billing/statements").json()

        assert [(row["period"], row["status"]) for row in body] == [
            (current, "provisional"),
            (before, "closed"),
        ]
        assert body[0]["total_uah"] == "70.00"  # 30 kWh × 2 + 10 kWh × 1
        assert body[1]["total_uah"] == "10.00"

    def test_is_scoped_to_the_callers_household(self, client, session: Session) -> None:
        mine = make_user(session)
        other_household = make_household(session, user_id=make_user(session).id)
        make_household(session, user_id=mine.id)
        authenticate(client, mine)

        response = client.get(f"/billing/statements?household_id={other_household.id}")

        assert response.status_code == 403

    def test_requires_authentication(self, client) -> None:
        assert client.get("/billing/statements").status_code == 401
