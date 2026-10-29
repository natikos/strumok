"""meter_readings: corrected_at and correction_reason

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meter_readings", sa.Column("corrected_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "meter_readings", sa.Column("correction_reason", sa.String(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("meter_readings", "correction_reason")
    op.drop_column("meter_readings", "corrected_at")
