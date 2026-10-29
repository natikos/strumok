"""meter_segments: meter replacements

Revision ID: 0010
Revises: 0009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meter_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("old_final_day", sa.Numeric(12, 2), nullable=False),
        sa.Column("old_final_night", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_start_day", sa.Numeric(12, 2), nullable=False),
        sa.Column("new_start_night", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "period", name="uq_meter_segment_period"),
    )
    op.create_index(
        op.f("ix_meter_segments_household_id"), "meter_segments", ["household_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_meter_segments_household_id"), table_name="meter_segments")
    op.drop_table("meter_segments")
