from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.auth.schemas import (
    ErrorOut,
    LoginIn,
    RegisterIn,
    UserOut,
    UserPreferencesIn,
)
from app.api.auth.service import (
    InvalidOrExpiredTokenError,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    create_access_token,
    get_user_from_token,
    register_user,
)
from app.api.deps import get_current_user
from app.api.deps.auth import AUTH_CHALLENGE_HEADERS
from app.core.config import settings
from app.db import get_session
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

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
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Invalid credentials",
        "model": ErrorOut,
        "content": {
            "application/json": {
                "example": {"detail": "invalidCredentials"},
            }
        },
    }
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

def set_auth_cookie(response: Response, *, user: User) -> None:
    response.set_cookie(
        key=settings.auth.auth_cookie_name,
        value=create_access_token(user),
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
        set_auth_cookie(response, user=user)

        return UserOut.from_user(user)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="emailAlreadyRegistered",
        ) from exc


@router.post("/login", response_model=UserOut, responses=LOGIN_RESPONSES)
def login(
    payload: LoginIn,
    response: Response,
    session: Session = Depends(get_session),
) -> UserOut:
    try:
        user = authenticate_user(session=session, email=payload.email, password=payload.password)
        set_auth_cookie(response, user=user)

        return UserOut.from_user(user)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidCredentials",
        ) from exc


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(
    response: Response,
    access_token: str | None = Cookie(default=None, alias=settings.auth.auth_cookie_name),
    session: Session = Depends(get_session),
) -> Response:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missingAuthenticationToken",
            headers=AUTH_CHALLENGE_HEADERS,
        )

    try:
        user = get_user_from_token(
            session=session,
            token=access_token,
            verify_expiration=False,
        )
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidOrExpiredToken",
            headers=AUTH_CHALLENGE_HEADERS,
        ) from exc

    set_auth_cookie(response, user=user)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(key=settings.auth.auth_cookie_name, samesite="lax")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut, responses=ME_RESPONSES)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(current_user)


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
