"""`GET /billing/current-rate`: the per-kWh rate in force for the current period.

Residents see it to sanity-check a bill, so it must follow `effective_from <=
current period` (never newest row, never a future-dated one) and must not leak
internal columns. The clock is frozen at 2026-01-15 Kyiv, so the current period
is 2025-12 and the lookup crosses a year boundary.
"""

import pytest
from sqlmodel import Session

from tests.factories import authenticate, make_electricity_rate, make_user

PERIOD = "2025-12"


@pytest.fixture(autouse=True)
def _frozen_period(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.billing.routes.current_billing_period", lambda: PERIOD)


def test_requires_authentication(client) -> None:
    response = client.get("/billing/current-rate")

    assert response.status_code == 401


def test_user_without_a_household_still_gets_the_rate(client, session: Session) -> None:
    make_electricity_rate(
        session, day_rate_uah="4.32", night_rate_uah="2.16", effective_from="2025-01"
    )
    authenticate(client, make_user(session))

    response = client.get("/billing/current-rate")

    assert response.status_code == 200
    assert response.json()["day_rate_uah"] == "4.3200"


def test_returns_null_when_no_rate_is_configured(client, session: Session) -> None:
    authenticate(client, make_user(session))

    response = client.get("/billing/current-rate")

    assert response.status_code == 200
    assert response.json() is None


def test_returns_null_when_every_rate_is_future_dated(client, session: Session) -> None:
    make_electricity_rate(session, effective_from="2026-01")
    authenticate(client, make_user(session))

    response = client.get("/billing/current-rate")

    assert response.status_code == 200
    assert response.json() is None


def test_rate_effective_in_the_current_period_is_returned_with_string_decimals(
    client, session: Session
) -> None:
    make_electricity_rate(
        session, day_rate_uah="4.32", night_rate_uah="2.16", effective_from=PERIOD
    )
    authenticate(client, make_user(session))

    body = client.get("/billing/current-rate").json()

    assert body["day_rate_uah"] == "4.3200"
    assert body["night_rate_uah"] == "2.1600"
    assert body["effective_from"] == PERIOD


def test_newest_rate_not_after_the_period_wins_and_future_rate_is_ignored(
    client, session: Session
) -> None:
    # Inserted unsorted; the future row is also the newest by id.
    make_electricity_rate(
        session, day_rate_uah="5.00", night_rate_uah="2.50", effective_from="2025-09"
    )
    make_electricity_rate(
        session, day_rate_uah="3.00", night_rate_uah="1.50", effective_from="2024-12"
    )
    make_electricity_rate(
        session, day_rate_uah="9.00", night_rate_uah="7.00", effective_from="2026-01"
    )
    authenticate(client, make_user(session))

    body = client.get("/billing/current-rate").json()

    assert body["effective_from"] == "2025-09"
    assert body["day_rate_uah"] == "5.0000"
    assert body["night_rate_uah"] == "2.5000"


def test_response_exposes_only_the_rate_fields(client, session: Session) -> None:
    make_electricity_rate(session, effective_from="2025-01")
    authenticate(client, make_user(session))

    body = client.get("/billing/current-rate").json()

    assert set(body) == {"day_rate_uah", "night_rate_uah", "effective_from"}
