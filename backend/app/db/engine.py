from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db import models  # noqa: F401  # ensure model metadata is registered

engine = create_engine(
    settings.db.url,
    echo=False,
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
    if settings.environment == "development":
        SQLModel.metadata.create_all(engine)


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
