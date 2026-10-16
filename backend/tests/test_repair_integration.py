"""Real MCP, PostgreSQL/LangGraph and Docker; model patches below are OFFLINE fixtures."""

import asyncio
import json
from uuid import uuid4

import docker
import httpx
import pytest
import test_rag_integration as rag_fixtures
from fastapi import HTTPException
from sqlalchemy import text
from test_rag_integration import OfflineProvider, seed_run
from test_repair import offline_patch

from workbench.config import settings
from workbench.db import Investigation, Repair, Run
from workbench.rag.provider import ProviderError
from workbench.rag.snapshot import load_snapshot
from workbench.repair.mcp_client import connect_tools
from workbench.repair.service import RepairManager
from workbench.repair.verifier import CHECK_NAMES, VERIFIER_VERSION

rag_store = rag_fixtures.rag_store
pytestmark = pytest.mark.integration


@pytest.fixture
def broker_url():
    client = docker.from_env()
    try:
        broker = client.containers.get("ai-debugging-workbench-repair-broker-1")
        network = broker.attrs["NetworkSettings"]["Networks"][
            "ai-debugging-workbench_repair-control"
        ]
        return f"http://{network['IPAddress']}:8012"
    finally:
        client.close()


async def seed_investigation(store):
    run_id = await seed_run(store)
    investigation_id = uuid4()
    async with store.begin() as session:
        session.add(
            Investigation(
                id=investigation_id,
                run_id=run_id,
                status="completed",
                report="OFFLINE fixture report",
                snapshot_id=load_snapshot().id,
                diagnosis={"outcome": "diagnosis", "diagnosis": "Offline proposed cause"},
                retrieval={"supplied_context": []},
                events=[],
                provider_calls=[],
            )
        )
    return investigation_id


async def test_real_mcp_discovery_permission_and_stale_base(broker_url):
    repair_id = uuid4()
    async with connect_tools(repair_id, load_snapshot().id, broker_url) as tools:
        assert tools.events[0]["method"] == "initialize"
        assert tools.events[0]["protocol_version"]
        names = {t["name"] for t in tools.events[1]["tools"]}
        assert names == {"search_source", "read_source", "apply_candidate", "verify_candidate"}
        found = await tools.call("search_source", {"query": "function render"})
        assert found["matches"] and found["snapshot_id"] == load_snapshot().id
        source = await tools.call(
            "read_source", {"path": "fixtures/retail/cart.js", "start_line": 30, "end_line": 52}
        )
        assert "calculateTotals(items)" in source["content"]
        for path in ["../backend/.env", "backend/src/workbench/repair/verifier.py", "/etc/passwd"]:
            with pytest.raises(ValueError, match="outside the approved"):
                await tools.call("read_source", {"path": path, "start_line": 1, "end_line": 2})
        with pytest.raises(ValueError, match="not owned"):
            await tools.call("verify_candidate", {"candidate_hash": "a" * 64})
        patch = offline_patch().model_dump() | {"original_sha256": "a" * 64}
        with pytest.raises(ValueError, match="Stale base"):
            await tools.call("apply_candidate", {"patch": patch})
        assert any(e.get("is_error") for e in tools.events)


@pytest.mark.parametrize(
    "new,expected",
    [
        ("sum + item.unitPriceCents * item.quantity", "passed"),
        ("sum + item.unitPriceCents * 3", "failed"),
        ("sum + item.unitPriceCents + 0", "failed"),
        (
            "sum + item.unitPriceCents * item.quantity + "
            "(document.querySelector('[data-testid=total]').hidden = true, 0)",
            "failed",
        ),
        (
            "sum + item.unitPriceCents * item.quantity + "
            "(setTimeout(() => document.querySelector('[data-testid=total]').textContent = "
            "'x'.repeat(10000), 0), 0)",
            "failed",
        ),
    ],
)
async def test_fixed_verifier_rejects_negative_fixtures_and_binds_exact_hash(
    broker_url, new, expected
):
    repair_id = uuid4()
    async with httpx.AsyncClient(base_url=broker_url, timeout=70) as client:
        original = (await client.post("/original/verify")).json()
        assert original["status"] == "failed"
        assert any(c["name"] == "add-one-baseline" and c["passed"] for c in original["checks"])
        assert any(c["name"] == "increment-two" and not c["passed"] for c in original["checks"])
        async with connect_tools(repair_id, load_snapshot().id, broker_url) as tools:
            candidate = await tools.call(
                "apply_candidate", {"patch": offline_patch(new).model_dump()}
            )
            assert candidate["attempt"] == 1
            assert candidate["isolation"]["internal_network"]
            result = await tools.call(
                "verify_candidate", {"candidate_hash": candidate["candidate_hash"]}
            )
            assert result["status"] == expected, result
            assert result["candidate_hash"] == candidate["candidate_hash"]
            assert result["verifier_version"] == VERIFIER_VERSION
            assert len(result["executed_file_hashes"]) == 3
            from workbench.repair.contracts import sha256

            assert result["executed_file_hashes"]["fixtures/retail/cart.js"] == sha256(
                candidate["content"]
            )
            assert result["container_image_id"].startswith("sha256:")
            assert result["check_names"] == CHECK_NAMES
            assert len(result["checks"]) == 12
            assert all(
                len(text) <= 200
                for check in result["checks"]
                for text in check["observed"].values()
            )
            if "repeat(10000)" in new:
                assert any(check["output_truncated"] for check in result["checks"])
            if expected == "passed":
                assert all(c["passed"] for c in result["checks"])
            repeated = (await client.post(f"/candidates/{repair_id}/1/verify")).json()
            assert repeated == result
            collision = await client.post(
                "/candidates",
                json={
                    "repair_id": str(repair_id),
                    "attempt": 1,
                    "patch": offline_patch("sum + 0").model_dump(),
                },
            )
            assert collision.status_code == 409
            screenshot = await client.get(f"/candidates/{repair_id}/1/artifacts/after.png")
            assert screenshot.status_code == 200 and len(screenshot.content) > 1000
        await client.post(f"/repairs/{repair_id}/cleanup")


