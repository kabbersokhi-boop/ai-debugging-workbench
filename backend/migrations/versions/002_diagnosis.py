"""Add immutable repository snapshots, pgvector indexes and diagnosis records."""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""CREATE TABLE source_snapshots (
        id VARCHAR(64) PRIMARY KEY, source_commit VARCHAR(40) NOT NULL,
        fixture_sha256 VARCHAR(64) NOT NULL, manifest JSON NOT NULL)""")
    op.execute(
        "CREATE INDEX ix_source_snapshots_fixture_sha256 ON source_snapshots(fixture_sha256)"
    )
    op.execute("""CREATE TABLE repository_indexes (
        id VARCHAR(64) PRIMARY KEY,
        snapshot_id VARCHAR(64) NOT NULL REFERENCES source_snapshots(id),
        embedding_model VARCHAR(200) NOT NULL, dimensions INTEGER NOT NULL,
        chunker_version VARCHAR(80) NOT NULL)""")
    op.execute("""CREATE TABLE source_chunks (
        id SERIAL PRIMARY KEY, index_id VARCHAR(64) NOT NULL REFERENCES repository_indexes(id),
        source_id VARCHAR(16) NOT NULL, path TEXT NOT NULL, start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL, symbol TEXT NOT NULL, content TEXT NOT NULL,
        search_text TEXT NOT NULL,
        search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', search_text)) STORED,
        embedding VECTOR NOT NULL, UNIQUE(index_id, source_id))""")
    op.execute("CREATE INDEX ix_source_chunks_index_id ON source_chunks(index_id)")
    op.execute("CREATE INDEX source_chunks_fts ON source_chunks USING gin(search_vector)")
    op.execute("""CREATE TABLE investigations (
        id UUID PRIMARY KEY, run_id UUID NOT NULL REFERENCES runs(id),
        status VARCHAR(40) NOT NULL, report TEXT NOT NULL, snapshot_id VARCHAR(64) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        retrieval JSON, model_input JSON, diagnosis JSON, error TEXT, error_code VARCHAR(80),
        provider_calls JSON NOT NULL, events JSON NOT NULL)""")
    op.execute("CREATE INDEX ix_investigations_run_id ON investigations(run_id)")


def downgrade() -> None:
    for table in ["investigations", "source_chunks", "repository_indexes", "source_snapshots"]:
        op.drop_table(table)
    # Leave the shared extension and all Milestone 1 data intact.
