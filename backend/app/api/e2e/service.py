"""State the Playwright suite sets up between tests. Mounted only when
ENVIRONMENT=e2e, which config refuses unless the database is a local `*_e2e`
one (docs/testing.md)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlmodel import Session, SQLModel

from app.api.auth.service import pwd_context
from app.api.push.service import e2e_push_outbox
from app.core import email
from app.core.time import now_utc_aware, set_clock_offset
from app.db.models import LanguageCode, User


def set_clock(now: datetime) -> datetime:
    """Shifts the app clock so it reads `now` at this instant; it keeps
    running at real speed afterwards, like the browser's under page.clock."""
    set_clock_offset(now - datetime.now(timezone.utc))
    return now_utc_aware()


def reset_clock() -> None:
    set_clock_offset(timedelta(0))


def reset(session: Session) -> None:
    """Empties every table (TRUNCATE skips the row-level append-only
    triggers), restarts ids so `STR-<id>` references are predictable, and
    clears the outbox and clock."""
    tables = ", ".join(table.name for table in SQLModel.metadata.sorted_tables)
    session.exec(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # type: ignore[call-overload]
    session.commit()
    email.e2e_outbox.clear()
    e2e_push_outbox.clear()
    reset_clock()


def create_user(
    session: Session,
    *,
    email_address: str,
    password: str,
    first_name: str,
    last_name: str,
    is_admin: bool,
    language: LanguageCode,
) -> User:
    """An active, verified user with a password. Sign-up is closed and invites
    need an admin, so this is how a run gets its first admin."""
    user = User(
        email=email_address.strip().lower(),
        first_name=first_name,
        last_name=last_name,
        password_hash=pwd_context.hash(password),
        is_admin=is_admin,
        email_verified=True,
        language=language,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def outbox(to: str | None) -> list[dict[str, str]]:
    if to is None:
        return list(email.e2e_outbox)
    wanted = to.strip().lower()
    return [message for message in email.e2e_outbox if message["to"].lower() == wanted]
