"""The app clock and the e2e-only pieces that the Playwright suite relies on.

The suite runs with ENVIRONMENT=development, so the e2e router is never mounted
here and `settings.environment` is never flipped: the guard is exercised by
constructing fresh `Settings` objects, and the e2e service functions are called
directly.
"""

from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from jose import jwt
from pydantic import ValidationError
from sqlmodel import Session, select
from starlette.testclient import TestClient

from app.api.auth import service as auth_service
from app.api.auth.service import (
    create_email_verification_token,
    create_password_reset_token,
)
from app.api.e2e import service as e2e_service
from app.core import email as email_module
from app.core import time as app_time
from app.core.config import (
    AuthSettings,
    DbSettings,
    ImapSettings,
    Settings,
    is_e2e_database,
    settings,
)
from app.core.domain.billing import kyiv_now
from app.core.time import now_utc_aware, set_clock_offset, utc_now
from app.db.models import Household, User
from tests.factories import DEFAULT_PASSWORD, authenticate, make_household, make_user

LOCAL_E2E_URL = "postgresql://postgres:postgres@localhost:5432/strumok_e2e"


@pytest.fixture(autouse=True)
def _restore_clock() -> Iterator[None]:
    set_clock_offset(timedelta(0))
    yield
    set_clock_offset(timedelta(0))


def _sign(claims: dict) -> str:
    return jwt.encode(
        claims,
        settings.auth.secret_key.get_secret_value(),
        algorithm=settings.auth.algorithm,
    )


def _real_now() -> datetime:
    return datetime.now(timezone.utc)


# --- the clock -----------------------------------------------------------------


def test_app_clock_offset_defaults_to_zero() -> None:
    before = _real_now()
    app = now_utc_aware()
    after = _real_now()
    assert before <= app <= after


def test_utc_now_and_kyiv_now_follow_the_offset() -> None:
    set_clock_offset(timedelta(days=400))
    expected = _real_now() + timedelta(days=400)

    assert abs(now_utc_aware() - expected) < timedelta(seconds=5)
    assert abs(utc_now() - expected.replace(tzinfo=None)) < timedelta(seconds=5)
    assert abs(kyiv_now() - expected) < timedelta(seconds=5)
    assert utc_now().tzinfo is None
    assert kyiv_now().utcoffset() in (timedelta(hours=2), timedelta(hours=3))


def test_clock_offset_can_be_moved_back_to_real_time() -> None:
    set_clock_offset(timedelta(days=-30))
    set_clock_offset(timedelta(0))
    assert abs(now_utc_aware() - _real_now()) < timedelta(seconds=5)


# --- access tokens use the app clock ------------------------------------------


