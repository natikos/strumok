from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db import models  # noqa: F401  # ensure model metadata is registered

engine = create_engine(settings.db.url)


def init_db() -> None:
    if settings.environment == "development":
        SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
