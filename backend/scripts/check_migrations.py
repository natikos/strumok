"""Fail unless the database has every Alembic migration bundled in this checkout.

Read-only: only SELECTs from ``alembic_version``. Used by the deployment
preflight and the /deploy command.

    PROD_DATABASE_URL=... uv run python scripts/check_migrations.py

Migration files import the app, so the usual app settings (AUTH_SECRET_KEY,
PUSH_VAPID_*, ENVIRONMENT, DATABASE_URL) must be set to something; only
``PROD_DATABASE_URL`` is connected to.
"""

import os
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def missing_revisions(applied: str | None, script: ScriptDirectory) -> list[str]:
    """Revisions bundled in the code that sit after ``applied`` (oldest first)."""
    head = script.get_current_head()
    if head is None:
        return []
    revs = [r.revision for r in script.iterate_revisions(head, applied or "base")]
    if applied and applied in revs:
        revs.remove(applied)
    return list(reversed(revs))


def main() -> int:
    url = os.environ.get("PROD_DATABASE_URL")
    if not url:
        print("PROD_DATABASE_URL is not set", file=sys.stderr)
        return 2
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    engine = sa.create_engine(
        url,
        connect_args={
            "connect_timeout": 10,
            "options": "-c default_transaction_read_only=on",
        },
    )
    with engine.connect() as conn:
        applied = conn.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
    known = {r.revision for r in script.walk_revisions()}
    if applied is not None and applied not in known:
        print(f"Production is at {applied}, which this checkout does not know.")
        return 1
    missing = missing_revisions(applied, script)
    if missing:
        print(f"Production is at {applied}; unapplied migrations: {', '.join(missing)}")
        return 1
    print(f"Migrations up to date at {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
