from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from sqlmodel import Session

from app.api.auth.service import InvalidOrExpiredTokenError, get_user_from_token
from app.core.config import settings
from app.db.engine import get_session
from app.db.models import User

cookie_scheme = APIKeyCookie(name=settings.auth.auth_cookie_name, auto_error=False)

AUTH_CHALLENGE_HEADERS = {"WWW-Authenticate": "Bearer"}
INVALID_OR_EXPIRED_TOKEN_ERROR_CODE = "invalidOrExpiredToken"
MISSING_AUTHENTICATION_TOKEN_ERROR_CODE = "missingAuthenticationToken"


def get_current_user_from_token(*, session: Session, token: str) -> User:
    try:
        return get_user_from_token(session=session, token=token)
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_OR_EXPIRED_TOKEN_ERROR_CODE,
            headers=AUTH_CHALLENGE_HEADERS,
        ) from exc


def get_current_user(
    access_token: str | None = Depends(cookie_scheme),
    session: Session = Depends(get_session),
) -> User:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_AUTHENTICATION_TOKEN_ERROR_CODE,
            headers=AUTH_CHALLENGE_HEADERS,
        )

    return get_current_user_from_token(session=session, token=access_token)
