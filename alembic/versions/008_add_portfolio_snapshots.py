"""add_portfolio_snapshots

Revision ID: 008
Revises: 007
Create Date: 2026-05-15 01:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_status", sa.String(length=32), nullable=False),
        sa.Column("source_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshots_as_of", "portfolio_snapshots", ["as_of"], unique=False)
    op.create_index(
        "ix_portfolio_snapshots_user_as_of",
        "portfolio_snapshots",
        ["user_id", "as_of"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_snapshots_user_created",
        "portfolio_snapshots",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_portfolio_snapshots_user_id", "portfolio_snapshots", ["user_id"], unique=False)

    op.create_table(
        "holding_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("instrument_name", sa.String(length=255), nullable=True),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("industry_id", sa.UUID(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("avg_cost", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("last_price", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("market_value_native", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("market_value_base", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_holding_snapshots_snapshot", "holding_snapshots", ["snapshot_id"], unique=False)
    op.create_index(
        "ix_holding_snapshots_user_account",
        "holding_snapshots",
        ["user_id", "account_id"],
        unique=False,
    )
    op.create_index("ix_holding_snapshots_user_id", "holding_snapshots", ["user_id"], unique=False)
    op.create_index(
        "ix_holding_snapshots_user_instrument",
        "holding_snapshots",
        ["user_id", "instrument_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_holding_snapshots_user_instrument", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_user_id", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_user_account", table_name="holding_snapshots")
    op.drop_index("ix_holding_snapshots_snapshot", table_name="holding_snapshots")
    op.drop_table("holding_snapshots")
    op.drop_index("ix_portfolio_snapshots_user_id", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_user_created", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_user_as_of", table_name="portfolio_snapshots")
    op.drop_index("ix_portfolio_snapshots_as_of", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
