"""Immutable checklist applications; existing approval and verifier records stay intact."""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"


def upgrade():
    op.create_table(
        "repository_audit_checklist_uses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("record", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute("""CREATE TRIGGER immutable_repository_record BEFORE UPDATE OR DELETE
        ON repository_audit_checklist_uses FOR EACH ROW
        EXECUTE FUNCTION immutable_patch_candidate()""")


def downgrade():
    op.drop_table("repository_audit_checklist_uses")
