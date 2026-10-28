"""payment_details: the co-op's IBAN and recipient

Revision ID: 0012
Revises: 0011
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("iban", sa.String(), nullable=False),
        sa.Column("recipient_name", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_payment_details_single"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("payment_details")
