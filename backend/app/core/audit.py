from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session

from app.db.models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def record(
    session: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    household_id: int | None = None,
    period: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    """Adds an audit row to the caller's transaction without committing, so the
    action and its audit entry commit or roll back together. `actor_user_id` is
    None for system actions."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        household_id=household_id,
        period=period,
        before=_jsonable(before),
        after=_jsonable(after),
        reason=reason,
    )
    session.add(entry)
    return entry
