"""period_restatements and append-only charge_adjustments

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.db.models import CHARGE_ADJUSTMENTS_APPEND_ONLY_SQL

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "period_restatements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["period"], ["billing_periods.period"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_period_restatements_period", "period_restatements", ["period"])
    op.create_table(
        "charge_adjustments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("applies_to_period", sa.String(length=7), nullable=False),
        sa.Column("posted_in_period", sa.String(length=7), nullable=False),
        sa.Column("amount_uah", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason_code", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("restatement_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason_code IN ('rateCorrection', 'readingCorrection', 'billCorrection', 'manual')",
            name="ck_charge_adjustments_reason_code",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["applies_to_period"], ["billing_periods.period"]),
        sa.ForeignKeyConstraint(["posted_in_period"], ["billing_periods.period"]),
        sa.ForeignKeyConstraint(["restatement_id"], ["period_restatements.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "household_id",
        "applies_to_period",
        "posted_in_period",
        "restatement_id",
    ):
        op.create_index(
            f"ix_charge_adjustments_{column}", "charge_adjustments", [column]
        )
    op.get_bind().exec_driver_sql(CHARGE_ADJUSTMENTS_APPEND_ONLY_SQL)


def downgrade() -> None:
    op.drop_table("charge_adjustments")
    op.get_bind().exec_driver_sql(
        "DROP FUNCTION IF EXISTS charge_adjustments_reject_change()"
    )
    op.drop_table("period_restatements")
