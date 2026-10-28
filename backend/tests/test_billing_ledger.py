"""Billing ledger: the pure statement function, the
append-only charges table and the statements endpoint."""

import random
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session

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


class TestLossAllocation:
    def _inputs(self, usages: list[tuple[str, str]]) -> list[ChargeInput]:
        return [
            ChargeInput(
                household_id=i,
                owner_user_id=None,
                reading_id=None,
                day_usage_kwh=D(day),
                night_usage_kwh=D(night),
            )
            for i, (day, night) in enumerate(usages, start=1)
        ]

    def test_shares_always_add_up_to_the_bill_exactly(self) -> None:
        from app.core.domain import reconcile_period

        rng = random.Random(42)
        for _ in range(500):
            usages = [
                (
                    f"{rng.randint(0, 800)}.{rng.randint(0, 99):02d}",
                    f"{rng.randint(0, 800)}.{rng.randint(0, 99):02d}",
                )
                for _ in range(rng.randint(1, 10))
            ]
            # Bills below the tariff sum exercise a negative loss.
            bill = D(f"{rng.randint(0, 9000)}.{rng.randint(0, 99):02d}")

            result = reconcile_period(
                self._inputs(usages),
                day_rate_uah=D("4.32"),
                night_rate_uah=D("2.16"),
                bill_total_uah=bill,
            )

            assert sum(line.total_uah for line in result.lines) == bill
            assert all(
                line.loss_share_uah == line.loss_share_uah.quantize(D("0.01"))
                for line in result.lines
            )

    def test_split_is_pro_rata_by_usage(self) -> None:
        from app.core.domain import reconcile_period

        result = reconcile_period(
            self._inputs([("100", "0"), ("300", "0")]),
            day_rate_uah=D("1"),
            night_rate_uah=D("1"),
            bill_total_uah=D("500.00"),  # tariff 400 + loss 100
        )

        assert [line.loss_share_uah for line in result.lines] == [
            D("25.00"),
            D("75.00"),
        ]
        assert result.loss_uah == D("100.00")

    def test_negative_loss_reduces_every_share(self) -> None:
        from app.core.domain import reconcile_period

        result = reconcile_period(
            self._inputs([("100", "0"), ("100", "0")]),
            day_rate_uah=D("1"),
            night_rate_uah=D("1"),
            bill_total_uah=D("190.00"),
        )

        assert result.loss_uah == D("-10.00")
        assert [line.total_uah for line in result.lines] == [D("95.00"), D("95.00")]

    def test_remainder_kopeck_goes_to_the_lowest_id_on_a_tie_and_is_reported(
        self,
    ) -> None:
        from app.core.domain import reconcile_period

        result = reconcile_period(
            self._inputs([("1", "0"), ("1", "0"), ("1", "0")]),
            day_rate_uah=D("0"),
            night_rate_uah=D("0"),
            bill_total_uah=D("0.10"),
        )

        assert [line.loss_share_uah for line in result.lines] == [
            D("0.04"),
            D("0.03"),
            D("0.03"),
        ]
        assert result.remainder_household_ids == [1]

    def test_zero_usage_everywhere_splits_equally_and_single_household_takes_all(
        self,
    ) -> None:
        from app.core.domain import reconcile_period

        zero = reconcile_period(
            self._inputs([("0", "0"), ("0", "0")]),
            day_rate_uah=D("1"),
            night_rate_uah=D("1"),
            bill_total_uah=D("10.00"),
        )
        single = reconcile_period(
            self._inputs([("5", "5")]),
            day_rate_uah=D("1"),
            night_rate_uah=D("1"),
            bill_total_uah=D("33.33"),
        )

        assert [line.total_uah for line in zero.lines] == [D("5.00"), D("5.00")]
        assert single.lines[0].total_uah == D("33.33")

    def test_without_a_bill_it_is_tariff_only(self) -> None:
        from app.core.domain import reconcile_period

        result = reconcile_period(
            self._inputs([("10", "0")]), day_rate_uah=D("2"), night_rate_uah=D("1")
        )

        assert result.loss_uah is None
        assert result.lines[0].total_uah == D("20.00")
