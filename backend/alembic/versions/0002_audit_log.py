"""audit_log: append-only record of money- and ownership-affecting actions

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.db.models import AUDIT_LOG_APPEND_ONLY_SQL

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("household_id", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_household_id", "audit_log", ["household_id"])
    op.create_index("ix_audit_log_period", "audit_log", ["period"])
    # exec_driver_sql: the function body contains ":" and "%" that text() would
    # treat as bind parameters.
    op.get_bind().exec_driver_sql(AUDIT_LOG_APPEND_ONLY_SQL)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.get_bind().exec_driver_sql("DROP FUNCTION IF EXISTS audit_log_reject_change()")
