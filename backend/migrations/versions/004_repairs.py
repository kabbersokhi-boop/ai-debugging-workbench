"""Repair runs and native LangGraph PostgreSQL checkpoints (SDK schema at locked version)."""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade() -> None:
    op.create_table(
        "repairs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column(
            "investigation_id", sa.Uuid(), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("snapshot_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("error_code", sa.String(80)),
    )
    op.create_index("ix_repairs_run_id", "repairs", ["run_id"])
    op.create_index("ix_repairs_investigation_id", "repairs", ["investigation_id"])
    op.execute("CREATE SCHEMA repair_graph")
    op.execute(
        "CREATE TABLE IF NOT EXISTS repair_graph.checkpoint_migrations ("
        "\n    v INTEGER PRIMARY KEY\n);"
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (0)")
    op.execute(
        "CREATE TABLE IF NOT EXISTS repair_graph.checkpoints (\n    "
        "thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT "
        "'',\n    checkpoint_id TEXT NOT NULL,\n    parent_checkpoint_id "
        "TEXT,\n    type TEXT,\n    checkpoint JSONB NOT NULL,\n    metadata "
        "JSONB NOT NULL DEFAULT '{}',\n    PRIMARY KEY (thread_id, "
        "checkpoint_ns, checkpoint_id)\n);"
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (1)")
    op.execute(
        "CREATE TABLE IF NOT EXISTS repair_graph.checkpoint_blobs (\n    "
        "thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT "
        "'',\n    channel TEXT NOT NULL,\n    version TEXT NOT NULL,\n    "
        "type TEXT NOT NULL,\n    blob BYTEA,\n    PRIMARY KEY (thread_id, "
        "checkpoint_ns, channel, version)\n);"
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (2)")
    op.execute(
        "CREATE TABLE IF NOT EXISTS repair_graph.checkpoint_writes (\n    "
        "thread_id TEXT NOT NULL,\n    checkpoint_ns TEXT NOT NULL DEFAULT "
        "'',\n    checkpoint_id TEXT NOT NULL,\n    task_id TEXT NOT NULL,"
        "\n    idx INTEGER NOT NULL,\n    channel TEXT NOT NULL,\n    type "
        "TEXT,\n    blob BYTEA NOT NULL,\n    PRIMARY KEY (thread_id, "
        "checkpoint_ns, checkpoint_id, task_id, idx)\n);"
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (3)")
    op.execute("ALTER TABLE repair_graph.checkpoint_blobs ALTER COLUMN blob DROP not null;")
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (4)")
    op.execute("SELECT 1;")
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (5)")
    op.execute(
        "\n    CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON "
        "repair_graph.checkpoints(thread_id);\n    "
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (6)")
    op.execute(
        "\n    CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON"
        " repair_graph.checkpoint_blobs(thread_id);\n    "
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (7)")
    op.execute(
        "\n    CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx "
        "ON repair_graph.checkpoint_writes(thread_id);\n    "
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (8)")
    op.execute(
        "ALTER TABLE repair_graph.checkpoint_writes ADD COLUMN IF NOT "
        "EXISTS task_path TEXT NOT NULL DEFAULT '';"
    )
    op.execute("INSERT INTO repair_graph.checkpoint_migrations(v) VALUES (9)")


def downgrade() -> None:
    op.execute("DROP SCHEMA repair_graph CASCADE")
    op.drop_table("repairs")
