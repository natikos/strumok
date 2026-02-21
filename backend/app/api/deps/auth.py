from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.api.auth.service import InvalidOrExpiredTokenError, get_user_from_token
from app.core.config import settings
from app.db.engine import get_session
from app.db.models import User

http_bearer = HTTPBearer(auto_error=False)

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
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    access_token: str | None = Cookie(
        default=None, alias=settings.auth.auth_cookie_name
    ),
    session: Session = Depends(get_session),
) -> User:
    token = credentials.credentials if credentials is not None else access_token

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MISSING_AUTHENTICATION_TOKEN_ERROR_CODE,
            headers=AUTH_CHALLENGE_HEADERS,
        )

    return get_current_user_from_token(session=session, token=token)
