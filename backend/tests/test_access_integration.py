"""Guest ownership and quota transactions against a disposable PostgreSQL schema."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import test_rag_integration as fixtures
from fastapi import HTTPException

from workbench import access, api, service
from workbench.config import settings
from workbench.db import GuestSession, Investigation, Repair, Run
from workbench.rag.service import InvestigationManager
from workbench.rag.snapshot import load_snapshot
from workbench.repair.service import RepairManager

rag_store = fixtures.rag_store
pytestmark = pytest.mark.integration


async def test_guest_ownership_artifacts_idempotency_and_expiry(rag_store, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "guest_access", True)
    for module in (access, api, service):
        monkeypatch.setattr(module, "sessions", rag_store)
    monkeypatch.setattr(settings, "artifact_dir", tmp_path)

    class Manager:
        async def create(self, bug_id, key):
            from sqlalchemy import select

            async with rag_store.begin() as session:
                prior = await session.scalar(select(Run).where(Run.idempotency_key == key))
                if prior:
                    run_id = prior.id
                else:
                    run_id = uuid4()
                    session.add(
                        Run(id=run_id, bug_id=bug_id, status="cancelled", idempotency_key=key)
                    )
            return await service.get_run(run_id)

    monkeypatch.setattr(api.app.state, "manager", Manager(), raising=False)
    monkeypatch.setattr(
        api.app.state, "investigations", InvestigationManager(store=rag_store), raising=False
    )
    monkeypatch.setattr(api.app.state, "repairs", RepairManager(store=rag_store), raising=False)
    transport = httpx.ASGITransport(app=api.app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://private") as a,
        httpx.AsyncClient(transport=transport, base_url="http://private") as b,
    ):
        await a.get("/api/mode")
        await b.get("/api/mode")
        assert a.cookies["workbench_guest"] != b.cookies["workbench_guest"]
        headers = {"Idempotency-Key": "same-browser-key"}
        first = (
            await a.post("/api/runs", json={"bug_id": "cart-quantity"}, headers=headers)
        ).json()
        again = (
            await a.post("/api/runs", json={"bug_id": "cart-quantity"}, headers=headers)
        ).json()
        other = (
            await b.post("/api/runs", json={"bug_id": "cart-quantity"}, headers=headers)
        ).json()
        assert first["id"] == again["id"] != other["id"]
        run_id = UUID(first["id"])
        investigation_id, repair_id = uuid4(), uuid4()
        async with rag_store.begin() as session:
            session.add(
                Investigation(
                    id=investigation_id,
                    run_id=run_id,
                    status="completed",
                    report="offline access fixture",
                    snapshot_id=load_snapshot().id,
                    events=[],
                    provider_calls=[],
                )
            )
            await session.flush()
            session.add(
                Repair(
                    id=repair_id,
                    run_id=run_id,
                    investigation_id=investigation_id,
                    snapshot_id=load_snapshot().id,
                    status="cancelled",
                    state={"attempts": []},
                    events=[],
                )
            )
        folder = tmp_path / str(run_id)
        folder.mkdir()
        (folder / "before.png").write_bytes(b"private-test-pixels")
        for path in (
            f"/api/runs/{run_id}",
            f"/api/runs/{run_id}/artifacts/before.png",
            f"/api/investigations/{investigation_id}",
            f"/api/repairs/{repair_id}",
            f"/api/repairs/{repair_id}/evidence",
            f"/api/snapshots/{load_snapshot().id}",
        ):
            assert (await b.get(path)).status_code == 404, path
        assert (await a.get(f"/api/runs/{run_id}")).status_code == 200
        assert len((await a.get("/api/runs")).json()) == 1
        assert (
            await a.post(
                "/api/runs",
                headers={"Origin": "https://attacker.example"},
                json={"bug_id": "cart-quantity"},
            )
        ).status_code == 403
        async with rag_store.begin() as session:
            owner = await session.get(GuestSession, UUID(a.cookies["workbench_guest"]))
            owner.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert (await a.get(f"/api/runs/{run_id}")).status_code == 404


async def test_reservations_are_atomic_persisted_and_server_wide(rag_store, monkeypatch):
    monkeypatch.setattr(access, "sessions", rag_store)
    monkeypatch.setattr(settings, "global_token_limit", 20)
    monkeypatch.setattr(settings, "guest_token_limit", 15)
    owner = uuid4()
    await access.reserve(owner, 15)
    with pytest.raises(HTTPException) as error:
        await access.reserve(owner, 1)
    assert error.value.status_code == 429
    # The failed transaction must not partially consume the global budget.
    await access.reserve(uuid4(), 5)
    with pytest.raises(HTTPException):
        await access.reserve(uuid4(), 1)
