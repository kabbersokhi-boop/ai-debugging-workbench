"""Additive G1 source, candidate, approval plan and execution records."""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"


def upgrade():
    for table, columns in (
        ("repository_audit_sources", []),
        (
            "repository_audit_candidates",
            [
                sa.Column(
                    "snapshot_id",
                    sa.String(64),
                    sa.ForeignKey("repository_audit_sources.id"),
                    nullable=False,
                )
            ],
        ),
        ("repository_audit_plans", []),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.String(64), primary_key=True),
            *columns,
            sa.Column("record", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.execute(f"""CREATE TRIGGER immutable_repository_record BEFORE UPDATE OR DELETE ON {table}
                    FOR EACH ROW EXECUTE FUNCTION immutable_patch_candidate()""")
    op.create_table(
        "repository_audit_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(64),
            sa.ForeignKey("repository_audit_candidates.id"),
            nullable=False,
        ),
        sa.Column(
            "plan_id", sa.String(64), sa.ForeignKey("repository_audit_plans.id"), nullable=False
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    for table in (
        "repository_audit_runs",
        "repository_audit_plans",
        "repository_audit_candidates",
        "repository_audit_sources",
    ):
        op.drop_table(table)
