"""Recreate the Playwright suite's database and migrate it to head.

Run by the Playwright webServer before uvicorn starts (frontend/playwright.config.ts),
with the same environment as the server, ENVIRONMENT=e2e included:

    ENVIRONMENT=e2e DATABASE_URL=postgresql://...@localhost/strumok_e2e \\
        uv run python scripts/e2e_prepare_db.py

Destructive: drops the database first. Refuses anything but a local database
whose name ends in ``_e2e`` (the same rule ENVIRONMENT=e2e enforces at startup),
and fails if the frontend hasn't been built into ``backend/dist``, since the
app then serves no pages at all.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
DIST_INDEX = BACKEND_DIR / "dist" / "index.html"


def main() -> int:
    # Importing settings already refuses a non-e2e database under ENVIRONMENT=e2e;
    # the explicit check also covers a run where ENVIRONMENT was left out.
    from app.core.config import is_e2e_database, settings

    if settings.environment != "e2e" or not is_e2e_database(settings.db.url):
        print(
            "Refusing: needs ENVIRONMENT=e2e and a local *_e2e DATABASE_URL",
            file=sys.stderr,
        )
        return 2
    if not DIST_INDEX.is_file():
        print(
            f"{DIST_INDEX} is missing: run `bun run build` in frontend/ first",
            file=sys.stderr,
        )
        return 2

    url = make_url(settings.db.url)
    name = url.database
    maintenance = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with maintenance.connect() as conn:
        # Evict a previous run's server still attached, or DROP DATABASE blocks.
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    maintenance.dispose()

    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    print(f"Prepared {name} at head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
