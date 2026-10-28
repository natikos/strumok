from alembic import context
from sqlmodel import SQLModel

from app.db import models  # noqa: F401  # register tables on SQLModel.metadata
from app.db.engine import engine

target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            # Transaction-level lock: the engine may sit behind a
            # transaction-mode pooler, where a session lock would not hold.
            context.get_bind().exec_driver_sql("SELECT pg_advisory_xact_lock(7140001)")
            context.run_migrations()


run_migrations_online()
