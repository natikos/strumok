import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

from app.core.config import settings
from app.db import models  # noqa: F401  # ensure model metadata is registered

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"

engine = create_engine(
    settings.db.url,
    echo=False,
    hide_parameters=True,
    poolclass=NullPool,
    connect_args={"client_encoding": "utf8", "prepare_threshold": None},  # noqa: E501
)

# Separate engine so the probe's short connect timeout doesn't apply to normal requests.
probe_engine = create_engine(
    settings.db.url,
    echo=False,
    poolclass=NullPool,
    connect_args={"connect_timeout": 3},
)


def init_db() -> None:
    """Check the schema is at the newest migration; apply with `alembic upgrade head`."""
    head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        return
    logger.error("schemaOutdated: database at %s, expected %s", current, head)
    # e2e fails too, so a missing migration fails the suite instead of logging.
    if settings.environment in ("production", "e2e"):
        raise RuntimeError("schemaOutdated")


def get_session():
    with Session(engine) as session:
        yield session


def is_db_reachable() -> bool:
    try:
        with probe_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
