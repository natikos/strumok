"""Auth flow coverage: register, login, refresh, logout, /auth/me, verification-link.

Registration already sends a verification email (see test_register_email.py), so
every test here that hits /auth/register mocks `send_email` to keep the suite from
depending on Brevo credentials or making a real network call.
"""

from datetime import timedelta
from unittest.mock import patch

from jose import jwt
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.time import utc_now
from tests.factories import DEFAULT_PASSWORD, authenticate, make_user


def _register_payload(**overrides) -> dict:
    payload = {
        "email": "newresident@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": "correct-horse-battery-staple",
    }
    payload.update(overrides)
    return payload


class TestRegister:
    @patch("app.api.auth.service.send_email")
    def test_register_creates_user_and_sets_auth_cookie(self, mock_send_email, client: TestClient) -> None:
        response = client.post("/auth/register", json=_register_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newresident@example.com"
        assert body["email_verified"] is False
        assert settings.auth.auth_cookie_name in response.cookies

    @patch("app.api.auth.service.send_email")
    def test_register_with_taken_email_returns_409(self, mock_send_email, client: TestClient, session) -> None:
        make_user(session, email="taken@example.com")

        response = client.post("/auth/register", json=_register_payload(email="taken@example.com"))

        assert response.status_code == 409
        assert response.json()["detail"] == "emailAlreadyRegistered"

    @patch("app.api.auth.service.send_email")
    def test_register_with_taken_email_is_case_insensitive(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        make_user(session, email="taken@example.com")

        response = client.post("/auth/register", json=_register_payload(email="TAKEN@example.com"))

        assert response.status_code == 409
        assert response.json()["detail"] == "emailAlreadyRegistered"


class TestLogin:
    def test_login_with_correct_credentials_sets_auth_cookie(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")

        response = client.post(
            "/auth/login",
            json={"email": "resident@example.com", "password": DEFAULT_PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["email"] == user.email
        assert settings.auth.auth_cookie_name in response.cookies

    def test_login_with_wrong_password_returns_401(self, client: TestClient, session) -> None:
        make_user(session, email="resident@example.com")

        response = client.post(
            "/auth/login",
            json={"email": "resident@example.com", "password": "definitely-wrong"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidCredentials"
        assert settings.auth.auth_cookie_name not in response.cookies

    def test_login_with_unknown_email_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "whatever123"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidCredentials"

    def test_login_for_inactive_user_returns_401(self, client: TestClient, session) -> None:
        make_user(session, email="left@example.com", is_active=False)

        response = client.post(
            "/auth/login",
            json={"email": "left@example.com", "password": DEFAULT_PASSWORD},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidCredentials"


class TestMe:
    def test_me_without_cookie_returns_401(self, client: TestClient) -> None:
        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "missingAuthenticationToken"

    def test_me_with_garbage_token_returns_401(self, client: TestClient) -> None:
        client.cookies.set(settings.auth.auth_cookie_name, "not-a-jwt")

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_with_expired_token_returns_401(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        expired_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(minutes=1),
                "type": "access",
            },
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, expired_token)

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_returns_current_user_with_households(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)

        response = client.get("/auth/me")

        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "resident@example.com"
        assert body["households"] == []


class TestRefresh:
    def test_refresh_without_cookie_returns_401(self, client: TestClient) -> None:
        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "missingAuthenticationToken"

    def test_refresh_with_expired_token_still_succeeds(self, client: TestClient, session) -> None:
        """/auth/refresh calls get_user_from_token(verify_expiration=False), so an
        expired-but-otherwise-valid token is the intended refresh case, not a
        rejection -- confirmed by reading app/api/auth/routes.py:206-211."""
        user = make_user(session, email="resident@example.com")
        expired_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(days=1),
                "type": "access",
            },
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, expired_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 204
        assert settings.auth.auth_cookie_name in response.cookies

        new_token = response.cookies[settings.auth.auth_cookie_name]
        new_claims = jwt.decode(
            new_token, settings.auth.secret_key, algorithms=[settings.auth.algorithm]
        )
        assert new_claims["exp"] > utc_now().timestamp()

    def test_refresh_with_bad_signature_returns_401(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        forged_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() + timedelta(minutes=5),
                "type": "access",
            },
            "a-completely-different-secret",
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, forged_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_with_missing_subject_returns_401(self, client: TestClient) -> None:
        token_without_subject = jwt.encode(
            {"email": "nobody@example.com", "exp": utc_now() + timedelta(minutes=5), "type": "access"},
            settings.auth.secret_key,
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, token_without_subject)

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_for_deactivated_user_returns_401(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        user.is_active = False
        session.add(user)
        session.flush()

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"


class TestLogout:
    def test_logout_clears_cookie(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)

        response = client.post("/auth/logout")

        assert response.status_code == 204
        set_cookie_header = response.headers.get("set-cookie", "")
        assert f"{settings.auth.auth_cookie_name}=" in set_cookie_header
        assert "Max-Age=0" in set_cookie_header

    def test_logout_delete_cookie_omits_secure_flag_present_at_login_in_production_config(self) -> None:
        """Exercises the two Response.delete_cookie/set_cookie calls exactly as
        app/api/auth/routes.py invokes them, under production's `secure=True`,
        without touching the app or a database. This isolates the bug from the
        dev-only cookie constraints the rest of the suite runs under.
        """
        from starlette.responses import Response

        login_response = Response()
        login_response.set_cookie(
            key=settings.auth.auth_cookie_name,
            value="token",
            httponly=True,
            max_age=settings.auth_token_ttl_seconds,
            samesite="lax",
            secure=True,  # production value of settings.auth_cookie_secure
        )

        logout_response = Response()
        # Mirrors app/api/auth/routes.py:226 exactly -- no `secure` kwarg.
        logout_response.delete_cookie(key=settings.auth.auth_cookie_name, samesite="lax")

        login_set_cookie = login_response.headers["set-cookie"]
        logout_set_cookie = logout_response.headers["set-cookie"]

        assert "Secure" in login_set_cookie
        # BUG: this cookie was set with Secure, but the delete omits it. A
        # browser only overwrites a Secure cookie with a Set-Cookie that is
        # also sent over HTTPS and (per RFC 6265bis secure-cookie rules,
        # enforced by Chrome/Firefox) still requires the deleting response's
        # cookie to be treated consistently; more concretely, some browsers
        # will store this as a *second*, non-Secure cookie with the same name
        # rather than clearing the original, leaving the Secure auth cookie
        # alive after "logout".
        assert "Secure" not in logout_set_cookie


class TestVerificationLinkCooldown:
    @patch("app.api.auth.service.send_email")
    def test_requesting_verification_link_twice_within_cooldown_returns_429(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        user = make_user(session, email="unverified@example.com", email_verified=False)
        authenticate(client, user)

        first = client.post("/auth/verification-link")
        assert first.status_code == 204

        second = client.post("/auth/verification-link")

        assert second.status_code == 429
        assert second.json()["detail"] == "verificationEmailCooldown"
        retry_after = second.headers.get("retry-after")
        assert retry_after is not None
        assert 0 < int(retry_after) <= settings.auth.verify_email_resend_cooldown_seconds

    @patch("app.api.auth.service.send_email")
    def test_requesting_verification_link_after_cooldown_elapses_succeeds(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        user = make_user(session, email="unverified@example.com", email_verified=False)
        user.verification_email_last_sent_at = utc_now() - timedelta(
            seconds=settings.auth.verify_email_resend_cooldown_seconds + 5
        )
        session.add(user)
        session.flush()
        authenticate(client, user)

        response = client.post("/auth/verification-link")

        assert response.status_code == 204
        assert mock_send_email.call_count == 1

    @patch("app.api.auth.service.send_email")
    def test_requesting_verification_link_for_already_verified_user_is_a_noop(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        user = make_user(session, email="verified@example.com", email_verified=True)
        authenticate(client, user)

        response = client.post("/auth/verification-link")

        assert response.status_code == 204
        mock_send_email.assert_not_called()

    def test_verification_link_without_cookie_returns_401(self, client: TestClient) -> None:
        response = client.post("/auth/verification-link")

        assert response.status_code == 401
        assert response.json()["detail"] == "missingAuthenticationToken"