async def test_candidate_isolation_cleanup_and_preview_headers(broker_url):
    repair_id = uuid4()
    client = docker.from_env()
    try:
        async with connect_tools(repair_id, load_snapshot().id, broker_url) as tools:
            candidate = await tools.call("apply_candidate", {"patch": offline_patch().model_dump()})
            containers = client.containers.list(
                filters={"label": f"ai-debugging-workbench.repair={repair_id}-1"}
            )
            assert len(containers) == 1
            container = containers[0]
            host = container.attrs["HostConfig"]
            assert host["ReadonlyRootfs"] and host["Memory"] == 1073741824
            assert host["PidsLimit"] == 192 and host["CapDrop"] == ["ALL"]
            assert all(
                m["Destination"] == "/site" and not m["RW"] for m in container.attrs["Mounts"]
            )
            assert not any(
                "NVIDIA" in e or "DATABASE" in e for e in container.attrs["Config"]["Env"]
            )
            probe = container.exec_run(
                [
                    "python",
                    "-c",
                    "import importlib.util; print(importlib.util.find_spec('workbench'))",
                ]
            ).output
            assert isinstance(probe, bytes) and probe.strip() == b"None"
            write = container.exec_run(
                ["python", "-c", "open('/site/cart.js','w').write('tamper')"]
            )
            assert write.exit_code != 0
            network_name = next(iter(container.attrs["NetworkSettings"]["Networks"]))
            assert client.networks.get(network_name).attrs["Internal"]
            network = client.networks.get(network_name)
            broker_ips = [
                v["IPv4Address"].split("/")[0]
                for k, v in network.attrs["Containers"].items()
                if k != container.id
            ]
            assert len(broker_ips) == 1
            for address, port in [("1.1.1.1", 443), (broker_ips[0], 8012)]:
                probe = container.exec_run(
                    [
                        "python",
                        "-c",
                        (
                            "import socket; socket.create_connection("
                            f"('{address}', {port}), timeout=1)"
                        ),
                    ]
                )
                assert probe.exit_code != 0
            async with httpx.AsyncClient(timeout=10) as http:
                response = await http.get(f"http://127.0.0.1:8013/preview/{repair_id}/1/retail/")
                assert response.status_code == 410
                assert "Script delivery is disabled" in response.text
                remote = await http.post(
                    f"{broker_url}/candidates/{repair_id}/1/remote", json={"action": "reset"}
                )
                assert remote.status_code == 200
                assert remote.json()["candidate_hash"] == candidate["candidate_hash"]
                assert remote.json()["observed"]["bag-count"] == "0"
                await http.post(f"{broker_url}/repairs/{repair_id}/cleanup")
            assert candidate["candidate_hash"]
        assert not client.containers.list(
            all=True, filters={"label": f"ai-debugging-workbench.repair={repair_id}-1"}
        )
        assert not client.networks.list(
            filters={"label": f"ai-debugging-workbench.repair={repair_id}-1"}
        )
        assert not client.volumes.list(
            filters={"label": f"ai-debugging-workbench.repair={repair_id}-1"}
        )
    finally:
        client.close()


