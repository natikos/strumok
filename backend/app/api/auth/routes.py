import logging
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from app.api.auth.schemas import (
    ErrorOut,
    LoginIn,
    RegisterIn,
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
    confirm_email_verification,
    create_access_token,
    get_user_id_and_version_for_logout,
    list_user_households,
    refresh_access_token,
    register_user,
    request_email_verification_link,
)
from app.api.auth.throttle import (
    LOGIN_EMAIL_LIMIT,
    LOGIN_IP_LIMIT,
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


@router.post(
    "/register",
    response_model=UserOut,
    responses=REGISTER_RESPONSES,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterIn,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    try:
        user = register_user(
            session=session,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password=payload.password,
        )
        set_auth_cookie(response, token=create_access_token(user))

        try:
            request_email_verification_link(session=session, user=user)
        except VerificationEmailSendFailedError:
            logger.exception("Verification email failed to send during registration")

        return UserOut.from_user(user)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="emailAlreadyRegistered",
        ) from exc


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
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidOrExpiredToken",
            headers=AUTH_CHALLENGE_HEADERS,
        ) from exc

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

    response.delete_cookie(
        key=settings.auth.auth_cookie_name,
        samesite="lax",
        secure=settings.auth_cookie_secure,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserWithHouseholdsOut, responses=ME_RESPONSES)
def me(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserWithHouseholdsOut:
    households = list_user_households(session=session, user=current_user)
    return UserWithHouseholdsOut.from_user_with_households(
        current_user, households=households
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
