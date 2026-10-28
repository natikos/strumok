"""Households that miss the window are estimated at close and pay a late fee,
which is handed back to the households that did submit."""

import random
from decimal import Decimal

from sqlmodel import Session, select

from app.core.domain import ChargeInput, derive_usage, reconcile_period
from app.db.models import HouseholdCharge, MeterReading
from tests.factories import (
    authenticate,
    make_electricity_rate,
    make_household,
    make_meter_reading,
    make_user,
)

D = Decimal
BODY = {"confirm": True, "acknowledge_flags": False}


def _bill(client, period: str, total: str) -> None:
    response = client.put(
        f"/admin/periods/{period}/bill",
        json={"day_kwh": "1", "night_kwh": "1", "total_uah": total, "confirm": True},
    )
    assert response.status_code == 200, response.text


def _close(client, period: str):
    return client.post(f"/admin/periods/{period}/close", json=BODY)


class TestDeriveUsageAfterAnEstimate:
    def test_a_lower_real_reading_is_a_negative_true_up_not_zero(self) -> None:
        assert derive_usage(D("200"), D("180"), previous_is_estimate=True) == D("-20")
        assert derive_usage(D("200"), D("180")) == D("0")


class TestPenaltyInTheDomain:
    def _inputs(self, rng: random.Random):
        count = rng.randint(2, 9)
        inputs = []
        for i in range(1, count + 1):
            inputs.append(
                ChargeInput(
                    household_id=i,
                    owner_user_id=None,
                    reading_id=None,
                    day_usage_kwh=D(f"{rng.randint(0, 600)}.{rng.randint(0, 99):02d}"),
                    night_usage_kwh=D(
                        f"{rng.randint(0, 600)}.{rng.randint(0, 99):02d}"
                    ),
                    is_estimated=rng.random() < 0.3 and i != 1,
                )
            )
        return inputs

    def test_charges_still_add_up_to_the_bill_with_estimates_in_the_mix(self) -> None:
        rng = random.Random(11)
        for _ in range(400):
            inputs = self._inputs(rng)
            bill = D(f"{rng.randint(0, 9000)}.{rng.randint(0, 99):02d}")

            result = reconcile_period(
                inputs,
                day_rate_uah=D("4.32"),
                night_rate_uah=D("2.16"),
                bill_total_uah=bill,
            )

            assert sum(line.total_uah for line in result.lines) == bill

    def test_the_penalty_is_30_percent_of_the_estimated_tariff_only(self) -> None:
        inputs = [
            ChargeInput(1, None, None, D("100"), D("0")),
            ChargeInput(2, None, None, D("100"), D("0"), is_estimated=True),
        ]

        result = reconcile_period(
            inputs,
            day_rate_uah=D("2"),
            night_rate_uah=D("1"),
            bill_total_uah=D("500.00"),
        )

        on_time, estimated = result.lines
        assert estimated.penalty_uah == D(
            "60.00"
        )  # 30% of the 200 tariff, not the loss share
        assert on_time.penalty_uah == D("0.00")
        assert on_time.penalty_credit_uah == D("60.00")
        assert (
            estimated.total_uah - estimated.tariff_uah - estimated.loss_share_uah
            == D("60.00")
        )


def _setup(client, session: Session):
    authenticate(client, make_user(session, is_admin=True))
    make_electricity_rate(session, day_rate_uah="2", night_rate_uah="0")
    regular = make_household(session, name="Regular", user_id=make_user(session).id)
    sleeper = make_household(session, name="Sleeper", user_id=make_user(session).id)
    for household, values in ((regular, ("0", "100")), (sleeper, ("0", "50"))):
        make_meter_reading(
            session,
            household_id=household.id,
            period="2024-01",
            day_meter_value=values[0],
        )
        make_meter_reading(
            session,
            household_id=household.id,
            period="2024-02",
            day_meter_value=values[1],
        )
    return regular, sleeper


