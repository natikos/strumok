from datetime import timedelta

from jose import jwt
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


def register_user(
    *, session: Session, email: str, full_name: str, password: str
) -> User:
    user = User(
        email=email.strip().lower(),
        full_name=full_name.strip(),
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
    user = session.exec(
        select(User).where(User.email == email.strip().lower(), User.is_active)
    ).first()

    if user is None or not pwd_context.verify(password, user.password_hash):
        raise InvalidCredentialsError

    expires = utc_now() + timedelta(minutes=settings.auth.access_token_expiration)
    payload = {"sub": str(user.id), "email": user.email, "exp": expires}
    return jwt.encode(
        payload, settings.auth.secret_key, algorithm=settings.auth.algorithm
    )
