import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session

from app.db.models import APPEND_ONLY_TABLES


@pytest.fixture
def conn_session(engine):
    with Session(engine) as db:
        yield db
        db.rollback()


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_truncate_rejected(conn_session, table):
    with pytest.raises(DBAPIError, match="append-only"):
        conn_session.exec(text(f"TRUNCATE {table}"))  # type: ignore[call-overload]


def test_truncate_cascade_from_parent_rejected(conn_session):
    with pytest.raises(DBAPIError, match="append-only"):
        conn_session.exec(text("TRUNCATE households CASCADE"))  # type: ignore[call-overload]


def test_opt_out_is_transaction_local(conn_session):
    conn_session.exec(text("SET LOCAL strumok.allow_truncate = 'on'"))  # type: ignore[call-overload]
    conn_session.exec(text("TRUNCATE audit_log"))  # type: ignore[call-overload]
    conn_session.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        conn_session.exec(text("TRUNCATE audit_log"))  # type: ignore[call-overload]
