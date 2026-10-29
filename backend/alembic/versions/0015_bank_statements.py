"""bank_statements

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-29 12:14:31.208377

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bank_statement_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("encoding", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("account_iban", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("first_operation_date", sa.Date(), nullable=False),
        sa.Column("last_operation_date", sa.Date(), nullable=False),
        sa.Column("covered_through", sa.Date(), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("credits_new", sa.Integer(), nullable=False),
        sa.Column("credits_duplicate", sa.Integer(), nullable=False),
        sa.Column("debits_skipped", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "covered_through >= last_operation_date",
            name="ck_bank_statement_files_coverage",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_bank_statement_files_sha256"),
    )
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "document_number", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("amount_uah", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payer_iban", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("payer_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("purpose", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("first_file_id", sa.Integer(), nullable=False),
        sa.Column("suggested_household_id", sa.Integer(), nullable=True),
        sa.Column(
            "suggestion_source", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("dismissed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("dismiss_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.CheckConstraint(
            "amount_uah > 0", name="ck_bank_transactions_amount_positive"
        ),
        sa.ForeignKeyConstraint(
            ["dismissed_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["first_file_id"],
            ["bank_statement_files.id"],
        ),
        sa.ForeignKeyConstraint(
            ["suggested_household_id"],
            ["households.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_number",
            "operation_date",
            "amount_uah",
            "payer_iban",
            name="uq_bank_transactions_dedupe",
        ),
    )
    op.create_index(
        op.f("ix_bank_transactions_operation_date"),
        "bank_transactions",
        ["operation_date"],
        unique=False,
    )
    op.add_column(
        "payments", sa.Column("bank_transaction_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_payments_bank_transaction_id"),
        "payments",
        ["bank_transaction_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_payments_bank_transaction_id",
        "payments",
        "bank_transactions",
        ["bank_transaction_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_payments_bank_transaction_id", "payments", type_="foreignkey"
    )
    op.drop_index(op.f("ix_payments_bank_transaction_id"), table_name="payments")
    op.drop_column("payments", "bank_transaction_id")
    op.drop_index(
        op.f("ix_bank_transactions_operation_date"), table_name="bank_transactions"
    )
    op.drop_table("bank_transactions")
    op.drop_table("bank_statement_files")
