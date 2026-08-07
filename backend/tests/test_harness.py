"""Tests for the test harness itself.

These assert that the savepoint fixture really isolates. The failure mode being
guarded against is silent: a subtly wrong fixture lets rows leak between tests
while every test still passes, so the leak only shows up much later as
order-dependent flakiness. The pair below turns that into an immediate failure.
"""

from decimal import Decimal

from sqlmodel import Session, func, select

from app.db.models import Household, MeterReading, User
from tests.factories import (
    DEFAULT_PASSWORD,
    authenticate,
    make_household,
    make_meter_reading,
    make_user,
)


def _count(session: Session, model: type) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


class TestIsolation:
    """Rows written by one test must not be visible to the next."""

    def test_a_writes_rows(self, session: Session) -> None:
        user = make_user(session, email="leak-check@example.com")
        make_household(session, name="Leak Check", user_id=user.id)

        assert _count(session, User) == 1
        assert _count(session, Household) == 1

    def test_b_sees_an_empty_database(self, session: Session) -> None:
        # Fails if the previous test's rows survived, i.e. the savepoint teardown
        # is not actually rolling back.
        assert _count(session, User) == 0
        assert _count(session, Household) == 0


class TestIsolationSurvivesServiceCommit:
    """The service layer commits its own transaction; that must not escape.

    ``submit_meter_reading`` calls ``session.commit()``. Without the savepoint
    restart listener this would either end the outer transaction (leaking the row)
    or leave the session unusable for the rest of the test.
    """

    def test_a_submits_through_the_api(self, client, session: Session) -> None:
        user = make_user(session, email="commit-check@example.com")
        household = make_household(session, name="Commit Check", user_id=user.id)
        authenticate(client, user)

        response = client.post(
            "/meter-readings",
            params={"household_id": household.id},
            json={
                "period": "2026-07",
                "day_meter_value": "1000.00",
                "night_meter_value": "500.00",
            },
        )

        assert response.status_code == 201, response.text
        # The session is still usable after the service's commit.
        assert _count(session, MeterReading) == 1

    def test_b_sees_no_committed_reading(self, session: Session) -> None:
        assert _count(session, MeterReading) == 0


class TestHarnessWiring:
    """Sanity checks on auth, Decimal fidelity, and the app under test."""

    def test_health_endpoint_is_reachable(self, client) -> None:
        assert client.get("/health").json() == {"status": "ok"}

    def test_unauthenticated_request_is_rejected(self, client) -> None:
        response = client.get("/meter-readings")

        assert response.status_code == 401
        assert response.json()["detail"] == "missingAuthenticationToken"

    def test_real_login_issues_a_usable_cookie(self, client, session: Session) -> None:
        # Exercises the genuine password + JWT path rather than a stubbed
        # dependency, so the auth boundary itself is under test.
        user = make_user(session, email="login@example.com")
        make_household(session, name="Login Plot", user_id=user.id)

        login = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": DEFAULT_PASSWORD},
        )
        assert login.status_code == 200, login.text

        assert client.get("/meter-readings").status_code == 200

    def test_decimal_survives_the_database_round_trip(self, session: Session) -> None:
        # The reason this suite requires Postgres instead of SQLite: money must
        # come back as an exact Decimal, not a float approximation.
        user = make_user(session)
        household = make_household(session, user_id=user.id)
        reading = make_meter_reading(
            session,
            household_id=household.id,
            period="2026-07",
            day_meter_value="1234.56",
            amount_charged_uah="987.65",
        )
        session.expire(reading)

        assert reading.day_meter_value == Decimal("1234.56")
        assert isinstance(reading.amount_charged_uah, Decimal)
        assert reading.amount_charged_uah == Decimal("987.65")
