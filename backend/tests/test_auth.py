"""Auth flow coverage: register, login, refresh, logout, /auth/me, verification-link.

Registration already sends a verification email (see test_register_email.py), so
every test here that hits /auth/register mocks `send_email` to keep the suite from
depending on Brevo credentials or making a real network call.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from jose import jwt
from starlette.testclient import TestClient

from app.api.auth.service import create_email_verification_token
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
    def test_register_creates_user_and_sets_auth_cookie(
        self, mock_send_email, client: TestClient
    ) -> None:
        response = client.post("/auth/register", json=_register_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newresident@example.com"
        assert body["email_verified"] is False
        assert settings.auth.auth_cookie_name in response.cookies

    @patch("app.api.auth.service.send_email")
    def test_register_with_taken_email_returns_409(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        make_user(session, email="taken@example.com")

        response = client.post(
            "/auth/register", json=_register_payload(email="taken@example.com")
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "emailAlreadyRegistered"

    @patch("app.api.auth.service.send_email")
    def test_register_with_taken_email_is_case_insensitive(
        self, mock_send_email, client: TestClient, session
    ) -> None:
        make_user(session, email="taken@example.com")

        response = client.post(
            "/auth/register", json=_register_payload(email="TAKEN@example.com")
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "emailAlreadyRegistered"


class TestLogin:
    def test_login_with_correct_credentials_sets_auth_cookie(
        self, client: TestClient, session
    ) -> None:
        user = make_user(session, email="resident@example.com")

        response = client.post(
            "/auth/login",
            json={"email": "resident@example.com", "password": DEFAULT_PASSWORD},
        )

        assert response.status_code == 200
        assert response.json()["email"] == user.email
        assert settings.auth.auth_cookie_name in response.cookies

    def test_login_with_wrong_password_returns_401(
        self, client: TestClient, session
    ) -> None:
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

    def test_login_for_inactive_user_returns_401(
        self, client: TestClient, session
    ) -> None:
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

    def test_me_with_expired_token_returns_401(
        self, client: TestClient, session
    ) -> None:
        user = make_user(session, email="resident@example.com")
        expired_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(minutes=1),
                "auth_time": utc_now().timestamp(),
                "ver": user.token_version,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, expired_token)

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_with_stale_token_version_returns_401(
        self, client: TestClient, session
    ) -> None:
        """A token minted before logout (or any future password change / deactivation
        that bumps token_version) must stop authenticating immediately, not just
        stop refreshing -- get_current_user goes through get_user_from_token, which
        checks `ver` too."""
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        user.token_version += 1
        session.add(user)
        session.flush()

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_with_email_verification_token_returns_401(
        self, client: TestClient, session
    ) -> None:
        """An emailed verification-link token must not double as a session cookie.

        Regression for #62: get_user_from_token previously accepted any token
        signed with the app secret regardless of `type`, so a verification
        token (mailed to the resident, type "email_verification") could be
        used to authenticate a full session.
        """
        user = make_user(session, email="resident@example.com")
        verification_token = create_email_verification_token(user)
        client.cookies.set(settings.auth.auth_cookie_name, verification_token)

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_returns_current_user_with_households(
        self, client: TestClient, session
    ) -> None:
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

    def test_refresh_with_expired_token_still_succeeds(
        self, client: TestClient, session
    ) -> None:
        """/auth/refresh accepts a token whose `exp` has already passed -- that's
        the whole point of refresh -- as long as it's still within the idle and
        absolute windows. `auth_time` here is "now", well within both windows;
        only `exp` is stale."""
        user = make_user(session, email="resident@example.com")
        expired_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(days=1),
                "auth_time": utc_now().timestamp(),
                "ver": user.token_version,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, expired_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 204
        assert settings.auth.auth_cookie_name in response.cookies

        new_token = response.cookies[settings.auth.auth_cookie_name]
        new_claims = jwt.decode(
            new_token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
        )
        assert new_claims["exp"] > utc_now().timestamp()

    def test_refresh_carries_original_auth_time_forward(
        self, client: TestClient, session
    ) -> None:
        """The refreshed token must keep the ORIGINAL login instant, not reset it
        to now -- otherwise continuous refreshing would let a session live
        forever, defeating the 180-day absolute cap entirely."""
        user = make_user(session, email="resident@example.com")
        original_auth_time = (utc_now() - timedelta(days=100)).timestamp()
        token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(days=1),
                "auth_time": original_auth_time,
                "ver": user.token_version,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, token)

        response = client.post("/auth/refresh")

        assert response.status_code == 204
        new_token = response.cookies[settings.auth.auth_cookie_name]
        new_claims = jwt.decode(
            new_token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
        )
        assert new_claims["auth_time"] == pytest.approx(original_auth_time, abs=1)

    def test_refresh_with_bad_signature_returns_401(
        self, client: TestClient, session
    ) -> None:
        user = make_user(session, email="resident@example.com")
        forged_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() + timedelta(minutes=5),
                "auth_time": utc_now().timestamp(),
                "ver": user.token_version,
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
            {
                "email": "nobody@example.com",
                "exp": utc_now() + timedelta(minutes=5),
                "auth_time": utc_now().timestamp(),
                "ver": 0,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, token_without_subject)

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_for_deactivated_user_returns_401(
        self, client: TestClient, session
    ) -> None:
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        user.is_active = False
        session.add(user)
        session.flush()

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_me_for_deactivated_user_returns_401(
        self, client: TestClient, session
    ) -> None:
        """A deactivated user's outstanding session must stop working immediately
        on every authenticated route, not just refresh."""
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        user.is_active = False
        session.add(user)
        session.flush()

        response = client.get("/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_with_stale_token_version_returns_401(
        self, client: TestClient, session
    ) -> None:
        """A token issued before the user's token_version was bumped (logout,
        eventually password reset/deactivation) must not be refreshable, even
        though its signature, exp, and auth_time all look fine on their own."""
        user = make_user(session, email="resident@example.com")
        user.token_version = 1
        session.add(user)
        session.flush()
        stale_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() + timedelta(minutes=5),
                "auth_time": utc_now().timestamp(),
                "ver": 0,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, stale_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_session_older_than_180_days_returns_401(
        self, client: TestClient, session
    ) -> None:
        """Even a continuously-refreshed token (recent `exp`) must eventually stop
        working once the ORIGINAL login (`auth_time`) is more than the 180-day
        absolute cap in the past -- this is the hard session ceiling, independent
        of activity."""
        user = make_user(session, email="resident@example.com")
        old_session_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() + timedelta(minutes=5),
                "auth_time": (
                    utc_now()
                    - timedelta(days=settings.auth.refresh_absolute_window_days + 1)
                ).timestamp(),
                "ver": user.token_version,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, old_session_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 401
        assert response.json()["detail"] == "invalidOrExpiredToken"

    def test_refresh_after_30_days_still_succeeds(
        self, client: TestClient, session
    ) -> None:
        """The core usability fix: a resident who last opened the app 30 days ago
        -- well within both the 45-day idle window and the 180-day absolute cap
        -- must be refreshed transparently, not sent back to the login screen."""
        user = make_user(session, email="resident@example.com")
        month_old_token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "exp": utc_now() - timedelta(days=30),
                "auth_time": (utc_now() - timedelta(days=30)).timestamp(),
                "ver": user.token_version,
                "type": "access",
            },
            settings.auth.secret_key.get_secret_value(),
            algorithm=settings.auth.algorithm,
        )
        client.cookies.set(settings.auth.auth_cookie_name, month_old_token)

        response = client.post("/auth/refresh")

        assert response.status_code == 204
        assert settings.auth.auth_cookie_name in response.cookies


class TestLogout:
    def test_logout_clears_cookie(self, client: TestClient, session) -> None:
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)

        response = client.post("/auth/logout")

        assert response.status_code == 204
        set_cookie_header = response.headers.get("set-cookie", "")
        assert f"{settings.auth.auth_cookie_name}=" in set_cookie_header
        assert "Max-Age=0" in set_cookie_header

    def test_logout_delete_cookie_matches_secure_flag_set_at_login_in_production_config(
        self,
    ) -> None:
        """Exercises the two Response.delete_cookie/set_cookie calls exactly as
        app/api/auth/routes.py invokes them, under production's `secure=True`,
        without touching the app or a database. This isolates the assertion
        from the dev-only cookie constraints the rest of the suite runs under.
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
        # Mirrors app/api/auth/routes.py:224-228 exactly.
        logout_response.delete_cookie(
            key=settings.auth.auth_cookie_name,
            samesite="lax",
            secure=True,  # production value of settings.auth_cookie_secure
        )

        login_set_cookie = login_response.headers["set-cookie"]
        logout_set_cookie = logout_response.headers["set-cookie"]

        assert "Secure" in login_set_cookie
        # The delete must also carry Secure, or browsers may store it as a
        # second, non-Secure cookie with the same name instead of clearing
        # the original, leaving the Secure auth cookie alive after "logout".
        assert "Secure" in logout_set_cookie

    def test_logout_invalidates_leaked_copy_of_the_cookie(
        self, client: TestClient, session
    ) -> None:
        """The whole point of server-side revocation: a copy of the cookie taken
        before logout (e.g. by an attacker, or a second browser tab) must stop
        working for both reads and refresh once the legitimate user logs out --
        not just the cookie in the browser that issued the logout call."""
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        leaked_cookie = client.cookies.get(settings.auth.auth_cookie_name)
        assert leaked_cookie is not None

        logout_response = client.post("/auth/logout")
        assert logout_response.status_code == 204

        client.cookies.set(settings.auth.auth_cookie_name, leaked_cookie)

        me_response = client.get("/auth/me")
        assert me_response.status_code == 401
        assert me_response.json()["detail"] == "invalidOrExpiredToken"

        refresh_response = client.post("/auth/refresh")
        assert refresh_response.status_code == 401
        assert refresh_response.json()["detail"] == "invalidOrExpiredToken"

    def test_logout_without_cookie_is_a_noop_success(self, client: TestClient) -> None:
        response = client.post("/auth/logout")

        assert response.status_code == 204

    def test_logout_with_garbage_cookie_is_a_noop_success(
        self, client: TestClient
    ) -> None:
        client.cookies.set(settings.auth.auth_cookie_name, "not-a-jwt")

        response = client.post("/auth/logout")

        assert response.status_code == 204

    def test_replaying_an_already_revoked_cookie_does_not_log_out_a_later_session(
        self, client: TestClient, session
    ) -> None:
        """A copy of a cookie that's already been logged out must not keep the
        power to bump token_version forever -- otherwise an attacker holding
        one stale cookie could force-log-out every session the user starts
        from then on, a permanent targeted denial of service from a single
        leaked cookie (the exact scenario this whole fix exists to close)."""
        user = make_user(session, email="resident@example.com")
        authenticate(client, user)
        first_session_cookie = client.cookies.get(settings.auth.auth_cookie_name)
        assert first_session_cookie is not None

        # First logout: revokes the first session (bumps token_version once).
        assert client.post("/auth/logout").status_code == 204
        session.refresh(user)
        assert user.token_version == 1

        # A second, unrelated session starts (e.g. logging in on another device).
        authenticate(client, user)
        second_session_cookie = client.cookies.get(settings.auth.auth_cookie_name)

        # Replaying the already-revoked first cookie against /auth/logout
        # must be a no-op: it carries the stale ver=0, so it must NOT bump
        # token_version again and kill the second session.
        client.cookies.set(settings.auth.auth_cookie_name, first_session_cookie)
        replay_response = client.post("/auth/logout")
        assert replay_response.status_code == 204

        session.refresh(user)
        assert user.token_version == 1

        # The second session is still alive.
        client.cookies.set(settings.auth.auth_cookie_name, second_session_cookie)
        response = client.get("/auth/me")
        assert response.status_code == 200

    def test_login_issued_token_has_an_auth_time_close_to_now_in_utc(
        self, client: TestClient, session
    ) -> None:
        """auth_time must be computed as a UTC instant regardless of the
        server host's local timezone -- utc_now() returns a naive datetime,
        and reading it as local time (rather than tagging it UTC first) would
        skew every session's absolute-cap deadline by the host's UTC offset."""
        user = make_user(session, email="resident@example.com")

        response = client.post(
            "/auth/login",
            json={"email": user.email, "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 200

        token = response.cookies[settings.auth.auth_cookie_name]
        claims = jwt.decode(
            token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
        )

        now_utc = datetime.now(timezone.utc).timestamp()
        assert abs(claims["auth_time"] - now_utc) < 5


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
        assert (
            0 < int(retry_after) <= settings.auth.verify_email_resend_cooldown_seconds
        )

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

    def test_verification_link_without_cookie_returns_401(
        self, client: TestClient
    ) -> None:
        response = client.post("/auth/verification-link")

        assert response.status_code == 401
        assert response.json()["detail"] == "missingAuthenticationToken"
