"""Failure lifecycle tests against real PostgreSQL in a disposable per-test schema."""

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench import service
from workbench.config import settings
from workbench.contracts import RunStatus
from workbench.db import Base, Run

pytestmark = pytest.mark.integration


@pytest.fixture
async def isolated_store(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[async_sessionmaker]:
    schema = f"test_{uuid4().hex}"
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        scoped = await connection.execution_options(schema_translate_map={None: schema})
        await scoped.run_sync(Base.metadata.create_all)
    store = async_sessionmaker(
        engine.execution_options(schema_translate_map={None: schema}), expire_on_commit=False
    )
    monkeypatch.setattr(service, "sessions", store)
    try:
        yield store
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


@pytest.mark.parametrize("failure", ["unavailable", "empty", "invalid", "timeout"])
async def test_runner_failures_never_become_reproduced(
    isolated_store: async_sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if failure == "unavailable":
            raise httpx.ConnectError("offline", request=request)
        if failure == "invalid":
            return httpx.Response(200, text='{"kind":"result","title":"x","detail":"x"}\n')
        if failure == "timeout":
            await asyncio.sleep(1)
        return httpx.Response(200, text="")

    if failure == "timeout":
        monkeypatch.setattr(settings, "run_timeout_seconds", 0.01)
    async with httpx.AsyncClient(
        base_url="http://runner", transport=httpx.MockTransport(handler)
    ) as client:
        manager = service.RunManager(client)
        created = await manager.create("cart-quantity", None)
        await asyncio.gather(*list(manager.tasks.values()))
        run = await service.get_run(created.id)
        assert run.status == RunStatus.ERROR
        assert run.result is None
        assert run.error
        assert run.events[-1].kind == "error"
        await manager.close()


async def test_restart_recovers_unfinished_runs_and_preserves_terminal_outcomes(
    isolated_store: async_sessionmaker,
) -> None:
    ids = [uuid4(), uuid4(), uuid4()]
    async with isolated_store.begin() as session:
        for run_id, status in zip(ids, ["queued", "running", "cancelled"], strict=True):
            session.add(Run(id=run_id, bug_id="cart-quantity", status=status))
    async with httpx.AsyncClient(base_url="http://runner") as client:
        manager = service.RunManager(client)
        await manager.recover()
        for run_id in ids[:2]:
            recovered = await service.get_run(run_id)
            assert recovered.status == RunStatus.INTERRUPTED
            assert recovered.error and "restarted" in recovered.error
            assert recovered.events[-1].title == "Run interrupted"
        assert (await service.get_run(ids[-1])).status == RunStatus.CANCELLED
        await manager.recover()
        assert len((await service.get_run(ids[0])).events) == 1


async def test_concurrent_duplicate_requests_produce_one_run(
    isolated_store: async_sessionmaker,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return httpx.Response(200, text="")

    async with httpx.AsyncClient(
        base_url="http://runner", transport=httpx.MockTransport(handler)
    ) as client:
        manager = service.RunManager(client)
        first, second = await asyncio.gather(
            manager.create("cart-quantity", "shared-idempotency-key"),
            manager.create("cart-quantity", "shared-idempotency-key"),
        )
        assert first.id == second.id
        assert len(manager.tasks) == 1
        cancelled = await manager.cancel(first.id)
        assert cancelled.status == RunStatus.CANCELLED
        assert cancelled.result is None
        await manager.close()
