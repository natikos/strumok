"""unique electricity_rates.effective_from

create_rate checks for an existing row and then inserts, so concurrent
requests could both pass the check; the constraint closes that race.
Fails if production already holds duplicates; resolve them first.

Revision ID: 0001
Revises: 0000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = "0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_electricity_rates_effective_from", table_name="electricity_rates")
    op.create_index(
        "ix_electricity_rates_effective_from",
        "electricity_rates",
        ["effective_from"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_electricity_rates_effective_from", table_name="electricity_rates")
    op.create_index(
        "ix_electricity_rates_effective_from",
        "electricity_rates",
        ["effective_from"],
        unique=False,
    )
