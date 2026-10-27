"""Actual recovery/persistence/validation with controlled broker and cancellation schedules."""

import asyncio
import copy
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import anyio
import httpx
import pytest
from test_repository_audit import candidate_for, completed_result, fixture_source, plan_for

from workbench.evaluator.catalog import identity
from workbench.repository_audit import recovery, service


@pytest.fixture
def state(monkeypatch):
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    aid = uuid4()
    result = completed_result(source, candidate, plan, aid)
    evidence = {
        "snapshot": source,
        "candidate": candidate,
        "plan": plan,
        "engine_id": service.engine_id(),
        "approval": {
            "local_owner": True,
            "candidate_id": candidate["id"],
            "plan_id": identity(plan),
            "approved_at": datetime.now(UTC).isoformat(),
        },
    }
    row = SimpleNamespace(id=aid, status="running", evidence=evidence, updated_at=datetime.now(UTC))
    rows = [row]

    class Session:
        async def scalars(self, query):
            return SimpleNamespace(all=lambda: [r for r in rows if r.status == "running"])

        async def get(self, model, key, **kwargs):
            return next(r for r in rows if r.id == key)

    class Sessions:
        @asynccontextmanager
        async def __call__(self):
            yield Session()

        begin = __call__

    monkeypatch.setattr(service, "sessions", Sessions())
    monkeypatch.setattr(recovery, "POLL_SECONDS", 0.09)
    monkeypatch.setattr(recovery, "POLL_INTERVAL", 0.003)
    monkeypatch.setattr(recovery, "CANCEL_SECONDS", 0.05)
    monkeypatch.setattr(recovery, "PERSIST_SECONDS", 0.05)
    return SimpleNamespace(row=row, rows=rows, result=result, requests=[])


def broker(monkeypatch, state, handler):
    original = httpx.AsyncClient

    async def route(request):
        state.requests.append((request.method, request.url.path))
        if request.method == "POST":
            assert request.url.path.endswith("/cancel"), "Recovery requested candidate execution"
            return httpx.Response(200, json={"status": "cancellation_requested"})
        return await handler(request)

    monkeypatch.setattr(
        service.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(route), **kwargs),
    )


async def test_absent_terminal_is_bounded_classified_and_idempotent(monkeypatch, state, caplog):
    async def missing(request):
        return httpx.Response(404)

    broker(monkeypatch, state, missing)
    caplog.set_level(logging.INFO, logger=recovery.LOGGER.name)
    manager = service.RepositoryAuditManager()
    started = time.monotonic()
    await manager.recover()
    assert time.monotonic() - started < 0.5
    assert state.row.status == "interrupted" and "result" not in state.row.evidence
    before, count = copy.deepcopy(state.row.__dict__), len(state.requests)
    await manager.recover()
    assert state.row.__dict__ == before and len(state.requests) == count
    events = [json.loads(r.message) for r in caplog.records if r.name == recovery.LOGGER.name]
    assert events[-1]["classification"] == "interrupted"
    assert events[-1]["http_404_count"] > 1
    assert all(e["candidate_execution_requested"] is False for e in events)
    assert len(events) == 6  # summaries, not one application log per 404


async def test_delayed_valid_result_preserves_completed_evidence_and_other_history(
    monkeypatch, state
):
    completed = SimpleNamespace(
        id=uuid4(), status="completed", evidence={"immutable": "prior"}, updated_at="unchanged"
    )
    state.rows.append(completed)
    before = copy.deepcopy(completed.__dict__)
    attempts = 0

    async def delayed(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("controlled earlier request timeout")
        if attempts < 4:
            return httpx.Response(404)
        return httpx.Response(200, json=state.result)

    broker(monkeypatch, state, delayed)
    manager = service.RepositoryAuditManager()
    await manager.recover()
    assert state.row.status == "tests_passed"
    assert state.row.evidence["result"] == state.result
    assert state.row.evidence["result_hash"] == identity(state.result)
    assert completed.__dict__ == before
    saved = copy.deepcopy(state.row.__dict__)
    await manager.recover()
    assert state.row.__dict__ == saved and attempts == 4


@pytest.mark.parametrize("mode", ["hang", "slow", "connection", "invalid_json", "array", "forged"])
async def test_broker_failures_finish_without_orphan_polling(monkeypatch, state, mode):
    active = 0

    async def failure(request):
        nonlocal active
        active += 1
        try:
            if mode == "hang":
                await anyio.sleep_forever()
            if mode == "slow":
                await anyio.sleep(0.3)
            if mode == "connection":
                raise httpx.ConnectError("controlled connection failure")
            if mode == "invalid_json":
                return httpx.Response(200, content=b"{malformed")
            if mode == "array":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json={**state.result, "candidate_hash": "forged"})
        finally:
            active -= 1

    broker(monkeypatch, state, failure)
    started = time.monotonic()
    await service.RepositoryAuditManager().recover()
    assert time.monotonic() - started < 0.5 and active == 0
    assert state.row.status == (
        "invalid_evidence" if mode in ("invalid_json", "array", "forged") else "interrupted"
    )
    assert "result" not in state.row.evidence


