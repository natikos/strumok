"""opening_balances: debt or credit carried over from the spreadsheets

Revision ID: 0014
Revises: 0013
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opening_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("amount_uah", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_opening_balances_household"),
    )
    op.create_index(
        op.f("ix_opening_balances_household_id"),
        "opening_balances",
        ["household_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_opening_balances_household_id"), table_name="opening_balances"
    )
    op.drop_table("opening_balances")
