"""drop users.reminder_hour: reminders go out at one fixed time

Revision ID: 0023
Revises: 0022
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # contract: drops users.reminder_hour. The previous release's User model
    # still selects the column, so (1) until the new app is deployed the old
    # one fails every query on users, so release outside the submission window
    # (days 1-5), and (2) rolling back to the old tag afterwards is impossible:
    # restore the release dump (docs/operations.md#failed-release).
    op.drop_constraint("ck_users_reminder_hour", "users", type_="check")
    op.drop_column("users", "reminder_hour")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "reminder_hour", sa.SmallInteger(), server_default="9", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_users_reminder_hour", "users", "reminder_hour BETWEEN 0 AND 23"
    )
