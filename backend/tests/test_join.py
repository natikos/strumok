"""Self-registration: a resident signs up and takes a free plot in one step."""

from unittest.mock import patch

from sqlmodel import Session, select

from app.api.auth.throttle import JOIN_IP_LIMIT
from app.core.config import settings
from app.db.models import AuditLog, HouseholdOwnership, User
from tests.factories import make_household, make_user


def _payload(household_id: int, **overrides) -> dict:
    payload = {
        "email": "New.Resident@example.com",
        "first_name": "Nina",
        "last_name": "Kovalenko",
        "password": "correct-horse-battery-staple",
        "household_id": household_id,
    }
    payload.update(overrides)
    return payload


class TestJoinableHouseholds:
    def test_lists_only_active_plots_without_an_owner(
        self, client, session: Session
    ) -> None:
        free = make_household(session, name="Вільна")
        make_household(session, name="Зайнята", user_id=make_user(session).id)
        make_household(session, name="Неактивна", is_active=False)

        response = client.get("/auth/join/households")

        assert response.status_code == 200
        assert response.json() == [{"id": free.id, "name": "Вільна"}]


class TestJoin:
    @patch("app.api.auth.service.send_email")
    def test_creates_account_owns_plot_and_signs_in(
        self, mock_send_email, client, session: Session
    ) -> None:
        household = make_household(session)

        response = client.post("/auth/join", json=_payload(household.id))

        assert response.status_code == 201, response.text
        assert response.json()["email"] == "new.resident@example.com"
        assert settings.auth.auth_cookie_name in response.cookies
        user = session.exec(
            select(User).where(User.email == "new.resident@example.com")
        ).one()
        session.refresh(household)
        assert household.user_id == user.id
        assert session.exec(
            select(HouseholdOwnership).where(
                HouseholdOwnership.household_id == household.id,
                HouseholdOwnership.user_id == user.id,
            )
        ).one()
        assert "residentSelfRegistered" in {
            e.action for e in session.exec(select(AuditLog)).all()
        }
        mock_send_email.assert_called_once()

    @patch("app.api.auth.service.send_email")
    def test_taken_plot_disappears_from_the_list(
        self, _mock, client, session: Session
    ) -> None:
        household = make_household(session)

        client.post("/auth/join", json=_payload(household.id))

        assert client.get("/auth/join/households").json() == []

    @patch("app.api.auth.service.send_email")
    def test_plot_taken_in_the_meantime_is_409(
        self, _mock, client, session: Session
    ) -> None:
        household = make_household(session, user_id=make_user(session).id)

        response = client.post("/auth/join", json=_payload(household.id))

        assert response.status_code == 409
        assert response.json()["detail"] == "householdAlreadyAssigned"
        assert (
            session.exec(
                select(User).where(User.email == "new.resident@example.com")
            ).first()
            is None
        )

    def test_unknown_or_inactive_plot_is_404(self, client, session: Session) -> None:
        inactive = make_household(session, is_active=False)

        for household_id in (inactive.id, 999999):
            response = client.post("/auth/join", json=_payload(household_id))
            assert response.status_code == 404
            assert response.json()["detail"] == "householdNotFound"

    def test_registered_email_is_409(self, client, session: Session) -> None:
        make_user(session, email="new.resident@example.com")
        household = make_household(session)

        response = client.post("/auth/join", json=_payload(household.id))

        assert response.status_code == 409
        assert response.json()["detail"] == "emailAlreadyRegistered"
        session.refresh(household)
        assert household.user_id is None

    @patch("app.api.auth.service.send_email")
    def test_ip_is_throttled(self, _mock, client, session: Session) -> None:
        household = make_household(session, user_id=make_user(session).id)
        for _ in range(JOIN_IP_LIMIT.max_attempts):
            client.post("/auth/join", json=_payload(household.id))

        response = client.post("/auth/join", json=_payload(household.id))

        assert response.status_code == 429
        assert response.json()["detail"] == "tooManyAttempts"
