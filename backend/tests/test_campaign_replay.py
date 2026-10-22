"""Replay immutable public evidence offline; never execute the downloaded project code."""

import copy
import json
import shutil
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from workbench.config import ROOT
from workbench.evaluator.catalog import identity
from workbench.repository_audit.campaign import bind_audit, load_campaign, retained_campaign
from workbench.repository_audit.routes import router
from workbench.repository_audit.service import view

FOLDER = ROOT / "evaluation/repository-examples/g3"


@pytest.fixture(scope="module")
def retained():
    return retained_campaign(FOLDER)


def test_actual_evidence_replays_and_counts_every_declared_case(retained):
    summary, audits = retained
    assert len(audits) == 28
    assert summary["counts"] == {
        "selected_candidates": 6,
        "genuine_candidates_executed": 4,
        "genuine_candidates_admitted": 5,
        "planned_candidate_audits": 12,
        "candidate_audits": 8,
        "control_validations": 10,
        "reference_audits": 5,
        "alternative_audits": 5,
        "fresh_environments": 56,
        "repeat_disagreements": 0,
        "candidate_outcomes": {
            "ordinary_pass_independent_pass": 3,
            "ordinary_failure": 1,
            "unsupported_environment": 1,
            "unsupported_source": 1,
        },
    }
    for audit in audits.values():
        row = SimpleNamespace(
            id=audit["id"],
            candidate_id=audit["candidate_id"],
            plan_id=audit["plan_id"],
            status=audit["status"],
            evidence=audit["evidence"],
            created_at=datetime.fromisoformat(audit["created_at"]),
            updated_at=datetime.fromisoformat(audit["updated_at"]),
        )
        assert view(row) == audit


def test_candidate_requirement_and_control_substitution_rejected(retained):
    summary, audits = retained
    declaration, cases, _ = load_campaign(FOLDER)
    case = cases[0]
    entry = next(
        e for e in summary["rows"] if e["case"] == case["key"] and e["role"] == "candidate"
    )
    audit = audits[entry["run_id"]]
    for field, value in (("revision", "f" * 40), ("base_commit", "f" * 40)):
        changed = copy.deepcopy(case)
        changed[field] = value
        with pytest.raises(ValueError, match="identity mismatch"):
            bind_audit(FOLDER, changed, audit, "candidate", declaration)
    changed = copy.deepcopy(case)
    changed["assertions"][0]["expected"] = "wrong"
    with pytest.raises(ValueError, match="assertions changed"):
        bind_audit(FOLDER, changed, audit, "candidate", declaration)
    changed = copy.deepcopy(case)
    changed["requirement"]["statement"] = "Altered requirement"
    with pytest.raises(ValueError, match="requirement identity mismatch"):
        bind_audit(FOLDER, changed, audit, "candidate", declaration)
    control = next(
        e for e in summary["rows"] if e["case"] == case["key"] and e["role"] == "control"
    )
    with pytest.raises(ValueError, match="Control substituted"):
        bind_audit(FOLDER, case, audits[control["run_id"]], "candidate", declaration)


def test_tampered_retained_manifest_is_not_a_scorecard(tmp_path):
    target = tmp_path / "g3"
    shutil.copytree(FOLDER, target)
    (target / "results/adjudications.json").write_text("{}")
    with pytest.raises(ValueError, match="material changed"):
        retained_campaign(target)


async def test_campaign_api_reopens_and_downloads_exact_validated_evidence(retained):
    summary, audits = retained
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        response = await client.get("/api/repository-audits/campaigns/g3")
        assert response.status_code == 200
        assert response.json() == summary
        row = next(r for r in summary["rows"] if r["role"] == "candidate")
        path = "/api/repository-audits/campaigns/g3/runs/" + row["run_id"]
        download = await client.get(path)
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]
        assert identity(download.json()) == identity(audits[row["run_id"]])
        assert (await client.get(path)).json() == download.json()
        assert (
            await client.get("/api/repository-audits/campaigns/g3/runs/" + str(uuid4()))
        ).status_code == 404


async def test_bad_campaign_material_cannot_display_a_pass(tmp_path, monkeypatch):
    from workbench.repository_audit import routes

    target = tmp_path / "g3"
    shutil.copytree(FOLDER, target)
    index = json.loads((target / "results/index.json").read_text())
    index["entries"][0]["audit_hash"] = "0" * 64
    (target / "results/index.json").write_text(json.dumps(index))
    monkeypatch.setattr(routes, "CAMPAIGN_ROOT", target)
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        response = await client.get("/api/repository-audits/campaigns/g3")
        assert response.status_code == 409
        assert "failed validation" in response.text
