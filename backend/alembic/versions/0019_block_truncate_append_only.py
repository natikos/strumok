"""block_truncate_append_only

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-29 21:00:00.000000

Row-level append-only triggers don't fire for TRUNCATE, so one statement could
still wipe the ledger or audit trail.
"""

from typing import Sequence, Union

from alembic import op

from app.db.models import APPEND_ONLY_TABLES, no_truncate_sql


# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    for table in APPEND_ONLY_TABLES:
        connection.exec_driver_sql(no_truncate_sql(table))


def downgrade() -> None:
    """Downgrade schema."""
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER {table}_no_truncate ON {table}")
