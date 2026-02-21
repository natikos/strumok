from datetime import timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.time import utc_now
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidOrExpiredTokenError(Exception):
    pass


def create_access_token(user: User) -> str:
    expires = utc_now() + timedelta(minutes=settings.auth.access_token_expiration)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def authenticate_user(*, session: Session, email: str, password: str) -> User:
    user = session.exec(
        select(User).where(User.email == email.strip().lower(), User.is_active)
    ).first()

    if user is None or not pwd_context.verify(password, user.password_hash):
        raise InvalidCredentialsError

    return user


def get_user_from_token(
    *,
    session: Session,
    token: str,
    verify_expiration: bool = True,
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
            options={"verify_exp": verify_expiration},
        )
        subject = payload.get("sub")

        if subject is None:
            raise ValueError("Token subject is missing")

        user_id = int(subject)
    except (JWTError, ValueError, TypeError) as exc:
        raise InvalidOrExpiredTokenError from exc

    user = session.get(User, user_id)

    if user is None or not user.is_active:
        raise InvalidOrExpiredTokenError

    return user


def register_user(
    *,
    session: Session,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
) -> User:
    user = User(
        email=email.strip().lower(),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        password_hash=pwd_context.hash(password),
    )

    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailAlreadyRegisteredError from exc

    session.refresh(user)

    return user


def login_user(*, session: Session, email: str, password: str) -> str:
    user = authenticate_user(session=session, email=email, password=password)
    return create_access_token(user)
