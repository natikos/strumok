from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class EmailAlreadyRegisteredError(Exception):
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
