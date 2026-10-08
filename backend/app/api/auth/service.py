from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, asc, select

from app.core.config import settings
from app.core.email import EmailSendError, send_email
from app.core.time import utc_now
from app.db.models import Household, User

VERIFICATION_TOKEN_TYPE = "email_verification"


def list_user_households(*, session: Session, user: User) -> list[Any]:
    return list(
        session.exec(
            select(Household.id, Household.name)
            .where(Household.user_id == user.id)
            .where(Household.is_active == True)  # noqa: E712
            .order_by(asc(Household.created_at))
        ).all()
    )


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Verified against when no user matches, so unknown emails cost the same bcrypt
# time as wrong passwords and response time doesn't reveal who is registered.
_DUMMY_PASSWORD_HASH = pwd_context.hash("timing-equalizer")


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidOrExpiredTokenError(Exception):
    pass


class VerificationEmailRateLimitError(Exception):
    def __init__(self, *, retry_after_seconds: int):
        super().__init__("verificationEmailCooldown")
        self.retry_after_seconds = retry_after_seconds


class VerificationEmailSendFailedError(Exception):
    pass


def create_access_token(user: User, *, auth_time: datetime | None = None) -> str:
    """`auth_time` is when the user originally logged in. Refresh passes the
    old value through so the 180-day cap isn't reset; login and register omit
    it, which starts a new session at the current time."""
    now = utc_now()
    expires = now + timedelta(minutes=settings.auth.access_token_expiration)
    # utc_now() is naive, and .timestamp() would treat it as local time.
    # Mark it as UTC first so auth_time is correct on any server timezone.
    auth_time_value = auth_time or now.replace(tzinfo=timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires,
        "auth_time": auth_time_value.timestamp(),
        "ver": user.token_version,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.auth.secret_key.get_secret_value(),
        algorithm=settings.auth.algorithm,
    )


def authenticate_user(*, session: Session, email: str, password: str) -> User:
    user = session.exec(
        select(User).where(User.email == email.strip().lower(), User.is_active)
    ).first()

    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_ok = pwd_context.verify(password, password_hash)

    if user is None or not password_ok:
        raise InvalidCredentialsError

    return user


def _decode_access_token(*, token: str, verify_expiration: bool) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
            options={"verify_exp": verify_expiration},
        )

        if payload.get("type") != "access":
            raise ValueError("Unexpected token type")

        if payload.get("sub") is None:
            raise ValueError("Token subject is missing")
    except (JWTError, ValueError) as exc:
        raise InvalidOrExpiredTokenError from exc

    return payload


def get_user_from_token(
    *,
    session: Session,
    token: str,
    verify_expiration: bool = True,
) -> User:
    payload = _decode_access_token(token=token, verify_expiration=verify_expiration)

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise InvalidOrExpiredTokenError from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidOrExpiredTokenError

    # A stale token_version means the user logged out (or a future password
    # reset/change, deactivation, or email change) since this token was
    # issued -- every outstanding token for them must stop working immediately.
    if payload.get("ver") != user.token_version:
        raise InvalidOrExpiredTokenError

    return user


def refresh_access_token(*, session: Session, token: str) -> str:
    """Validates an access token for refresh -- signature, type, subject, and
    token_version exactly like get_user_from_token(verify_expiration=False),
    plus the session's original auth_time must not be older than
    refresh_absolute_window_days. Returns a new token that carries the
    original auth_time forward unchanged."""
    payload = _decode_access_token(token=token, verify_expiration=False)

    try:
        user_id = int(payload["sub"])
        auth_time = payload["auth_time"]
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidOrExpiredTokenError from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidOrExpiredTokenError

    if payload.get("ver") != user.token_version:
        raise InvalidOrExpiredTokenError

    now = utc_now().replace(tzinfo=timezone.utc)
    auth_time_at = datetime.fromtimestamp(auth_time, tz=timezone.utc)

    session_age = now - auth_time_at
    if session_age > timedelta(days=settings.auth.refresh_absolute_window_days):
        raise InvalidOrExpiredTokenError

    return create_access_token(user, auth_time=auth_time_at)


