"""Additive session ownership and persisted admission reservations. Old rows stay local-only."""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"


def upgrade() -> None:
    op.add_column("runs", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.create_index("ix_runs_owner_id", "runs", ["owner_id"])
    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "usage_buckets",
        sa.Column("scope", sa.String(100), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("usage_buckets")
    op.drop_table("guest_sessions")
    op.drop_index("ix_runs_owner_id", table_name="runs")
    op.drop_column("runs", "owner_id")
