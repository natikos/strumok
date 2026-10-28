"""billing ledger: billing_periods, household_charges, readings.source

Expand phase: meter_readings keeps day/night usage and amount_charged_uah
for now (dropped in a later release). History before the current billing
period is copied into the ledger as closed periods, as-is, not recomputed.

Revision ID: 0004
Revises: 0003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

from app.core.domain import current_billing_period
from app.db.models import HOUSEHOLD_CHARGES_APPEND_ONLY_SQL

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def backfill_closed_history(connection: Connection, *, before_period: str) -> None:
    """Closes every period with readings earlier than `before_period` and turns
    each reading's frozen usage and amount into a household_charges row."""
    connection.execute(
        sa.text(
            """
            INSERT INTO billing_periods (period, status, rate_id, closed_at)
            SELECT p.period, 'closed',
                   (SELECT er.id FROM electricity_rates er
                     WHERE er.effective_from <= p.period
                     ORDER BY er.effective_from DESC LIMIT 1),
                   CURRENT_TIMESTAMP
            FROM (SELECT DISTINCT period FROM meter_readings
                   WHERE period < :before) p
            ON CONFLICT (period) DO NOTHING
            """
        ),
        {"before": before_period},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO household_charges
                (period, household_id, owner_user_id, reading_id,
                 day_usage_kwh, night_usage_kwh, is_estimated,
                 tariff_uah, loss_share_uah, penalty_uah, penalty_credit_uah,
                 total_uah)
            SELECT r.period, r.household_id, h.user_id, r.id,
                   r.day_usage_kwh, r.night_usage_kwh, false,
                   r.amount_charged_uah, 0, 0, 0, r.amount_charged_uah
            FROM meter_readings r
            JOIN households h ON h.id = r.household_id
            JOIN billing_periods bp ON bp.period = r.period AND bp.status = 'closed'
            WHERE r.period < :before
            ON CONFLICT (period, household_id) DO NOTHING
            """
        ),
        {"before": before_period},
    )


def upgrade() -> None:
    op.add_column(
        "meter_readings",
        sa.Column("source", sa.String(), server_default="resident", nullable=False),
    )
    op.create_table(
        "billing_periods",
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(), server_default="open", nullable=False),
        sa.Column("bill_day_kwh", sa.Numeric(12, 2), nullable=True),
        sa.Column("bill_night_kwh", sa.Numeric(12, 2), nullable=True),
        sa.Column("bill_total_uah", sa.Numeric(12, 2), nullable=True),
        sa.Column("rate_id", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'closed')", name="ck_billing_periods_status"
        ),
        sa.ForeignKeyConstraint(["rate_id"], ["electricity_rates.id"]),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("period"),
    )
    op.create_table(
        "household_charges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("reading_id", sa.Integer(), nullable=True),
        sa.Column("day_usage_kwh", sa.Numeric(12, 2), nullable=False),
        sa.Column("night_usage_kwh", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_estimated", sa.Boolean(), nullable=False),
        sa.Column("tariff_uah", sa.Numeric(12, 2), nullable=False),
        sa.Column("loss_share_uah", sa.Numeric(12, 2), nullable=False),
        sa.Column("penalty_uah", sa.Numeric(12, 2), nullable=False),
        sa.Column("penalty_credit_uah", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_uah", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["period"], ["billing_periods.period"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reading_id"], ["meter_readings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "period", "household_id", name="uq_household_charges_period_household"
        ),
    )
    op.create_index("ix_household_charges_period", "household_charges", ["period"])
    op.create_index(
        "ix_household_charges_household_id", "household_charges", ["household_id"]
    )
    connection = op.get_bind()
    backfill_closed_history(connection, before_period=current_billing_period())
    # exec_driver_sql: the function body contains ":" that text() would read as a bind.
    connection.exec_driver_sql(HOUSEHOLD_CHARGES_APPEND_ONLY_SQL)


def downgrade() -> None:
    op.drop_table("household_charges")
    op.get_bind().exec_driver_sql(
        "DROP FUNCTION IF EXISTS household_charges_reject_change()"
    )
    op.drop_table("billing_periods")
    op.drop_column("meter_readings", "source")
