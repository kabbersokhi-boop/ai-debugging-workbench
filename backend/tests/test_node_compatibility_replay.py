"""Deterministic addendum replay and combined accounting, with original G3 unchanged."""

import copy
import json
import shutil

import httpx
import pytest
from fastapi import FastAPI

from workbench.config import ROOT
from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit.campaign import bind_audit, load_campaign, retained_compatibility
from workbench.repository_audit.routes import router

ORIGINAL = ROOT / "evaluation/repository-examples/g3"
ADDENDUM = ROOT / "evaluation/repository-examples/g3-node-compatibility"


@pytest.fixture(scope="module")
def retained():
    return retained_compatibility(ADDENDUM, ORIGINAL)


def test_separate_original_addendum_and_combined_unique_denominators(retained):
    summary, audits = retained
    assert len(audits) == 12
    assert summary["original_g3_counts"]["genuine_candidates_executed"] == 4
    assert summary["original_g3_counts"]["candidate_outcomes"]["unsupported_source"] == 1
    assert summary["counts"]["genuine_candidates_executed"] == 2
    assert summary["counts"]["candidate_audits"] == 4
    assert summary["combined_coverage"] == {
        "selected_distinct_candidates": 6,
        "evaluated_distinct_candidates": 6,
        "formal_audits": 12,
        "ordinary_passing_candidates": 5,
        "ordinary_failing_candidates": 1,
        "additional_independent_defects": 0,
        "unsupported_or_incomplete": 0,
        "invalid_or_disputed": 0,
        "repeat_disagreements": 0,
    }


def test_engine_policy_and_frozen_prepared_plan_cannot_be_substituted(retained):
    summary, audits = retained
    declaration, cases, _ = load_campaign(ADDENDUM)
    row = next(r for r in summary["rows"] if r["role"] == "candidate")
    case = next(c for c in cases if c["key"] == row["case"])
    for key in ("engine_id", "ordinary_engine_id"):
        changed = copy.deepcopy(declaration)
        changed[key] = "0" * 64
        with pytest.raises(ValueError, match="engine or intake policy"):
            bind_audit(ADDENDUM, case, audits[row["run_id"]], "candidate", changed)


def test_changed_dependency_or_prepared_plan_material_breaks_freeze(tmp_path):
    root = tmp_path / "addendum"
    shutil.copytree(ADDENDUM, root)
    (root / "dependency-capsule.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen campaign material changed"):
        retained_compatibility(root, ORIGINAL)


async def test_addendum_api_download_and_original_view_are_distinct(retained):
    summary, audits = retained
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        original = (await client.get("/api/repository-audits/campaigns/g3")).json()
        assert original["counts"]["genuine_candidates_executed"] == 4
        response = await client.get("/api/repository-audits/campaigns/g3-node-compatibility")
        assert response.status_code == 200
        assert response.json() == summary
        row = next(r for r in summary["rows"] if r["role"] == "candidate")
        path = "/api/repository-audits/campaigns/g3-node-compatibility/runs/" + row["run_id"]
        download = await client.get(path)
        assert download.json() == audits[row["run_id"]]
        assert identity((await client.get(path)).json()) == identity(download.json())
        assert "attachment" in download.headers["content-disposition"]


def test_hash_manifest_is_content_identity_for_all_immutable_results():
    manifest = json.loads((ADDENDUM / "results/manifest.json").read_text())
    for name, checksum in manifest["files"].items():
        assert digest((ADDENDUM / "results" / name).read_bytes()) == checksum
