"""Invite-only registration: the head creates accounts, residents set a password."""

from unittest.mock import patch

from sqlmodel import Session, select

from app.api.auth.service import authenticate_user, InvalidCredentialsError
from app.db.models import AuditLog, User
from tests.factories import authenticate, make_household, make_user
import pytest

INVITE = {
    "email": "New.Resident@example.com",
    "first_name": "Nina",
    "last_name": "Kovalenko",
    "language": "ua",
}


def _token(link: str) -> str:
    return link.split("token=")[1]


class TestInvite:
    @patch("app.api.auth.service.send_email")
    def test_invite_creates_passwordless_user_assigns_household_and_audits(
        self, mock_send_email, client, session: Session
    ) -> None:
        admin = make_user(session, is_admin=True)
        household = make_household(session)
        authenticate(client, admin)

        response = client.post(
            "/admin/users", json={**INVITE, "household_id": household.id}
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["email_sent"] is True
        assert body["user"]["email"] == "new.resident@example.com"
        user = session.get(User, body["user"]["id"])
        assert user.password_hash is None
        session.refresh(household)
        assert household.user_id == user.id
        assert mock_send_email.call_args.kwargs["subject"] == "Запрошення до Струмок"
        actions = {e.action for e in session.exec(select(AuditLog)).all()}
        assert {"userInvited", "householdOwnerAssigned"} <= actions

    @patch("app.api.auth.service.send_email")
    def test_invite_link_works_once_verifies_email_and_signs_in(
        self, mock_send_email, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        link = client.post("/admin/users", json=INVITE).json()["invite_link"]
        client.cookies.clear()

        accepted = client.post(
            "/auth/password-reset/confirm",
            json={"token": _token(link), "password": "my-new-password-1"},
        )

        assert accepted.status_code == 200
        assert accepted.json()["email_verified"] is True
        assert client.get("/auth/me").status_code == 200  # signed in
        again = client.post(
            "/auth/password-reset/confirm",
            json={"token": _token(link), "password": "other-password-2"},
        )
        assert again.status_code == 400

    @patch("app.api.auth.service.send_email")
    def test_account_without_password_cannot_log_in(
        self, mock_send_email, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        client.post("/admin/users", json=INVITE)
        client.cookies.clear()

        response = client.post(
            "/auth/login",
            json={"email": "new.resident@example.com", "password": "anything-at-all"},
        )
        assert response.status_code == 401
        with pytest.raises(InvalidCredentialsError):
            authenticate_user(
                session=session, email="new.resident@example.com", password="x"
            )

    @patch("app.api.auth.service.send_email")
    def test_taken_email_and_owned_household_are_conflicts(
        self, mock_send_email, client, session: Session
    ) -> None:
        make_user(session, email="new.resident@example.com")
        owner = make_user(session)
        owned = make_household(session, user_id=owner.id)
        authenticate(client, make_user(session, is_admin=True))

        taken = client.post("/admin/users", json=INVITE)
        busy = client.post(
            "/admin/users",
            json={**INVITE, "email": "other@example.com", "household_id": owned.id},
        )

        assert taken.status_code == 409
        assert taken.json()["detail"] == "emailAlreadyRegistered"
        assert busy.status_code == 409
        assert busy.json()["detail"] == "householdAlreadyAssigned"

    @patch("app.api.auth.service.send_email")
    def test_email_failure_still_returns_a_copyable_link(
        self, mock_send_email, client, session: Session
    ) -> None:
        from app.core.email import EmailSendError

        mock_send_email.side_effect = EmailSendError("down")
        authenticate(client, make_user(session, is_admin=True))

        body = client.post("/admin/users", json=INVITE).json()

        assert body["email_sent"] is False
        assert "/set-password?token=" in body["invite_link"]

    @patch("app.api.auth.service.send_email")
    def test_resend_is_audited_throttled_and_refused_once_accepted(
        self, mock_send_email, client, session: Session
    ) -> None:
        authenticate(client, make_user(session, is_admin=True))
        user_id = client.post("/admin/users", json=INVITE).json()["user"]["id"]

        for _ in range(3):
            assert client.post(f"/admin/users/{user_id}/invite").status_code == 200
        throttled = client.post(f"/admin/users/{user_id}/invite")

        assert throttled.status_code == 429
        assert "Retry-After" in throttled.headers
        assert (
            len(
                session.exec(
                    select(AuditLog).where(AuditLog.action == "inviteResent")
                ).all()
            )
            == 3
        )

        accepted = session.get(User, user_id)
        accepted.password_hash = "x"
        session.flush()
        refused = client.post(f"/admin/users/{user_id}/invite")
        assert refused.status_code == 409
        assert refused.json()["detail"] == "inviteAlreadyAccepted"

    def test_non_admin_cannot_invite(self, client, session: Session) -> None:
        authenticate(client, make_user(session))
        assert client.post("/admin/users", json=INVITE).status_code == 403
