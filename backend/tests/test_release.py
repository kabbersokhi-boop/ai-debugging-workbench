"""Offline release boundaries and immutable scenario contracts."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from workbench.access import check_origin, token_reservation
from workbench.config import ROOT, settings
from workbench.rag.snapshot import APPROVED_PATHS, chunk_snapshot, load_snapshot, scenario_manifest
from workbench.release import app, requests
from workbench.repair.broker import verification_binding
from workbench.repair.contracts import apply_patch


def test_frozen_scenarios_have_distinct_sources_and_explicit_boundary():
    cases = scenario_manifest()["cases"]
    assert len(cases) == 12
    assert len({c["snapshot_id"] for c in cases}) == 12
    assert len({c["behavior"] for c in cases}) == 4
    assert sum(c["split"] == "development" for c in cases) == 4
    for case in cases:
        snapshot = load_snapshot(case["snapshot_id"])
        assert {f.path for f in snapshot.files} == APPROVED_PATHS
        chunks = chunk_snapshot(snapshot)
        assert chunks and all(c.path in APPROVED_PATHS for c in chunks)
        assert not any("evals/" in c.path or "verifier.py" in c.path for c in chunks)
        if case["id"] != "cart-quantity":
            source = next(f for f in snapshot.files if f.path.endswith("cart.js"))
            assert source.origin_path == f"fixtures/scenarios/{case['id']}/cart.js"
    with pytest.raises(ValueError):
        load_snapshot("../retail-snapshot.json")
    with pytest.raises(ValueError):
        load_snapshot("f" * 64)


def test_verification_identity_includes_source_runtime_and_scenario():
    cases = scenario_manifest()["cases"]
    original = verification_binding(cases[0]["snapshot_id"], "a" * 64, "sha256:image-a")
    for other in (
        verification_binding(cases[1]["snapshot_id"], "a" * 64, "sha256:image-a"),
        verification_binding(cases[0]["snapshot_id"], "b" * 64, "sha256:image-a"),
        verification_binding(cases[0]["snapshot_id"], "a" * 64, "sha256:image-b"),
    ):
        assert original["artifact_id"] != other["artifact_id"]
    assert original == verification_binding(cases[0]["snapshot_id"], "a" * 64, "sha256:image-a")


def test_patch_cannot_cross_scenarios():
    from test_repair import offline_patch

    other = load_snapshot(scenario_manifest()["cases"][1]["snapshot_id"])
    with pytest.raises(ValueError, match="snapshot"):
        apply_patch(other, offline_patch())


def test_guest_cross_origin_and_conservative_reservations():
    request = Request(
        {"type": "http", "method": "POST", "headers": [(b"origin", b"https://unrelated.example")]}
    )
    with pytest.raises(HTTPException) as failure:
        check_origin(request)
    assert failure.value.status_code == 403
    assert token_reservation("/api/x/investigations", "POST") == settings.provider_max_requests * (
        settings.model_input_token_limit + settings.model_output_token_limit
    )
    assert token_reservation("/api/x/repairs", "POST") > settings.repair_output_budget
    assert token_reservation("/api/x/repairs", "GET") == 0


async def test_public_recorded_surface_has_no_execution_or_private_history(monkeypatch, tmp_path):
    from workbench import release

    (tmp_path / "index.html").write_text("offline release health fixture")
    monkeypatch.setattr(release, "WEB", tmp_path)
    release.guests.clear()
    requests.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://release"
    ) as client:
        health = await client.get("/api/health")
        assert health.json()["provider_token_budget"] == 0
        manifest = (await client.get("/api/recordings")).json()
        record = (await client.get(f"/api/recordings/{manifest['records'][0]['id']}")).json()
        assert record["recording"]["historical"]
        assert record["repair"]["status"] == "verified"
        assert len(record["recording_sha256"]) == 64
        assert "frame-ancestors 'none'" in health.headers["content-security-policy"]
        for path in (
            "/api/evaluator/tasks",
            "/api/evaluator/runs",
            "/api/runs",
            "/api/investigations/x",
            "/api/repairs/x",
            "/retail/cart.js",
            "/api/recorded-assets/secret",
        ):
            assert (await client.get(path)).status_code == 404
        for path in ("/api/runs", "/api/recordings/x", "/candidates"):
            assert (await client.post(path, json={})).status_code == 405
        for _ in range(600):
            await client.get("/api/mode")
        assert (await client.get("/api/mode")).status_code == 429
    requests.clear()


def test_recordings_are_saved_actual_records_not_live_fixtures():
    record = json.loads((ROOT / "recordings/m3-live-success.json").read_text())
    assert record["mode"] == "live_nvidia"
    assert record["recording"]["mode"] == "recorded_live_nvidia"
    assert record["repair"]["state"]["provider_calls"]
    assert record["repair"]["id"] != str(uuid4())


async def test_frozen_experiment_transport_rejects_expired_or_exhausted_budget(
    tmp_path, monkeypatch
):
    import importlib.util
    from datetime import UTC, datetime, timedelta

    from workbench.rag.provider import ProviderError

    spec = importlib.util.spec_from_file_location(
        "budget_probe", ROOT / "scripts/evaluate_repairs.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUTPUT", tmp_path)
    for deadline, calls in (
        (datetime.now(UTC) - timedelta(seconds=1), 0),
        (datetime.now(UTC) + timedelta(seconds=60), 256),
    ):
        ledger = {
            "deadline": deadline.isoformat(),
            "http_requests": calls,
            "reserved_output_tokens": 0,
        }
        transport = module.BudgetTransport(ledger)
        with pytest.raises(ProviderError, match="budget exhausted"):
            await transport.handle_async_request(
                httpx.Request("POST", "https://provider.invalid", json={"max_tokens": 2000})
            )
        assert ledger["http_requests"] == calls
        await transport.aclose()
    assert not (tmp_path / "budget.json").exists()
