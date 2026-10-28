"""users.password_hash nullable: invited users have no password yet

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Fails while uninvited-yet-unaccepted users exist; remove them first.
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
