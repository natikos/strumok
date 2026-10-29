import logging
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api.auth.schemas import (
    ChangeEmailIn,
    ChangePasswordIn,
    ErrorOut,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    UserOut,
    UserPreferencesIn,
    UserWithHouseholdsOut,
    VerifyEmailIn,
)
from app.api.auth.service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidOrExpiredTokenError,
    VerificationEmailRateLimitError,
    VerificationEmailSendFailedError,
    authenticate_user,
    bump_token_version,
    change_password,
    confirm_email_change,
    confirm_email_verification,
    confirm_password_reset,
    create_access_token,
    get_user_id_and_version_for_logout,
    has_past_households,
    list_user_households,
    refresh_access_token,
    request_email_change,
    request_email_verification_link,
    request_password_reset,
)
from app.api.auth.throttle import (
    ACCOUNT_CHANGE_LIMIT,
    LOGIN_EMAIL_LIMIT,
    LOGIN_IP_LIMIT,
    RESET_EMAIL_LIMIT,
    RESET_IP_LIMIT,
    TooManyAttemptsError,
    check_not_throttled,
    record_failure,
)
from app.api.deps import get_current_user
from app.api.deps.auth import AUTH_CHALLENGE_HEADERS
from app.core.config import settings
from app.db import get_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

REGISTER_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "description": "Email is already registered",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "emailAlreadyRegistered"},
            }
        },
    }
}

LOGIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Too many failed attempts; see Retry-After",
        "model": ErrorOut,
        "headers": {
            "Retry-After": {
                "description": "Seconds until the next attempt is allowed",
                "schema": {"type": "integer"},
            }
        },
        "content": {
            "application/json": {
                "example": {"detail": "tooManyAttempts"},
            }
        },
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Invalid credentials",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "invalidCredentials"},
            }
        },
    },
}

ME_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication failed",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "examples": {
                    "missingAuthenticationToken": {
                        "summary": "No auth token provided",
                        "value": {"detail": "missingAuthenticationToken"},
                    },
                    "invalidOrExpiredToken": {
                        "summary": "Token is invalid or expired",
                        "value": {"detail": "invalidOrExpiredToken"},
                    },
                },
            }
        },
    }
}


VERIFICATION_LINK_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Verification email cooldown is active",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "verificationEmailCooldown"},
            }
        },
    },
    status.HTTP_502_BAD_GATEWAY: {
        "description": "Verification email could not be sent",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "verificationEmailSendFailed"},
            }
        },
    },
}

VERIFY_EMAIL_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "description": "Verification token is invalid or expired",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "invalidOrExpiredToken"},
            }
        },
    }
}


def set_auth_cookie(response: Response, *, token: str) -> None:
    response.set_cookie(
        key=settings.auth.auth_cookie_name,
        value=token,
        httponly=True,
        max_age=settings.auth_token_ttl_seconds,
        samesite="lax",
        secure=settings.auth_cookie_secure,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth.auth_cookie_name,
        samesite="lax",
        secure=settings.auth_cookie_secure,
    )


@router.post(
    "/register",
    status_code=status.HTTP_403_FORBIDDEN,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Self-registration is closed; the head invites residents",
            "model": ErrorOut,
            "content": {
                "application/json": {"example": {"detail": "registrationClosed"}}
            },
        }
    },
)
def register() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="registrationClosed"
    )


@router.post("/login", response_model=UserOut, responses=LOGIN_RESPONSES)
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    email_key = f"login:email:{payload.email.strip().lower()}"
    ip_key = f"login:ip:{request.client.host if request.client else 'unknown'}"

    try:
        check_not_throttled(session=session, key=email_key, limit=LOGIN_EMAIL_LIMIT)
        check_not_throttled(session=session, key=ip_key, limit=LOGIN_IP_LIMIT)
    except TooManyAttemptsError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="tooManyAttempts",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    try:
        user = authenticate_user(
            session=session, email=payload.email, password=payload.password
        )
        set_auth_cookie(response, token=create_access_token(user))

        return UserOut.from_user(user)
    except InvalidCredentialsError as exc:
        record_failure(session=session, key=email_key, limit=LOGIN_EMAIL_LIMIT)
        record_failure(session=session, key=ip_key, limit=LOGIN_IP_LIMIT)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidCredentials",
        ) from exc


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(
    response: Response,
    access_token: str | None = Cookie(
        default=None, alias=settings.auth.auth_cookie_name
    ),
    session: Session = Depends(get_session),
) -> Response:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missingAuthenticationToken",
            headers=AUTH_CHALLENGE_HEADERS,
        )

    try:
        new_token = refresh_access_token(session=session, token=access_token)
    except InvalidOrExpiredTokenError:
        # HTTPException would drop cookies set on `response`, so build the
        # 401 directly to clear the dead cookie in the same reply.
        rejected = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "invalidOrExpiredToken"},
            headers=AUTH_CHALLENGE_HEADERS,
        )
        clear_auth_cookie(rejected)
        return rejected

    set_auth_cookie(response, token=new_token)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    access_token: str | None = Cookie(
        default=None, alias=settings.auth.auth_cookie_name
    ),
    session: Session = Depends(get_session),
) -> Response:
    if access_token is not None:
        identity = get_user_id_and_version_for_logout(access_token)
        if identity is not None:
            user_id, token_version = identity
            user = session.get(User, user_id)
            # Ignore tokens that are already revoked (version doesn't match).
            # Otherwise someone holding an old stolen cookie could keep
            # calling /auth/logout and log the user out of every new session.
            if user is not None and token_version == user.token_version:
                bump_token_version(session=session, user=user)

    clear_auth_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserWithHouseholdsOut, responses=ME_RESPONSES)
