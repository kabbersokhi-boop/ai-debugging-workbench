"""Real PostgreSQL with explicitly deterministic offline provider fixtures."""

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from langchain_core.prompt_values import ChatPromptValue
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench.config import settings
from workbench.db import Base, Investigation, Run, SourceChunk
from workbench.rag.provider import ProviderError
from workbench.rag.retrieval import RepositoryRetriever
from workbench.rag.service import InvestigationManager
from workbench.rag.snapshot import identity, load_snapshot

pytestmark = pytest.mark.integration


class OfflineProvider:
    chat_model = "offline-deterministic-test"
    embedding_model = "offline-hash-embedding"
    rerank_model = "offline-order-rerank"

    def __init__(self, behavior: str = "insufficient"):
        self.behavior = behavior
        self.chat_started = asyncio.Event()
        self.calls: list[dict] = []

    async def embed(self, texts, input_type):
        self.calls.append({"workload": "embedding", "mode": "offline", "input_type": input_type})
        return [[(b + 1) / 256 for b in hashlib.sha256(t.encode()).digest()[:8]] for t in texts]

    async def rerank(self, query, passages):
        return [(i, float(len(passages) - i)) for i in range(len(passages))]

    async def chat(self, prompt: ChatPromptValue) -> str:
        self.chat_started.set()
        if self.behavior == "invalid":
            return "not structured JSON"
        if self.behavior == "failure":
            raise ProviderError("provider_http", "Offline simulated NVIDIA failure")
        if self.behavior == "wait":
            await asyncio.sleep(30)
        return json.dumps(
            {
                "outcome": "insufficient_evidence",
                "diagnosis": "Offline fixture cannot infer a diagnosis.",
                "citations": [],
                "observations": ["Offline test input received"],
                "uncertainty": ["No real model used in this test"],
                "next_check": "Inspect additional source evidence.",
            }
        )

    async def close(self):
        pass


@pytest.fixture
async def rag_store() -> AsyncIterator[async_sessionmaker]:
    schema = f"test_rag_{uuid4().hex}"
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        scoped = await connection.execution_options(schema_translate_map={None: schema})
        await scoped.run_sync(Base.metadata.create_all)
    store = async_sessionmaker(
        engine.execution_options(schema_translate_map={None: schema}), expire_on_commit=False
    )
    try:
        yield store
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


async def test_real_pgvector_fts_index_dedup_and_snapshot_isolation(
    rag_store: async_sessionmaker,
) -> None:
    provider = OfflineProvider()
    retriever = RepositoryRetriever(provider, rag_store)
    snapshot = load_snapshot()
    index_id = await retriever.index(snapshot)
    calls = len(provider.calls)
    assert await retriever.index(snapshot) == index_id
    assert len(provider.calls) == calls
    lexical = await retriever.retrieve(snapshot, index_id, "calculateTotals subtotal", "lexical")
    assert any(row.symbol == "calculateTotals" for row in lexical.candidates)
    dense = await retriever.retrieve(snapshot, index_id, "cart quantity", "dense")
    assert dense.candidates and all(c.dense_rank for c in dense.candidates)
    other = snapshot.model_copy(update={"source_commit": "a" * 40})
    other.id = identity(other.source_commit, [(f.path, f.sha256) for f in other.files])
    with pytest.raises(ValueError, match="Cross-snapshot"):
        await retriever.retrieve(other, index_id, "cart")
    async with rag_store() as session:
        assert await session.scalar(select(func.count()).select_from(SourceChunk)) == 84


async def seed_run(store: async_sessionmaker) -> UUID:
    run_id = uuid4()
    # Explicitly offline input; only source identity matters to these tests.
    evidence = {
        "quantity": 3,
        "unit_price_cents": 6400,
        "line_total_cents": 19200,
        "subtotal_cents": 6400,
        "shipping_cents": 800,
        "total_cents": 7200,
    }
    async with store.begin() as session:
        session.add(
            Run(
                id=run_id,
                bug_id="cart-quantity",
                status="reproduced",
                result={
                    "fixture_sha256": load_snapshot().fixture_sha256,
                    "baseline": evidence,
                    "observed": evidence,
                    "checks": [],
                },
            )
        )
    return run_id


@pytest.mark.parametrize(
    "behavior,status",
    [
        ("insufficient", "insufficient_evidence"),
        ("invalid", "invalid_output"),
        ("failure", "provider_error"),
    ],
)
async def test_saved_investigation_preserves_evidence_and_failure_classification(
    rag_store: async_sessionmaker, behavior: str, status: str
) -> None:
    run_id = await seed_run(rag_store)
    manager = InvestigationManager(lambda: OfflineProvider(behavior), rag_store)
    created = await manager.create(run_id, None)
    await asyncio.gather(*list(manager.tasks.values()))
    saved = await manager.get(created["id"])
    assert saved["status"] == status, saved
    assert saved["retrieval"]["supplied_context"]
    assert saved["model_input"]["browser_evidence"]
    assert (
        saved["diagnosis"] is None
        if status != "insufficient_evidence"
        else saved["diagnosis"]["outcome"] == "insufficient_evidence"
    )
    reopened = InvestigationManager(store=rag_store)
    assert (await reopened.history(run_id))[0]["id"] == created["id"]
    assert (await reopened.get(created["id"]))["retrieval"] == saved["retrieval"]
    await manager.close()


async def test_investigation_cancel_and_restart_keep_reproduction_separate(
    rag_store: async_sessionmaker,
) -> None:
    run_id = await seed_run(rag_store)
    provider = OfflineProvider("wait")
    manager = InvestigationManager(lambda: provider, rag_store)
    created = await manager.create(run_id, None)
    async with asyncio.timeout(10):
        await provider.chat_started.wait()
    cancelled = await manager.cancel(created["id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["retrieval"] is not None
    assert cancelled["diagnosis"] is None
    async with rag_store.begin() as session:
        row = await session.get(Investigation, created["id"])
        assert row is not None
        row.status = "diagnosing"
    await manager.recover()
    assert (await manager.get(created["id"]))["status"] == "interrupted"
    async with rag_store() as session:
        run = await session.get(Run, run_id)
        assert run is not None and run.status == "reproduced"
