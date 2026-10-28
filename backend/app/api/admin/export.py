import csv
import io
import json
from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlmodel import Session, col, select

from app.db.models import AuditLog, Household, Payment, User

CsvFormat = Literal["standard", "ua"]

BOM = "﻿"


def _cell(value: Any, fmt: CsvFormat) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        text = format(value, "f")
        return text.replace(".", ",") if fmt == "ua" else text
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def render_csv(
    header: Sequence[str], rows: Iterable[Sequence[Any]], fmt: CsvFormat
) -> str:
    """UTF-8 BOM so Excel reads Cyrillic; `ua` uses `;` and decimal commas."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";" if fmt == "ua" else ",")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(value, fmt) for value in row])
    return BOM + buffer.getvalue()


def payment_rows(
    *, session: Session, date_from: date | None, date_to: date | None
) -> list[tuple[Payment, str]]:
    query = select(Payment, Household.name).join(
        Household, col(Household.id) == col(Payment.household_id)
    )
    if date_from is not None:
        query = query.where(Payment.paid_on >= date_from)
    if date_to is not None:
        query = query.where(Payment.paid_on <= date_to)
    return [
        (payment, name)
        for payment, name in session.exec(
            query.order_by(col(Payment.paid_on), col(Payment.id))
        )
    ]


def audit_rows(
    *, session: Session, date_from: date | None, date_to: date | None
) -> list[tuple[AuditLog, User | None]]:
    query = select(AuditLog, User).join(
        User, col(User.id) == col(AuditLog.actor_user_id), isouter=True
    )
    if date_from is not None:
        query = query.where(
            col(AuditLog.created_at) >= datetime.combine(date_from, time.min)
        )
    if date_to is not None:
        query = query.where(
            col(AuditLog.created_at)
            < datetime.combine(date_to + timedelta(days=1), time.min)
        )
    return list(session.exec(query.order_by(col(AuditLog.id))))
