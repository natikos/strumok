from datetime import timedelta
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


def create_access_token(user: User) -> str:
    expires = utc_now() + timedelta(minutes=settings.auth.access_token_expiration)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(
        payload, settings.auth.secret_key, algorithm=settings.auth.algorithm
    )


def authenticate_user(*, session: Session, email: str, password: str) -> User:
    user = session.exec(
        select(User).where(User.email == email.strip().lower(), User.is_active)
    ).first()

    if user is None or not pwd_context.verify(password, user.password_hash):
        raise InvalidCredentialsError

    return user


def get_user_from_token(
    *,
    session: Session,
    token: str,
    verify_expiration: bool = True,
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
            options={"verify_exp": verify_expiration},
        )
        subject = payload.get("sub")

        if subject is None:
            raise ValueError("Token subject is missing")

        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as exc:
        raise InvalidOrExpiredTokenError from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidOrExpiredTokenError

    return user


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


def login_user(*, session: Session, email: str, password: str) -> str:
    user = authenticate_user(session=session, email=email, password=password)
    return create_access_token(user)


def create_email_verification_token(user: User) -> str:
    expires = utc_now() + timedelta(minutes=settings.auth.verification_token_expiration)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires,
        "type": VERIFICATION_TOKEN_TYPE,
    }
    return jwt.encode(
        payload, settings.auth.secret_key, algorithm=settings.auth.algorithm
    )


def verify_email_token(*, session: Session, token: str) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
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
    print(f"Settings: {settings.brevo}")
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
        print(f"Failed to send verification email to {user.email}: {exc}")
        raise VerificationEmailSendFailedError from exc

    user.verification_email_last_sent_at = now
    session.add(user)
    session.commit()
