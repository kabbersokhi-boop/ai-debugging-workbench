"""Separate immutable completed patches and fresh execution records."""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"


def upgrade():
    op.create_table(
        "patch_audit_candidates",
        sa.Column("id", sa.String(70), primary_key=True),
        sa.Column("task_id", sa.String(80), nullable=False, index=True),
        sa.Column("candidate_hash", sa.String(64), nullable=False, index=True),
        sa.Column("record", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "patch_audit_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(70),
            sa.ForeignKey("patch_audit_candidates.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("candidate_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute("""CREATE FUNCTION immutable_patch_candidate() RETURNS trigger
    LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Patch candidates are immutable'; END; $$""")
    op.execute("""CREATE TRIGGER immutable_patch_candidate BEFORE UPDATE OR DELETE
    ON patch_audit_candidates FOR EACH ROW EXECUTE FUNCTION immutable_patch_candidate()""")


def downgrade():
    op.drop_table("patch_audit_runs")
    op.drop_table("patch_audit_candidates")
    op.execute("DROP FUNCTION immutable_patch_candidate()")
