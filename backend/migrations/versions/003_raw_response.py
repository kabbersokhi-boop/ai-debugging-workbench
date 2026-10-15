"""Retain the accepted provider response alongside structured diagnosis."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.add_column("investigations", sa.Column("raw_response", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "raw_response")
