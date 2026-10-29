"""drop meter_readings usage and charge columns

Contract phase of the billing ledger (0004): usage is derived from consecutive
readings and charges live in household_charges, so the frozen copies on the
reading are gone.

Revision ID: 0013
Revises: 0012
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ("day_usage_kwh", "night_usage_kwh", "amount_charged_uah")


def upgrade() -> None:
    for column in COLUMNS:
        op.drop_column("meter_readings", column)


def downgrade() -> None:
    for column in COLUMNS:
        op.add_column(
            "meter_readings",
            sa.Column(
                column,
                sa.Numeric(12, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
