"""Known historical verifier inspection is separate from current execution authority."""

import copy
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from workbench.config import ROOT
from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import independent
from workbench.repository_audit.service import validate_saved, view
from workbench.repository_audit.verification import VerificationPlan, admit_plan
from workbench.repository_audit.verifiers import (
    CURRENT_VERIFIER,
    LEGACY_VERIFIER,
    verifier_hashes,
    verifier_sources,
)

HISTORICAL = ROOT / "docs/reports/assets/generalized-patch-audit-g02/accepted"
RECORDS = [
    path
    for path in sorted(HISTORICAL.glob("*.json"))
    if json.loads(path.read_text()).get("evidence", {}).get("result", {}).get("version")
    == "repository-independent-result-v1"
]


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.name)
def test_original_evidence_and_outcomes_remain_exactly_inspectable(path):
    original = json.loads(path.read_text())
    saved = copy.deepcopy(original)
    validate_saved(saved["evidence"], saved["id"])
    row = SimpleNamespace(
        id=saved["id"],
        candidate_id=saved["candidate_id"],
        plan_id=saved["plan_id"],
        status=saved["status"],
        evidence=saved["evidence"],
        created_at=datetime.fromisoformat(saved["created_at"]),
        updated_at=datetime.fromisoformat(saved["updated_at"]),
    )
    assert view(row) == original
    assert saved == original
    plan = saved["evidence"]["verification"]["plan"]
    assert "verifier_version" not in plan
    assert plan["adapter_hashes"] == verifier_hashes(LEGACY_VERIFIER)
    with pytest.raises(ValueError, match="Historical observation verifier is read-only"):
        independent.check(saved["evidence"])


def test_current_plan_is_explicit_and_cannot_reuse_old_validation():
    path = next(p for p in RECORDS if "node-positive-validation" in p.name)
    original = json.loads(path.read_text())
    e = copy.deepcopy(original["evidence"])
    old_plan = e["verification"]["plan"]
    new_plan = VerificationPlan.model_validate(
        {
            **old_plan,
            "verifier_version": CURRENT_VERIFIER,
            "adapter_hashes": verifier_hashes(),
            "adapter_sources": verifier_sources(),
        }
    ).model_dump()
    assert new_plan["verifier_version"] == "json-observer-v2"
    assert identity(new_plan) != e["verification"]["id"]
    assert new_plan["adapter_hashes"]["probe.cjs"] != old_plan["adapter_hashes"]["probe.cjs"]
    e["verification"] = {**e["verification"], "id": identity(new_plan), "plan": new_plan}
    e["stage"] = e["approval"]["stage"] = "execution"
    e["engine_id"] = independent.engine_id()
    e["approval"]["verification_id"] = identity(new_plan)
    e["validation"] = {"audit_id": original["id"], "result": original["evidence"]["result"]}
    with pytest.raises(ValueError, match="verification_id binding mismatch"):
        independent.check(e)


@pytest.mark.parametrize("version", [LEGACY_VERIFIER, CURRENT_VERIFIER, "untrusted-observer-v1"])
def test_matching_supplied_code_and_hashes_are_not_a_trust_registry(version):
    original = json.loads(RECORDS[0].read_text())["evidence"]
    value = copy.deepcopy(original["verification"]["plan"])
    value["verifier_version"] = version
    sources = verifier_sources()
    sources["probe.cjs"] = "process.stdout.write('arbitrary verifier');\n"
    value["adapter_sources"] = sources
    value["adapter_hashes"] = {name: digest(code) for name, code in sources.items()}
    with pytest.raises(ValueError):
        admit_plan(
            original["snapshot"],
            original["candidate"],
            original["plan"],
            value,
            original["verification"]["requirements"],
            for_execution=False,
        )


def test_original_artifact_manifest_stays_intact():
    root = HISTORICAL.parent
    manifest = json.loads((root / "manifest.json").read_text())
    for name, wanted in manifest["files"].items():
        assert digest((root / name).read_bytes()) == wanted
    assert len(RECORDS) == 8


async def test_retired_plan_is_rejected_before_new_record_or_execution(monkeypatch):
    from workbench.repository_audit import service

    e = json.loads(RECORDS[0].read_text())["evidence"]

    async def saved_material(*args):
        return e["snapshot"], e["candidate"], e["plan"]

    async def saved_verification(*args):
        return e["verification"]

    def forbidden_persistence(*args, **kwargs):
        raise AssertionError("Legacy execution reached persistence")

    monkeypatch.setattr(service, "material", saved_material)
    monkeypatch.setattr(service, "load", saved_verification)
    monkeypatch.setattr(service, "sessions", forbidden_persistence)
    manager = service.RepositoryAuditManager()
    with pytest.raises(ValueError, match="Historical observation verifier is read-only"):
        await manager.create(
            e["candidate"]["id"],
            identity(e["plan"]),
            e["verification"]["id"],
            stage="validation",
            approve_independent_plan=True,
        )
    assert not manager.jobs
