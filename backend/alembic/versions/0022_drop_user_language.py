"""drop users.language: the app is Ukrainian only

Revision ID: 0022
Revises: 0021
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # contract: drops users.language and the languagecode enum. The previous
    # release's User model still selects the column, so (1) until the new app is
    # deployed the old one fails every query on users, so release outside the
    # submission window (days 1-5), and (2) rolling back to the old tag afterwards
    # is impossible: restore the release dump (docs/operations.md#failed-release).
    op.drop_column("users", "language")
    op.execute("DROP TYPE languagecode")


def downgrade() -> None:
    language = sa.Enum("EN", "UA", name="languagecode")
    language.create(op.get_bind())
    op.add_column(
        "users",
        sa.Column("language", language, nullable=False, server_default="UA"),
    )
    op.alter_column("users", "language", server_default=None)