def register_user(
    *,
    session: Session,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> User:
    user = User(
        email=email.strip().lower(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        password_hash=pwd_context.hash(password),
    )

    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailAlreadyRegisteredError from exc

    session.refresh(user)

    return user


def get_user_id_and_version_for_logout(token: str) -> tuple[int, int] | None:
    """Returns (user_id, ver) from the token, even if expired, or None if it's
    unusable. Checks the signature only -- callers must compare ver with the
    user's current token_version."""
    try:
        payload = _decode_access_token(token=token, verify_expiration=False)
        return int(payload["sub"]), int(payload["ver"])
    except InvalidOrExpiredTokenError, KeyError, ValueError, TypeError:
        return None


def bump_token_version(*, session: Session, user: User) -> None:
    """Invalidates every outstanding token for this user (all devices)."""
    user.token_version += 1
    session.add(user)
    session.commit()


def create_email_verification_token(user: User) -> str:
    expires = utc_now() + timedelta(minutes=settings.auth.verification_token_expiration)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires,
        "type": VERIFICATION_TOKEN_TYPE,
    }
    return jwt.encode(
        payload,
        settings.auth.secret_key.get_secret_value(),
        algorithm=settings.auth.algorithm,
    )


def verify_email_token(*, session: Session, token: str) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key.get_secret_value(),
            algorithms=[settings.auth.algorithm],
        )

        if payload.get("type") != VERIFICATION_TOKEN_TYPE:
            raise ValueError("Unexpected token type")

        subject = payload.get("sub")

        if subject is None:
            raise ValueError("Token subject is missing")

        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as exc:
        raise InvalidOrExpiredTokenError from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active or user.email != payload.get("email"):
        raise InvalidOrExpiredTokenError

    return user


def confirm_email_verification(*, session: Session, token: str) -> User:
    user = verify_email_token(session=session, token=token)

    if not user.email_verified:
        user.email_verified = True
        session.add(user)
        session.commit()
        session.refresh(user)

    return user


def _build_verification_email_html(*, first_name: str, link: str) -> str:
    logo_url = f"{settings.brevo.app_base_url}/logo-email.png"
    return f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="color-scheme" content="light dark" />
        <meta name="supported-color-schemes" content="light dark" />
        <style>
          body {{ background-color: #edf7ff; }}
          .email-card {{ background-color: #ffffff; border-color: #d8ecff; }}
          .email-header {{ background-color: #ffffff; border-color: #edf7ff; }}
          .email-title {{ color: #0f172a; }}
          .email-body {{ color: #334155; }}
          .email-footnote {{ color: #64748b; }}
          .email-link {{ color: #2c8ad7; }}

          @media (prefers-color-scheme: dark) {{
            body {{ background-color: #0f172a !important; }}
            .email-card {{ background-color: #1e293b !important; border-color: #334155 !important; }}
            .email-header {{ background-color: #1e293b !important; border-color: #334155 !important; }}
            .email-title {{ color: #f8fafc !important; }}
            .email-body {{ color: #cbd5e1 !important; }}
            .email-footnote {{ color: #94a3b8 !important; }}
            .email-link {{ color: #5ea7e3 !important; }}
          }}
        </style>
      </head>
      <body style="margin: 0; padding: 0; background-color: #edf7ff;">
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    padding: 32px 16px;">
          <div class="email-card"
               style="max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 12px;
                      overflow: hidden; border: 1px solid #d8ecff;">
            <div class="email-header"
                 style="background-color: #ffffff; padding: 24px 32px; border-bottom: 1px solid #edf7ff;">
              <img src="{logo_url}" alt="Strumok" width="120" height="38"
                   style="display: block; height: 38px; width: auto;" />
            </div>
            <div style="padding: 32px;">
              <p class="email-title" style="margin: 0 0 16px; font-size: 16px; color: #0f172a;">
                Hi {first_name},
              </p>
              <p class="email-body" style="margin: 0 0 24px; font-size: 15px; line-height: 1.5; color: #334155;">
                Please confirm your email address to finish setting up your Strumok account.
              </p>
              <p style="margin: 0 0 24px;">
                <a href="{link}"
                   style="display: inline-block; padding: 12px 24px; background-color: #2c8ad7;
                          color: #ffffff; text-decoration: none; border-radius: 8px;
                          font-size: 15px; font-weight: 600;">
                  Verify email
                </a>
              </p>
              <p class="email-footnote" style="margin: 0; font-size: 13px; line-height: 1.5; color: #64748b;">
                If the button doesn't work, copy and paste this link into your browser:<br />
                <a href="{link}" class="email-link" style="color: #2c8ad7;">{link}</a>
              </p>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def request_email_verification_link(*, session: Session, user: User) -> None:
    cooldown_seconds = settings.auth.verify_email_resend_cooldown_seconds
    now = utc_now()
    last_sent_at = user.verification_email_last_sent_at

    if last_sent_at is not None:
        elapsed_seconds = int((now - last_sent_at).total_seconds())
        remaining_seconds = cooldown_seconds - elapsed_seconds

        if remaining_seconds > 0:
            raise VerificationEmailRateLimitError(retry_after_seconds=remaining_seconds)

    token = create_email_verification_token(user)
    link = f"{settings.brevo.app_base_url}/verify-email?token={token}"
    try:
        send_email(
            to_email=user.email,
            to_name=user.first_name,
            subject="Verify your Strumok email",
            html_content=_build_verification_email_html(
                first_name=user.first_name, link=link
            ),
        )
    except EmailSendError as exc:
        raise VerificationEmailSendFailedError from exc

    user.verification_email_last_sent_at = now
    session.add(user)
    session.commit()
