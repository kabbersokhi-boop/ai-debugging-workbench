"""Prepared inputs preserve frozen bytes and grant no execution authority."""

import json

import httpx
from fastapi import FastAPI

from workbench.config import ROOT, settings
from workbench.release import app as recorded
from workbench.repository_audit.routes import router


async def test_prepared_examples_match_frozen_inputs_and_require_fresh_approval(monkeypatch):
    monkeypatch.setattr(settings, "guest_access", False)
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/repository-audits/prepared-examples")
        assert response.status_code == 200
        root = ROOT / "evaluation/repository-examples/g2"
        frozen = json.loads((root / "examples.json").read_text())
        items = response.json()["examples"]
        assert {x["key"] for x in items} == {"python-positive", "node-positive"}
        for item in items:
            original = next(x for x in frozen["examples"] if x["key"] == item["key"])
            assert item == {
                **original,
                "patch": (root / original["patch"]).read_text(),
                "requirement": {**original["requirement"], "approval": "unapproved"},
            }
            assert not any(k in item for k in ("plan_id", "validation_run_id", "snapshot_id"))
        monkeypatch.setattr(settings, "guest_access", True)
        assert (await client.get("/api/repository-audits/prepared-examples")).status_code == 403
    assert not any(
        getattr(route, "path", "").startswith("/api/repository-audits") for route in recorded.routes
    )
