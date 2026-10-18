from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Computed, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from workbench.config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    bug_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    owner_id: Mapped[UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    error: Mapped[str | None]
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int]
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str]
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_commit: Mapped[str] = mapped_column(String(40))
    fixture_sha256: Mapped[str] = mapped_column(String(64), index=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)


class RepositoryIndex(Base):
    __tablename__ = "repository_indexes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("source_snapshots.id"))
    embedding_model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int]
    chunker_version: Mapped[str] = mapped_column(String(80))


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("index_id", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("repository_indexes.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(16))
    path: Mapped[str]
    start_line: Mapped[int]
    end_line: Mapped[int]
    symbol: Mapped[str]
    content: Mapped[str]
    search_text: Mapped[str]
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', search_text)", persisted=True)
    )
    embedding: Mapped[Any] = mapped_column(Vector())


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(40))
    report: Mapped[str]
    snapshot_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retrieval: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    model_input: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    diagnosis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_response: Mapped[str | None]
    error: Mapped[str | None]
    error_code: Mapped[str | None] = mapped_column(String(80))
    provider_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
sessions = async_sessionmaker(engine, expire_on_commit=False)


class Repair(Base):
    __tablename__ = "repairs"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"), index=True)
    investigation_id: Mapped[UUID] = mapped_column(ForeignKey("investigations.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    error: Mapped[str | None]
    error_code: Mapped[str | None] = mapped_column(String(80))


class GuestSession(Base):
    __tablename__ = "guest_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageBucket(Base):
    __tablename__ = "usage_buckets"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    requests: Mapped[int] = mapped_column(default=0)
    reserved_tokens: Mapped[int] = mapped_column(default=0)


class Evaluation(Base):
    __tablename__ = "agent_evaluations"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(80), index=True)
    candidate_id: Mapped[str] = mapped_column(String(100))
    candidate_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)


class ComparisonTrial(Base):
    __tablename__ = "agent_comparison_trials"
    __table_args__ = (
        UniqueConstraint("experiment_id", "task_id", "configuration_id", "trial_index"),
    )
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(40), index=True)
    task_id: Mapped[str] = mapped_column(String(80))
    configuration_id: Mapped[str] = mapped_column(String(80))
    trial_index: Mapped[int]
    record_hash: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    evaluation_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_evaluations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