async def test_shutdown_during_request_propagates_without_false_db_verdict(monkeypatch, state):
    entered = asyncio.Event()

    async def hang(request):
        entered.set()
        await anyio.sleep_forever()

    broker(monkeypatch, state, hang)
    task = asyncio.create_task(service.RepositoryAuditManager().recover())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert state.row.status == "running" and "reason" not in state.row.evidence


async def test_cancel_timeout_still_checks_for_valid_completed_result(monkeypatch, state):
    async def valid(request):
        return httpx.Response(200, json=state.result)

    broker(monkeypatch, state, valid)
    manager = service.RepositoryAuditManager()

    async def stalled_cancel(audit_id):
        await anyio.sleep_forever()

    monkeypatch.setattr(manager, "stop", stalled_cancel)
    await manager.recover()
    assert state.row.status == "tests_passed"
    assert state.row.evidence["result"] == state.result


async def test_database_failure_is_bounded_and_does_not_release_unsafe_startup(monkeypatch, state):
    async def valid(request):
        return httpx.Response(200, json=state.result)

    broker(monkeypatch, state, valid)
    manager = service.RepositoryAuditManager()

    async def blocked_database(*args, **kwargs):
        await anyio.sleep_forever()

    monkeypatch.setattr(manager, "finish", blocked_database)
    with pytest.raises(TimeoutError):
        await manager.recover()
    assert state.row.status == "running" and "result" not in state.row.evidence


async def test_native_cancellation_colliding_with_anyio_connection_scope_is_not_lost(monkeypatch):
    entered, connected = asyncio.Event(), asyncio.Event()
    calls = 0

    async def terminal(audit_id):
        nonlocal calls
        calls += 1
        async with anyio.create_task_group() as group:

            async def connection_attempt():
                entered.set()
                await connected.wait()
                # Real AnyIO Happy Eyeballs uses this housekeeping cancellation.
                group.cancel_scope.cancel()

            group.start_soon(connection_attempt)
            await anyio.sleep_forever()
        return None

    manager = service.RepositoryAuditManager()
    monkeypatch.setattr(manager, "terminal", terminal)
    task = asyncio.create_task(manager.wait_terminal(uuid4()))
    await entered.wait()
    connected.set()
    asyncio.get_running_loop().call_soon(task.cancel)
    done, _ = await asyncio.wait({task}, timeout=0.5)
    if not done:
        task.cancel()  # bounded cleanup if the regression returns
    with pytest.raises(asyncio.CancelledError):
        await task
    assert done and calls == 1


async def test_level_deadline_survives_anyio_own_cancellation(monkeypatch):
    calls = 0

    async def terminal(audit_id):
        nonlocal calls
        calls += 1
        async with anyio.create_task_group() as group:

            async def connection_attempt():
                await anyio.sleep(0.001)
                group.cancel_scope.cancel()

            group.start_soon(connection_attempt)
            await anyio.sleep_forever()
        return None

    manager = service.RepositoryAuditManager()
    monkeypatch.setattr(recovery, "POLL_SECONDS", 0.04)
    monkeypatch.setattr(recovery, "POLL_INTERVAL", 0.001)
    monkeypatch.setattr(manager, "terminal", terminal)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await manager.wait_terminal(uuid4())
    assert time.monotonic() - started < 0.5 and calls > 1
