import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyCookie
from sqlmodel import Session

from app.api.auth.service import InvalidOrExpiredTokenError, get_user_from_token
from app.core.config import settings
from app.db.engine import get_session
from app.db.models import User

cookie_scheme = APIKeyCookie(name=settings.auth.auth_cookie_name, auto_error=False)

AUTH_CHALLENGE_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_current_user_from_token(*, session: Session, token: str) -> User:
    try:
        return get_user_from_token(session=session, token=token)
    except InvalidOrExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidOrExpiredToken",
            headers=AUTH_CHALLENGE_HEADERS,
        ) from exc


def get_current_user(
    access_token: str | None = Depends(cookie_scheme),
    session: Session = Depends(get_session),
) -> User:
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missingAuthenticationToken",
            headers=AUTH_CHALLENGE_HEADERS,
        )

    return get_current_user_from_token(session=session, token=access_token)


def require_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> None:
    expected = settings.auth.internal_secret.get_secret_value()
    if not x_internal_secret or not secrets.compare_digest(x_internal_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalidInternalSecret",
        )


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="adminPrivilegesRequired",
        )
    return current_user
