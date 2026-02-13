from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.api.auth.schemas import RegisterIn, UserOut
from app.api.auth.service import (
    EmailAlreadyRegisteredError,
    register_user,
)
from app.db.engine import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class PasswordLengthCheckIn(BaseModel):
    password: str


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, session: Session = Depends(get_session)):
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


@router.post("/login")
def login_stub() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Auth login is not implemented yet",
    )
