from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.api.auth.service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    login_user,
    register_user,
)
from app.db.engine import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, session: Session = Depends(get_session)) -> UserOut:
    try:
        user = register_user(
            session=session,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
        )

        return UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_admin=user.is_admin,
            is_active=user.is_active,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = Depends(get_session)) -> TokenOut:
    try:
        token = login_user(
            session=session, email=payload.email, password=payload.password
        )
        return TokenOut(access_token=token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
