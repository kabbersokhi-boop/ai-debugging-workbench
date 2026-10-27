"""Immutable independent requirements and verification plans; G1 records stay unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("repository_audit_requirements", "repository_audit_verification_plans"):
        op.create_table(
            name,
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("record", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.execute(
            f"CREATE TRIGGER immutable_repository_record BEFORE UPDATE OR DELETE ON {name} "
            "FOR EACH ROW EXECUTE FUNCTION immutable_patch_candidate()"
        )


def downgrade():
    op.drop_table("repository_audit_verification_plans")
    op.drop_table("repository_audit_requirements")
