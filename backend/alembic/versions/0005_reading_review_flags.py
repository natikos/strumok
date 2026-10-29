"""meter_readings review flags: needs_review, review_reason, reviewed_by/at

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meter_readings",
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "meter_readings", sa.Column("review_reason", sa.String(), nullable=True)
    )
    op.add_column(
        "meter_readings", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "meter_readings", sa.Column("reviewed_at", sa.DateTime(), nullable=True)
    )
    op.create_foreign_key(
        "fk_meter_readings_reviewed_by_user_id",
        "meter_readings",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_meter_readings_review_reason",
        "meter_readings",
        "review_reason IN ('decrease', 'spike')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_meter_readings_review_reason", "meter_readings", type_="check"
    )
    op.drop_constraint(
        "fk_meter_readings_reviewed_by_user_id", "meter_readings", type_="foreignkey"
    )
    op.drop_column("meter_readings", "reviewed_at")
    op.drop_column("meter_readings", "reviewed_by_user_id")
    op.drop_column("meter_readings", "review_reason")
    op.drop_column("meter_readings", "needs_review")
