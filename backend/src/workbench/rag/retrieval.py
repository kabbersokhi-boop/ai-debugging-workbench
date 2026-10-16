import hashlib
import re
import time
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workbench.db import RepositoryIndex, SourceChunk, SourceSnapshot, sessions
from workbench.rag.contracts import Candidate, ContextChunk, RetrievalTrace, Snapshot
from workbench.rag.provider import Provider
from workbench.rag.snapshot import CHUNKER_VERSION, chunk_snapshot, validate_snapshot

Method = Literal["lexical", "dense", "hybrid", "hybrid_rerank"]


def search_text(value: str) -> str:
    return re.sub(r"[^\w]+", " ", re.sub(r"([a-z])([A-Z])", r"\1 \2", value))


def fuse(lexical: list[ContextChunk], dense: list[ContextChunk]) -> list[Candidate]:
    candidates: dict[str, Candidate] = {}
    for name, rows in [("lexical_rank", lexical), ("dense_rank", dense)]:
        for rank, row in enumerate(rows, 1):
            candidate = candidates.setdefault(row.source_id, Candidate(**row.model_dump()))
            setattr(candidate, name, rank)
            candidate.fusion_score += 1 / (60 + rank)
    return sorted(candidates.values(), key=lambda row: (-row.fusion_score, row.source_id))


def select_context(
    candidates: list[Candidate], snapshot_id: str, budget: int
) -> list[ContextChunk]:
    selected: list[ContextChunk] = []
    remaining = budget
    for candidate in candidates:
        cost = len(candidate.formatted(snapshot_id).encode()) + (2 if selected else 0)
        candidate.selected = cost <= remaining
        candidate.selection_reason = (
            "Included in rank order within context budget"
            if candidate.selected
            else "Skipped: complete chunk exceeds remaining context budget"
        )
        if candidate.selected:
            selected.append(
                ContextChunk.model_validate(
                    candidate.model_dump(include=set(ContextChunk.model_fields))
                )
            )
            remaining -= cost
    return selected


class RepositoryRetriever:
    def __init__(self, provider: Provider, store: async_sessionmaker[AsyncSession] = sessions):
        self.provider = provider
        self.store = store

    async def index(self, snapshot: Snapshot) -> str:
        validate_snapshot(snapshot)
        index_id = hashlib.sha256(
            f"{snapshot.id}:{self.provider.embedding_model}:{CHUNKER_VERSION}".encode()
        ).hexdigest()
        async with self.store.begin() as session:
            # Serialize the first embedding/index operation, also across CLI/API processes.
            # The enclosing investigation budget cancels and rolls back an incomplete index.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": index_id}
            )
            existing = await session.get(RepositoryIndex, index_id)
            if existing:
                return existing.id
            source = await session.get(SourceSnapshot, snapshot.id)
            if source is None:
                session.add(
                    SourceSnapshot(
                        id=snapshot.id,
                        source_commit=snapshot.source_commit,
                        fixture_sha256=snapshot.fixture_sha256,
                        manifest=snapshot.model_dump(),
                    )
                )
                await session.flush()
            chunks = chunk_snapshot(snapshot)
            vectors: list[list[float]] = []
            for start in range(0, len(chunks), 24):
                batch = chunks[start : start + 24]
                vectors.extend(
                    await self.provider.embed(
                        [f"{c.path} {c.symbol}\n{c.content}" for c in batch], "passage"
                    )
                )
            dimensions = {len(v) for v in vectors}
            if len(vectors) != len(chunks) or len(dimensions) != 1:
                raise ValueError("Invalid embedding cardinality or dimensions")
            session.add(
                RepositoryIndex(
                    id=index_id,
                    snapshot_id=snapshot.id,
                    embedding_model=self.provider.embedding_model,
                    dimensions=next(iter(dimensions)),
                    chunker_version=CHUNKER_VERSION,
                )
            )
            await session.flush()
            for chunk, vector in zip(chunks, vectors, strict=True):
                session.add(
                    SourceChunk(
                        index_id=index_id,
                        **chunk.model_dump(),
                        embedding=vector,
                        search_text=search_text(f"{chunk.path} {chunk.symbol} {chunk.content}"),
                    )
                )
        return index_id

    async def retrieve(
        self,
        snapshot: Snapshot,
        index_id: str,
        query: str,
        method: Method = "hybrid_rerank",
        budget: int = 4000,
    ) -> RetrievalTrace:
        started = time.monotonic()
        async with self.store() as session:
            index = await session.get(RepositoryIndex, index_id)
            if (
                index is None
                or index.snapshot_id != snapshot.id
                or index.embedding_model != self.provider.embedding_model
            ):
                raise ValueError("Cross-snapshot or incompatible embedding retrieval rejected")
            lexical: list[ContextChunk] = []
            dense: list[ContextChunk] = []
            if method != "dense":
                # OR-based lexical recall tolerates natural-language reports while PostgreSQL
                # performs stemming/ranking. Caller text never becomes executable SQL.
                terms = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{1,40}", search_text(query))[:80]
                tsquery = func.websearch_to_tsquery("english", " OR ".join(terms))
                rows = (
                    await session.scalars(
                        select(SourceChunk)
                        .where(
                            SourceChunk.index_id == index_id,
                            SourceChunk.search_vector.op("@@")(tsquery),
                        )
                        .order_by(
                            func.ts_rank_cd(SourceChunk.search_vector, tsquery).desc(),
                            SourceChunk.source_id,
                        )
                        .limit(12)
                    )
                ).all()
                lexical = [self.as_context(row) for row in rows]
            if method != "lexical":
                vector = (await self.provider.embed([query], "query"))[0]
                if len(vector) != index.dimensions:
                    raise ValueError("Query embedding dimensions differ from indexed model")
                rows = (
                    await session.scalars(
                        select(SourceChunk)
                        .where(SourceChunk.index_id == index_id)
                        .order_by(
                            SourceChunk.embedding.cosine_distance(vector), SourceChunk.source_id
                        )
                        .limit(12)
                    )
                ).all()
                dense = [self.as_context(row) for row in rows]
        candidates = fuse(lexical, dense)[:12]
        rerank_status = "not_requested"
        if method == "hybrid_rerank" and candidates:
            ranked = await self.provider.rerank(
                query, [f"{row.path}\n{row.content}" for row in candidates]
            )
            if sorted(i for i, _ in ranked) != list(range(len(candidates))):
                raise ValueError("Incomplete reranker result")
            ordered = []
            for i, score in ranked:
                candidates[i].rerank_score = score
                ordered.append(candidates[i])
            candidates = ordered
            rerank_status = "completed"
        selected = select_context(candidates, snapshot.id, budget)
        return RetrievalTrace(
            query=query,
            snapshot_id=snapshot.id,
            source_commit=snapshot.source_commit,
            index_id=index_id,
            method=method,
            embedding_model=self.provider.embedding_model,
            rerank_model=self.provider.rerank_model if method == "hybrid_rerank" else None,
            rerank_status=rerank_status,
            candidates=candidates,
            supplied_context=selected,
            context_budget=budget,
            context_cost=len("\n\n".join(c.formatted(snapshot.id) for c in selected).encode()),
            latency_ms=round((time.monotonic() - started) * 1000),
        )

    @staticmethod
    def as_context(row: SourceChunk) -> ContextChunk:
        return ContextChunk(
            source_id=row.source_id,
            path=row.path,
            start_line=row.start_line,
            end_line=row.end_line,
            symbol=row.symbol,
            content=row.content,
        )
