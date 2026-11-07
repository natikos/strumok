"""block TRUNCATE on append-only tables

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-07 12:00:00

"""

from typing import Sequence, Union

from alembic import op

from app.db.models import (
    APPEND_ONLY_TABLES,
    APPEND_ONLY_TRUNCATE_GUARD_FN_SQL,
    truncate_guard_trigger_sql,
)


# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(APPEND_ONLY_TRUNCATE_GUARD_FN_SQL)
    for table in APPEND_ONLY_TABLES:
        op.execute(truncate_guard_trigger_sql(table))


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table}")
    op.execute("DROP FUNCTION IF EXISTS append_only_reject_truncate()")
