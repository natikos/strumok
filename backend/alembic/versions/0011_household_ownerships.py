"""household_ownerships: who owned a plot and when

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_ownerships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("handover_day_meter_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("handover_night_meter_value", sa.Numeric(12, 2), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_household_ownerships_household_id"),
        "household_ownerships",
        ["household_id"],
    )
    op.create_index(
        op.f("ix_household_ownerships_user_id"), "household_ownerships", ["user_id"]
    )
    op.create_index(
        "uq_household_open_ownership",
        "household_ownerships",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    # Current owners become the open ownership, held since the plot was created.
    op.execute(
        """
        INSERT INTO household_ownerships (household_id, user_id, valid_from)
        SELECT id, user_id, created_at FROM households WHERE user_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_household_open_ownership", table_name="household_ownerships")
    op.drop_index(
        op.f("ix_household_ownerships_user_id"), table_name="household_ownerships"
    )
    op.drop_index(
        op.f("ix_household_ownerships_household_id"), table_name="household_ownerships"
    )
    op.drop_table("household_ownerships")