class OfflineRepair(OfflineProvider):
    def __init__(self, mode="valid"):
        super().__init__()
        self.mode = mode
        self.number = 0

    async def chat(self, prompt):
        self.chat_started.set()
        self.number += 1
        self.calls.append({"workload": "chat", "model": self.chat_model, "mode": "offline_fixture"})
        if self.mode == "failure":
            raise ProviderError("provider_http", "Offline simulated provider failure")
        if self.mode == "wait":
            await asyncio.sleep(30)
        if self.mode == "invalid":
            return "not JSON"
        if self.number == 1:
            return json.dumps(
                {
                    "action": "read_source",
                    "reason": "Read missing caller context",
                    "path": "fixtures/retail/cart.js",
                    "start_line": 30,
                    "end_line": 65,
                }
            )
        return json.dumps(
            {
                "action": "propose",
                "reason": "OFFLINE deterministic patch fixture",
                "patch": offline_patch(
                    "sum + 1"
                    if self.mode == "fail"
                    else "sum + item.unitPriceCents * item.quantity"
                ).model_dump(),
            }
        )


@pytest.mark.parametrize(
    "mode,status",
    [
        ("valid", "verified"),
        ("fail", "verification_failed"),
        ("invalid", "invalid_output"),
        ("failure", "provider_error"),
    ],
)
async def test_checkpointed_graph_saved_history_and_failed_attempts(
    rag_store, broker_url, mode, status
):
    investigation_id = await seed_investigation(rag_store)
    provider = OfflineRepair(mode)
    manager = RepairManager(lambda: provider, rag_store, broker_url)
    created = await manager.create(investigation_id)
    await asyncio.gather(*list(manager.tasks.values()))
    saved = await manager.get(created["id"])
    assert saved["status"] == status, saved
    assert saved["state"]["mcp_events"][0]["method"] == "initialize"
    if mode == "fail":
        assert len(saved["state"]["attempts"]) == 2
    if mode == "invalid":
        assert saved["state"]["model_records"][0]["raw_response"] == "not JSON"
        assert saved["state"]["model_records"][0]["rejection"]
    if mode == "valid":
        assert saved["state"]["source_reads"]
        assert saved["state"]["verification"]["candidate_hash"] == saved["state"]["candidate_hash"]
    reopened = RepairManager(store=rag_store, broker_url=broker_url)
    assert (await reopened.history(investigation_id))[0]["state"] == saved["state"]
    async with rag_store() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM repair_graph.checkpoints WHERE thread_id=:id"),
            {"id": str(created["id"])},
        )
        assert count >= (
            3 if mode == "failure" else 4
        )  # Failure still retains input/load checkpoints.
    await manager.close()


async def test_repair_cancellation_and_interruption_preserve_prior_statuses(rag_store, broker_url):
    investigation_id = await seed_investigation(rag_store)
    provider = OfflineRepair("wait")
    manager = RepairManager(lambda: provider, rag_store, broker_url)
    created = await manager.create(investigation_id)
    async with asyncio.timeout(25):
        await provider.chat_started.wait()
    cancelled = await manager.cancel(created["id"])
    assert cancelled["status"] == "cancelled"
    async with rag_store.begin() as session:
        row = await session.get(Repair, created["id"])
        assert row is not None
        row.status = "verifying"
        async with connect_tools(created["id"], load_snapshot().id, broker_url) as tools:
            candidate = await tools.call("apply_candidate", {"patch": offline_patch().model_dump()})
        row.state = {**row.state, "attempts": [{"number": 1, "candidate": candidate}]}
        investigation = await session.get(Investigation, investigation_id)
        assert investigation and investigation.status == "completed"
        run = await session.get(Run, investigation.run_id)
        assert run and run.status == "reproduced"
    await manager.recover()
    interrupted = await manager.get(created["id"])
    assert interrupted["status"] == "interrupted"
    assert interrupted["state"]["verification"] is None
    reconciliation = interrupted["state"]["reconciliation"][0]
    assert reconciliation["live"] and not reconciliation["safe_to_resume"]
    assert reconciliation["candidate_hash"] == candidate["candidate_hash"]
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{broker_url}/candidates/{created['id']}/1/reconcile")
        assert not response.json()["live"]
    with pytest.raises(HTTPException) as error:
        await manager.create(uuid4())
    assert error.value.status_code == 404


async def test_shared_wall_clock_timeout_keeps_no_verification_claim(
    rag_store, broker_url, monkeypatch
):
    investigation_id = await seed_investigation(rag_store)
    monkeypatch.setattr(settings, "repair_timeout_seconds", 1)
    manager = RepairManager(lambda: OfflineRepair("wait"), rag_store, broker_url)
    created = await manager.create(investigation_id)
    await asyncio.gather(*list(manager.tasks.values()))
    saved = await manager.get(created["id"])
    assert saved["status"] == "error" and saved["error_code"] == "timeout"
    assert saved["state"]["verification"] is None
    await manager.close()


async def test_real_mcp_executor_outage_is_an_execution_error():
    async with connect_tools(uuid4(), load_snapshot().id, "http://127.0.0.1:1") as tools:
        with pytest.raises(RuntimeError, match="executor is unavailable"):
            await tools.call("apply_candidate", {"patch": offline_patch().model_dump()})
        assert tools.events[-1]["is_error"]
        assert tools.events[-1]["result"]["tool_error"]["kind"] == "execution"
