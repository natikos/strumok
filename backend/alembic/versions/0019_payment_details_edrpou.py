"""payment_details_edrpou: the co-op's EDRPOU on its payment details

Revision ID: 0019
Revises: 0018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_details", sa.Column("edrpou", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_details", "edrpou")
