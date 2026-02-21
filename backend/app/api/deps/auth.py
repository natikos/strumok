from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.config import settings
from app.db.engine import get_session
from app.db.models import User

http_bearer = HTTPBearer(auto_error=False)

AUTH_CHALLENGE_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_current_user_from_token(*, session: Session, token: str) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )

        subject = payload.get("sub")

        if subject is None:
            raise ValueError("Token subject is missing")

        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=AUTH_CHALLENGE_HEADERS,
        ) from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers=AUTH_CHALLENGE_HEADERS,
        )

    return user


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
            detail="Missing authentication token",
            headers=AUTH_CHALLENGE_HEADERS,
        )

    return get_current_user_from_token(session=session, token=token)
