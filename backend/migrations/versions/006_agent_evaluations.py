"""Independent evaluation evidence, additive to accepted debugger history."""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"


def upgrade() -> None:
    op.create_table(
        "agent_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_id", sa.String(80), nullable=False),
        sa.Column("candidate_id", sa.String(100), nullable=False),
        sa.Column("candidate_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("evidence", sa.JSON(), nullable=False),
    )
    op.create_index("ix_agent_evaluations_task_id", "agent_evaluations", ["task_id"])


def downgrade() -> None:
    op.drop_table("agent_evaluations")