class TestEstimatesAtClose:
    def test_a_missing_household_is_estimated_penalised_and_the_fee_is_credited(
        self, client, session: Session
    ) -> None:
        regular, sleeper = _setup(client, session)
        # March: only `regular` submits (150 -> 50 kWh); sleeper's last real usage was 50.
        make_meter_reading(
            session, household_id=regular.id, period="2024-03", day_meter_value="150"
        )
        _bill(client, "2024-03", "200.00")

        assert _close(client, "2024-03").status_code == 200

        estimate = session.exec(
            select(MeterReading).where(
                MeterReading.household_id == sleeper.id,
                MeterReading.period == "2024-03",
            )
        ).one()
        assert estimate.source == "estimate"
        assert estimate.day_meter_value == D("100")  # virtual: 50 + 50 estimated
        charges = {
            c.household_id: c
            for c in session.exec(
                select(HouseholdCharge).where(HouseholdCharge.period == "2024-03")
            )
        }
        assert charges[sleeper.id].is_estimated is True
        assert charges[sleeper.id].penalty_uah == D("30.00")  # 30% of 100
        assert charges[regular.id].penalty_credit_uah == D("30.00")
        assert sum(c.total_uah for c in charges.values()) == D("200.00")

    def test_the_next_real_reading_is_measured_against_the_virtual_value(
        self, client, session: Session
    ) -> None:
        regular, sleeper = _setup(client, session)
        make_meter_reading(
            session, household_id=regular.id, period="2024-03", day_meter_value="150"
        )
        _bill(client, "2024-03", "200.00")
        _close(client, "2024-03")  # sleeper estimated at virtual 100
        make_meter_reading(
            session, household_id=sleeper.id, period="2024-04", day_meter_value="120"
        )
        make_meter_reading(
            session, household_id=regular.id, period="2024-04", day_meter_value="200"
        )
        _bill(client, "2024-04", "200.00")

        assert _close(client, "2024-04").status_code == 200

        april = {
            c.household_id: c
            for c in session.exec(
                select(HouseholdCharge).where(HouseholdCharge.period == "2024-04")
            )
        }
        # 120 against the virtual 100, not against the real 50: no double billing.
        assert april[sleeper.id].day_usage_kwh == D("20")

    def test_a_lower_real_reading_after_an_estimate_gives_negative_usage(
        self, client, session: Session
    ) -> None:
        regular, sleeper = _setup(client, session)
        make_meter_reading(
            session, household_id=regular.id, period="2024-03", day_meter_value="150"
        )
        _bill(client, "2024-03", "200.00")
        _close(client, "2024-03")  # sleeper virtual 100
        make_meter_reading(
            session, household_id=sleeper.id, period="2024-04", day_meter_value="80"
        )
        make_meter_reading(
            session, household_id=regular.id, period="2024-04", day_meter_value="200"
        )
        _bill(client, "2024-04", "150.00")

        assert _close(client, "2024-04").status_code == 200

        april = {
            c.household_id: c
            for c in session.exec(
                select(HouseholdCharge).where(HouseholdCharge.period == "2024-04")
            )
        }
        assert april[sleeper.id].day_usage_kwh == D("-20")
        assert april[sleeper.id].tariff_uah == D("-40.00")  # a credit, not clamped to 0
        assert sum(c.total_uah for c in april.values()) == D("150.00")

    def test_no_usage_history_falls_back_to_the_median_never_zero(
        self, client, session: Session
    ) -> None:
        regular, _sleeper = _setup(client, session)
        baseline_only = make_household(
            session, name="New", user_id=make_user(session).id
        )
        make_meter_reading(
            session,
            household_id=baseline_only.id,
            period="2024-02",
            day_meter_value="500",
        )
        make_meter_reading(
            session, household_id=regular.id, period="2024-03", day_meter_value="160"
        )
        _bill(client, "2024-03", "300.00")

        assert _close(client, "2024-03").status_code == 200

        estimate = session.exec(
            select(MeterReading).where(
                MeterReading.household_id == baseline_only.id,
                MeterReading.period == "2024-03",
            )
        ).one()
        assert estimate.day_meter_value > D("500")

    def test_inactive_households_are_not_estimated_and_never_submitted_ones_are_skipped(
        self, client, session: Session
    ) -> None:
        regular, sleeper = _setup(client, session)
        sleeper_row = session.get(type(sleeper), sleeper.id)
        sleeper_row.is_active = False
        make_household(session, name="Brand new")  # no readings at all
        make_meter_reading(
            session, household_id=regular.id, period="2024-03", day_meter_value="150"
        )
        session.flush()
        _bill(client, "2024-03", "100.00")

        assert _close(client, "2024-03").status_code == 200

        assert [
            r.source
            for r in session.exec(
                select(MeterReading).where(MeterReading.period == "2024-03")
            )
        ] == ["resident"]
