"""Development scenarios only. Held-out behavioral outcomes are measured after freezing."""

import asyncio
from uuid import uuid4

import httpx
import pytest
import test_rag_integration as fixtures
import test_repair_integration as repair_fixtures
from test_rag_integration import OfflineProvider

from workbench.rag.retrieval import RepositoryRetriever
from workbench.rag.snapshot import load_snapshot, scenario, scenario_manifest
from workbench.repair.contracts import PatchProposal
from workbench.repair.mcp_client import connect_tools

rag_store = fixtures.rag_store
broker_url = repair_fixtures.broker_url
pytestmark = pytest.mark.integration


async def test_two_real_indexes_reject_cross_snapshot_context(rag_store):
    provider = OfflineProvider()
    retriever = RepositoryRetriever(provider, rag_store)
    a = load_snapshot()
    b = load_snapshot(scenario("shipping-threshold")["snapshot_id"])
    first, second = await retriever.index(a), await retriever.index(b)
    assert first != second
    before = len(provider.calls)
    assert await retriever.index(b) == second
    assert len(provider.calls) == before
    with pytest.raises(ValueError, match="snapshot"):
        await retriever.retrieve(b, first, "shipping threshold")
    result = await retriever.retrieve(b, second, "shipping threshold", "lexical")
    assert result.snapshot_id == b.id
    assert all(
        c.source_id in {x.source_id for x in result.candidates} for c in result.supplied_context
    )


@pytest.mark.parametrize("case_id", ["shipping-threshold", "decrement-skip", "clamp-zero"])
async def test_development_source_mcp_candidate_and_verification_identity(broker_url, case_id):
    case = scenario(case_id)
    snapshot = load_snapshot(case["snapshot_id"])
    source = next(f for f in snapshot.files if f.path.endswith("cart.js"))
    # Explicit OFFLINE verifier control, never attributed to the model or copied into its corpus.
    original = next(f for f in load_snapshot().files if f.path.endswith("cart.js"))
    healthy = original.content.replace(
        "sum + item.unitPriceCents, 0", "sum + item.unitPriceCents * item.quantity, 0"
    )
    proposal = PatchProposal.model_validate(
        {
            "snapshot_id": snapshot.id,
            "path": source.path,
            "original_sha256": source.sha256,
            "explanation": "OFFLINE development verifier control; no model inference",
            "edits": [{"old": source.content, "new": healthy}],
        }
    )
    repair_id = uuid4()
    async with httpx.AsyncClient(base_url=broker_url, timeout=70) as client:
        baseline = (
            await client.post("/original/verify", params={"snapshot_id": snapshot.id})
        ).json()
        assert baseline["source_snapshot"] == snapshot.id
        assert not next(c["passed"] for c in baseline["checks"] if c["name"] == case["issue_check"])
        async with connect_tools(repair_id, snapshot.id, broker_url) as tools:
            read = await tools.call(
                "read_source", {"path": source.path, "start_line": 1, "end_line": 65}
            )
            assert read["snapshot_id"] == snapshot.id
            candidate = await tools.call("apply_candidate", {"patch": proposal.model_dump()})
            checked = await tools.call(
                "verify_candidate", {"candidate_hash": candidate["candidate_hash"]}
            )
            assert checked["status"] == "passed", checked
            assert checked["source_snapshot"] == snapshot.id
            assert checked["scenario_expectations"] != ""
            assert checked["container_image_id"].startswith("sha256:")
            assert checked["artifact_id"] != checked["verifier_version"]
        await client.post(f"/repairs/{repair_id}/cleanup")


async def test_development_scenarios_reproduce_through_existing_api():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8010", timeout=10) as client:
        for case in scenario_manifest()["cases"]:
            if case["split"] != "development" or case["id"] == "cart-quantity":
                continue
            response = await client.post("/api/runs", json={"bug_id": case["id"]})
            response.raise_for_status()
            run_id = response.json()["id"]
            async with asyncio.timeout(65):
                while True:
                    row = (await client.get(f"/api/runs/{run_id}")).json()
                    if row["status"] not in ("queued", "running"):
                        break
                    await asyncio.sleep(0.25)
            assert row["status"] == "reproduced", row
            assert row["result"]["source_snapshot"] == case["snapshot_id"]
            assert len(row["result"]["behavioral_checks"]) == 12


async def test_remote_preview_rejects_commands_and_kills_nonresponsive_script(broker_url):
    import json

    import docker
    from test_repair import offline_patch

    from workbench.config import ROOT

    repair_id = uuid4()
    async with connect_tools(repair_id, load_snapshot().id, broker_url) as tools:
        candidate = await tools.call(
            "apply_candidate",
            {
                "patch": offline_patch(
                    "sum + item.unitPriceCents + (() => { while (true) {} })()"
                ).model_dump()
            },
        )
    async with httpx.AsyncClient(base_url=broker_url, timeout=20) as client:
        path = f"/candidates/{repair_id}/1/remote"
        assert (
            await client.post(path, json={"action": "evaluate", "script": "alert(1)"})
        ).status_code == 422
        assert (await client.post(path, json={"action": "reset"})).status_code == 200
        # The reduce callback executes only after an item is added, not on the empty bag.
        response = await client.post(path, json={"action": "add"})
        assert response.status_code in (503, 504)
    docker_client = docker.from_env()
    try:
        retained_containers = docker_client.containers.list(
            all=True, filters={"label": f"ai-debugging-workbench.repair={repair_id}-1"}
        )
        assert not retained_containers
        folder = ROOT / "artifacts/milestone-04"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "remote-timeout-record.json").write_text(
            json.dumps(
                {
                    "mode": "offline_security_probe",
                    "repair_id": str(repair_id),
                    "candidate": candidate,
                    "mcp_events": tools.events,
                    "remote_status": response.status_code,
                    "remote_response": response.json(),
                    "retained_containers": len(retained_containers),
                    "verification_performed": False,
                },
                indent=2,
            )
        )
    finally:
        docker_client.close()
