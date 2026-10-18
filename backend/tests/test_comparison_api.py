"""Deterministic API mutation fixtures; no model calls or persistent-row modifications."""

import copy

import httpx
from fastapi import FastAPI

from workbench.config import settings
from workbench.evaluator import experiment_store
from workbench.evaluator.experiment import read_trial
from workbench.evaluator.experiment_catalog import freeze
from workbench.evaluator.routes import router


async def test_comparison_is_read_only_and_inherits_guest_denial(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(settings, "guest_access", True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/evaluator/comparisons/m02-v1")).status_code == 403
        assert (
            await client.post("/api/evaluator/comparisons/m02-v1", json={"command": "anything"})
        ).status_code == 405
    monkeypatch.setattr(settings, "guest_access", False)


async def test_stored_comparison_mutation_fails_before_aggregation(monkeypatch):
    frozen = freeze()
    rows = [read_trial(c["id"]) for c in frozen["body"]["order"]]
    altered = copy.deepcopy(rows)
    final = next(r for r in altered if r and r.get("result"))
    final["result"]["ordinary"]["exit_code"] = 1

    async def records():
        return altered

    monkeypatch.setattr(experiment_store, "records", records)
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/evaluator/comparisons/m02-v1")
    assert response.status_code == 409
    assert "validation" in response.json()["detail"]