def me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserWithHouseholdsOut:
    households = list_user_households(session=session, user=current_user)
    return UserWithHouseholdsOut.from_user_with_households(
        current_user,
        households=households,
        has_past_households=has_past_households(session=session, user=current_user),
    )


@router.patch("/preferences", response_model=UserOut)
def update_preferences(
    payload: UserPreferencesIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserOut:
    if payload.theme is not None:
        current_user.theme = payload.theme

    if payload.language is not None:
        current_user.language = payload.language

    if payload.reminder_hour is not None:
        current_user.reminder_hour = payload.reminder_hour

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return UserOut.from_user(current_user)


@router.post(
    "/verification-link",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=VERIFICATION_LINK_RESPONSES,
)
def send_verification_link(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    if current_user.email_verified:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        request_email_verification_link(session=session, user=current_user)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except VerificationEmailRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="verificationEmailCooldown",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except VerificationEmailSendFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="verificationEmailSendFailed",
        ) from exc


@router.post(
    "/verify-email",
    response_model=UserOut,
    responses=VERIFY_EMAIL_RESPONSES,
)
def verify_email(
    payload: VerifyEmailIn,
    session: Session = Depends(get_session),
) -> UserOut:
    try:
        user = confirm_email_verification(session=session, token=payload.token)
        return UserOut.from_user(user)
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalidOrExpiredToken",
        ) from exc


ACCOUNT_CHANGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {
        "description": "Current password is wrong",
        "model": ErrorOut,
        "content": {"application/json": {"example": {"detail": "invalidCredentials"}}},
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Too many wrong passwords; see Retry-After",
        "model": ErrorOut,
        "headers": {
            "Retry-After": {
                "description": "Seconds until the next attempt is allowed",
                "schema": {"type": "integer"},
            }
        },
        "content": {"application/json": {"example": {"detail": "tooManyAttempts"}}},
    },
}


def _guard_account_change(*, session: Session, user: User) -> str:
    key = f"account:user:{user.id}"
    try:
        check_not_throttled(session=session, key=key, limit=ACCOUNT_CHANGE_LIMIT)
    except TooManyAttemptsError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="tooManyAttempts",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return key


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCOUNT_CHANGE_RESPONSES,
)
def update_password(
    payload: ChangePasswordIn,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    key = _guard_account_change(session=session, user=current_user)
    try:
        change_password(
            session=session,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidCredentialsError as exc:
        record_failure(session=session, key=key, limit=ACCOUNT_CHANGE_LIMIT)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalidCredentials"
        ) from exc

    set_auth_cookie(response, token=create_access_token(current_user))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/email",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **ACCOUNT_CHANGE_RESPONSES,
        status.HTTP_409_CONFLICT: REGISTER_RESPONSES[status.HTTP_409_CONFLICT],
        status.HTTP_502_BAD_GATEWAY: VERIFICATION_LINK_RESPONSES[
            status.HTTP_502_BAD_GATEWAY
        ],
    },
)
def update_email(
    payload: ChangeEmailIn,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    key = _guard_account_change(session=session, user=current_user)
    try:
        request_email_change(
            session=session,
            user=current_user,
            current_password=payload.current_password,
            new_email=payload.new_email,
        )
    except InvalidCredentialsError as exc:
        record_failure(session=session, key=key, limit=ACCOUNT_CHANGE_LIMIT)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalidCredentials"
        ) from exc
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="emailAlreadyRegistered"
        ) from exc
    except VerificationEmailSendFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="verificationEmailSendFailed",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/confirm-email-change",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=VERIFY_EMAIL_RESPONSES,
)
def confirm_email_change_route(
    payload: VerifyEmailIn,
    session: Session = Depends(get_session),
) -> Response:
    try:
        confirm_email_change(session=session, token=payload.token)
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalidOrExpiredToken"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_request(
    payload: PasswordResetRequestIn,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """Always 204, throttled or not, so nothing reveals which emails exist."""
    email_key = f"reset:email:{payload.email.strip().lower()}"
    ip_key = f"reset:ip:{request.client.host if request.client else 'unknown'}"

    try:
        check_not_throttled(session=session, key=email_key, limit=RESET_EMAIL_LIMIT)
        check_not_throttled(session=session, key=ip_key, limit=RESET_IP_LIMIT)
    except TooManyAttemptsError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    record_failure(session=session, key=email_key, limit=RESET_EMAIL_LIMIT)
    record_failure(session=session, key=ip_key, limit=RESET_IP_LIMIT)
    request_password_reset(session=session, email=payload.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password-reset/confirm",
    response_model=UserOut,
    responses=VERIFY_EMAIL_RESPONSES,
)
def password_reset_confirm(
    payload: PasswordResetConfirmIn,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    """Also the set-password step of an invite. Signs the user in: they just
    proved ownership of the inbox."""
    try:
        user = confirm_password_reset(
            session=session, token=payload.token, password=payload.password
        )
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalidOrExpiredToken"
        ) from exc
    set_auth_cookie(response, token=create_access_token(user))
    return UserOut.from_user(user)
