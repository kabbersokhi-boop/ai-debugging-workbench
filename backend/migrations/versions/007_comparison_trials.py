"""Append-only comparison trial snapshots; existing evaluation history is reused."""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"


def upgrade() -> None:
    op.create_table(
        "agent_comparison_trials",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("experiment_id", sa.String(40), nullable=False, index=True),
        sa.Column("task_id", sa.String(80), nullable=False),
        sa.Column("configuration_id", sa.String(80), nullable=False),
        sa.Column("trial_index", sa.Integer(), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), sa.ForeignKey("agent_evaluations.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("experiment_id", "task_id", "configuration_id", "trial_index"),
    )
    # Application imports insert once. Database also refuses UPDATE/DELETE of retained trials.
    op.execute("""CREATE FUNCTION immutable_comparison_trial() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Comparison trials are append-only'; END; $$""")
    op.execute("""CREATE TRIGGER immutable_comparison_trial BEFORE UPDATE OR DELETE
    ON agent_comparison_trials FOR EACH ROW EXECUTE FUNCTION immutable_comparison_trial()""")


def downgrade() -> None:
    op.drop_table("agent_comparison_trials")
    op.execute("DROP FUNCTION immutable_comparison_trial()")
