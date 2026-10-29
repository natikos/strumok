"""zero_baseline_review_reason

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-29 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "ck_meter_readings_review_reason", "meter_readings", type_="check"
    )
    op.create_check_constraint(
        "ck_meter_readings_review_reason",
        "meter_readings",
        "review_reason IN ('decrease', 'spike', 'zeroBaseline')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE meter_readings SET review_reason = NULL "
        "WHERE review_reason = 'zeroBaseline'"
    )
    op.drop_constraint(
        "ck_meter_readings_review_reason", "meter_readings", type_="check"
    )
    op.create_check_constraint(
        "ck_meter_readings_review_reason",
        "meter_readings",
        "review_reason IN ('decrease', 'spike')",
    )
