from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.api.auth.schemas import ErrorOut, LoginIn, RegisterIn, UserOut
from app.api.auth.service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    login_user,
    register_user,
)
from app.api.deps import get_current_user, get_current_user_from_token
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
        token = login_user(
            session=session,
            email=payload.email,
            password=payload.password,
        )
        response.set_cookie(
            key=settings.auth.auth_cookie_name,
            value=token,
            httponly=True,
            max_age=settings.auth_token_ttl_seconds,
            samesite="lax",
            secure=settings.auth_cookie_secure,
        )

        return UserOut(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
        )
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
        token = login_user(
            session=session, email=payload.email, password=payload.password
        )
        user = get_current_user_from_token(session=session, token=token)
        response.set_cookie(
            key=settings.auth.auth_cookie_name,
            value=token,
            httponly=True,
            max_age=settings.auth_token_ttl_seconds,
            samesite="lax",
            secure=settings.auth_cookie_secure,
        )

        return UserOut(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidCredentials",
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(key=settings.auth.auth_cookie_name, samesite="lax")
    return response


@router.get("/me", response_model=UserOut, responses=ME_RESPONSES)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
    )