def test_access_token_is_rejected_once_its_exp_passes_on_the_app_clock(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    authenticate(client, user)
    assert client.get("/auth/me").status_code == 200

    # Real time says the token has ~60 minutes left; the app clock says it's over.
    set_clock_offset(timedelta(hours=2))
    assert client.get("/auth/me").status_code == 401


def test_access_token_whose_exp_is_past_on_the_real_clock_is_valid_on_the_app_clock(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    set_clock_offset(timedelta(days=-3))
    authenticate(client, user)  # exp = 3 days ago + 1 hour, in real terms
    # The app clock is still back in the past, so the token is fresh.
    assert client.get("/auth/me").status_code == 200

    set_clock_offset(timedelta(0))
    assert client.get("/auth/me").status_code == 401


def test_access_token_without_exp_is_rejected(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    token = _sign(
        {
            "sub": str(user.id),
            "email": user.email,
            "auth_time": _real_now().timestamp(),
            "ver": user.token_version,
            "type": "access",
        }
    )
    client.cookies.set(settings.auth.auth_cookie_name, token)
    assert client.get("/auth/me").status_code == 401


def test_access_token_with_non_numeric_exp_is_rejected(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    token = _sign(
        {
            "sub": str(user.id),
            "exp": "tomorrow",
            "auth_time": _real_now().timestamp(),
            "ver": user.token_version,
            "type": "access",
        }
    )
    client.cookies.set(settings.auth.auth_cookie_name, token)
    assert client.get("/auth/me").status_code == 401


def test_access_token_is_valid_through_its_exp_second_and_expired_after(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    exp = int(_real_now().timestamp()) + 600
    token = _sign(
        {
            "sub": str(user.id),
            "exp": exp,
            "auth_time": _real_now().timestamp(),
            "ver": user.token_version,
            "type": "access",
        }
    )
    client.cookies.set(settings.auth.auth_cookie_name, token)

    set_clock_offset(timedelta(seconds=exp - int(_real_now().timestamp())))
    assert client.get("/auth/me").status_code == 200  # exp == now: not yet expired

    set_clock_offset(timedelta(seconds=exp - int(_real_now().timestamp()) + 2))
    assert client.get("/auth/me").status_code == 401


def test_refresh_accepts_an_access_token_whose_exp_has_passed(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    authenticate(client, user)
    set_clock_offset(timedelta(hours=2))
    assert client.get("/auth/me").status_code == 401

    response = client.post("/auth/refresh")

    assert response.status_code == 204
    assert client.get("/auth/me").status_code == 200


def test_refresh_still_rejects_a_token_with_no_exp(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    token = _sign(
        {
            "sub": str(user.id),
            "auth_time": _real_now().timestamp(),
            "ver": user.token_version,
            "type": "access",
        }
    )
    client.cookies.set(settings.auth.auth_cookie_name, token)
    assert client.post("/auth/refresh").status_code == 401


# --- emailed tokens use the app clock -----------------------------------------


def test_email_verification_token_expires_on_the_app_clock(
    client: TestClient, session: Session
) -> None:
    user = make_user(session, email_verified=False)
    token = create_email_verification_token(user)
    minutes = settings.auth.verification_token_expiration

    set_clock_offset(timedelta(minutes=minutes + 1))
    response = client.post("/auth/verify-email", json={"token": token})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalidOrExpiredToken"
    session.refresh(user)
    assert user.email_verified is False


def test_email_verification_token_is_valid_before_the_app_clock_reaches_exp(
    client: TestClient, session: Session
) -> None:
    user = make_user(session, email_verified=False)
    token = create_email_verification_token(user)
    minutes = settings.auth.verification_token_expiration

    set_clock_offset(timedelta(minutes=minutes - 5))
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200


def test_email_change_token_expires_on_the_app_clock(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        auth_service,
        "send_email",
        lambda **kwargs: sent.append(kwargs["html_content"]),
    )
    user = make_user(session, email="old@example.com")
    authenticate(client, user)
    assert (
        client.post(
            "/auth/email",
            json={"current_password": DEFAULT_PASSWORD, "new_email": "new@example.com"},
        ).status_code
        == 204
    )
    token = sent[0].split("token=")[1].split('"')[0].split("<")[0].split("&")[0]

    set_clock_offset(timedelta(minutes=settings.auth.verification_token_expiration + 1))
    response = client.post("/auth/confirm-email-change", json={"token": token})

    assert response.status_code == 400
    assert response.json()["detail"] == "invalidOrExpiredToken"
    session.refresh(user)
    assert user.email == "old@example.com"


def test_password_reset_token_expires_on_the_app_clock(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    token = create_password_reset_token(user)

    set_clock_offset(auth_service.PASSWORD_RESET_TTL + timedelta(minutes=1))
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "a-brand-new-password"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalidOrExpiredToken"


def test_password_reset_token_is_valid_before_the_app_clock_reaches_exp(
    client: TestClient, session: Session
) -> None:
    user = make_user(session)
    token = create_password_reset_token(user)

    set_clock_offset(auth_service.PASSWORD_RESET_TTL - timedelta(minutes=5))
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "a-brand-new-password"},
    )
    assert response.status_code == 200


# --- the e2e config guard -----------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:postgres@localhost:5432/strumok_e2e",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/other_e2e",
    ],
)
def test_is_e2e_database_accepts_local_e2e_databases(url: str) -> None:
    assert is_e2e_database(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.example.com:5432/strumok_e2e",
        "postgresql://u:p@localhost.evil.com:5432/strumok_e2e",
        "postgresql://u:p@localhost:5432/strumok",
        "postgresql://u:p@localhost:5432/strumok_e2e_backup",
        "postgresql://u:p@localhost:5432/",
        "postgresql://localhost:5432/strumok_e2e@db.example.com",
        "postgresql://u:p@localhost/x_e2e?host=remote.example.com",
        "postgresql://u:p@localhost/x_e2e?hostaddr=10.0.0.5",
        "postgresql://u:p@localhost/x_e2e?service=prod",
        "postgresql://u:p@localhost/Strumok_E2E",
        "postgresql://u:p@localhost/x-y_e2e",
    ],
)
def test_is_e2e_database_rejects_remote_or_non_e2e_databases(url: str) -> None:
    assert is_e2e_database(url) is False


def _settings(
    environment: str, *, url: str = LOCAL_E2E_URL, **extra: object
) -> Settings:
    return Settings(  # pyright: ignore[reportCallIssue]
        _env_file=None,  # pyright: ignore[reportCallIssue]
        environment=environment,  # pyright: ignore[reportArgumentType]
        db=DbSettings(url=url),
        **extra,  # pyright: ignore[reportArgumentType]
    )


def test_e2e_environment_accepts_a_local_e2e_database() -> None:
    assert _settings("e2e").environment == "e2e"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db.example.com:5432/strumok_e2e",
        "postgresql://u:p@localhost:5432/strumok",
    ],
)
def test_e2e_environment_refuses_a_remote_or_non_e2e_database(url: str) -> None:
    with pytest.raises(ValidationError):
        _settings("e2e", url=url)


def test_e2e_environment_refuses_enabled_imap() -> None:
    imap = ImapSettings(
        user="coop@example.com",
        password="x",
        allowed_senders=["a@bank.ua"],  # pyright: ignore[reportArgumentType]
    )
    assert imap.enabled
    with pytest.raises(ValidationError):
        _settings("e2e", imap=imap)


@pytest.mark.parametrize("environment", ["development", "production"])
def test_guard_does_not_apply_outside_e2e(environment: str) -> None:
    imap = ImapSettings(
        user="coop@example.com",
        password="x",
        allowed_senders=["a@bank.ua"],  # pyright: ignore[reportArgumentType]
    )
    built = _settings(
        environment, url="postgresql://u:p@db.example.com:5432/strumok", imap=imap
    )
    assert built.environment == environment


def test_every_settings_class_hides_input_in_validation_errors() -> None:
    from app.core import config

    classes = [
        config.DbSettings,
        config.AuthSettings,
        config.BrevoSettings,
        config.PushSettings,
        config.ImapSettings,
        config.Settings,
    ]
    for cls in classes:
        assert cls.model_config.get("hide_input_in_errors") is True, cls.__name__


def test_nested_settings_error_does_not_echo_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRATION", "hunter2-not-an-int")
    with pytest.raises(ValidationError) as caught:
        AuthSettings(secret_key="s")  # pyright: ignore[reportCallIssue,reportArgumentType]
    assert "hunter2-not-an-int" not in str(caught.value)


def test_invalid_settings_error_does_not_echo_secrets() -> None:
    with pytest.raises(ValidationError) as caught:
        _settings("e2e", url="postgresql://u:hunter2-pw@db.example.com:5432/x")
    assert "hunter2-pw" not in str(caught.value)


# --- the e2e router is absent outside e2e -------------------------------------


def test_e2e_routes_are_not_mounted_outside_e2e(client: TestClient) -> None:
    assert settings.environment == "development"
    for method, path in [
        ("post", "/__e2e/reset"),
        ("put", "/__e2e/clock"),
        ("post", "/__e2e/users"),
    ]:
        response = getattr(client, method)(path, json={})
        assert response.status_code in (404, 405), path

    # Were the router mounted this would be a JSON list; a dist build may
    # answer with the SPA shell instead, which is fine.
    outbox = client.get("/__e2e/outbox")
    assert outbox.status_code in (200, 404)
    assert not outbox.headers.get("content-type", "").startswith("application/json")

    clock = client.put("/__e2e/clock", json={"now": "2031-01-02T12:00:00+02:00"})
    assert clock.status_code in (404, 405)
    assert abs(now_utc_aware() - _real_now()) < timedelta(seconds=5)


def test_e2e_paths_are_absent_from_the_openapi_schema(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert not [p for p in paths if "__e2e" in p]


# --- e2e service ---------------------------------------------------------------


def test_reset_empties_every_table_and_restarts_identities(session: Session) -> None:
    owner = make_user(session)
    make_household(session, name="A", user_id=owner.id)
    make_household(session, name="B", user_id=owner.id)
    email_module.e2e_outbox.append({"to": "x@y.z", "subject": "s", "html_content": "h"})
    set_clock_offset(timedelta(days=9))

    e2e_service.reset(session)

    assert session.exec(select(User)).all() == []
    assert session.exec(select(Household)).all() == []
    assert email_module.e2e_outbox == []
    assert abs(now_utc_aware() - _real_now()) < timedelta(seconds=5)

    fresh = make_household(session, name="First")
    assert fresh.id == 1


def test_set_clock_with_an_aware_time_moves_the_app_clock_and_keeps_it_running() -> (
    None
):
    target = datetime(2027, 1, 2, 12, 0, tzinfo=timezone(timedelta(hours=2)))

    returned = e2e_service.set_clock(target)

    assert abs(returned - target) < timedelta(seconds=5)
    assert abs(now_utc_aware() - target) < timedelta(seconds=5)
    assert abs(kyiv_now() - target) < timedelta(seconds=5)
    assert kyiv_now().year == 2027 and kyiv_now().day == 2
    assert app_time._offset > timedelta(days=30)


def test_reset_clock_returns_the_app_clock_to_real_time() -> None:
    e2e_service.set_clock(datetime(2031, 6, 1, tzinfo=timezone.utc))
    e2e_service.reset_clock()
    assert abs(now_utc_aware() - _real_now()) < timedelta(seconds=5)


def test_outbox_filters_by_recipient_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [
        {"to": "Anna@Example.com", "subject": "1", "html_content": "a"},
        {"to": "boris@example.com", "subject": "2", "html_content": "b"},
        {"to": "anna@example.com", "subject": "3", "html_content": "c"},
    ]
    monkeypatch.setattr(email_module, "e2e_outbox", list(messages))

    assert [m["subject"] for m in e2e_service.outbox(" ANNA@example.com ")] == [
        "1",
        "3",
    ]
    assert e2e_service.outbox("nobody@example.com") == []
    assert [m["subject"] for m in e2e_service.outbox(None)] == ["1", "2", "3"]


def test_create_user_makes_an_active_verified_user_who_can_log_in(
    client: TestClient, session: Session
) -> None:
    from app.db.models import LanguageCode

    user = e2e_service.create_user(
        session,
        email_address="  Admin@Example.COM ",
        password="correct-horse-battery",
        first_name="Ada",
        last_name="Head",
        is_admin=True,
        language=LanguageCode.EN,
    )

    assert user.email == "admin@example.com"
    login = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    assert client.get("/auth/me").status_code == 200


def test_push_in_e2e_is_recorded_not_sent_to_the_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.push import service as push_service
    from app.db.models import PushSubscription

    def _must_not_be_called(**_: object) -> None:
        raise AssertionError("webpush must not be called under e2e")

    monkeypatch.setattr(settings, "environment", "e2e")
    monkeypatch.setattr(push_service, "webpush", _must_not_be_called)
    monkeypatch.setattr(push_service, "e2e_push_outbox", [])
    subscription = PushSubscription(
        user_id=1, endpoint="https://push.example.com/e/1", p256dh="k", auth="a"
    )

    outcome = push_service.send_one(subscription, '{"title": "t"}')

    assert outcome is push_service.SendOutcome.SENT
    assert push_service.e2e_push_outbox == [
        {"endpoint": "https://push.example.com/e/1", "payload": '{"title": "t"}'}
    ]


def test_reset_clears_the_push_outbox(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushed = [{"endpoint": "e", "payload": "p"}]
    monkeypatch.setattr(e2e_service, "e2e_push_outbox", pushed)

    e2e_service.reset(session)

    assert pushed == []
