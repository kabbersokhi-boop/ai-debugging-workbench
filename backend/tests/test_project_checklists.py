"""Reusable declarations, exact application binding, and report/CLI approval boundaries."""

import copy
import json

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from test_repository_audit import IMAGE, candidate_for, fixture_source

from workbench.config import settings
from workbench.evaluator.catalog import digest, identity
from workbench.release import app as recorded
from workbench.repository_audit import checklists
from workbench.repository_audit.checklists import (
    Checklist,
    compatibility,
    compile_plans,
    validate_use,
)
from workbench.repository_audit.cli import approval_id, main
from workbench.repository_audit.report import block, render_report
from workbench.repository_audit.routes import router


def declaration(source=None):
    source = source or fixture_source()
    excerpt = "Return the sum of the two integer arguments."
    return {
        "version": "project-checklist-v1",
        "name": "Integer addition",
        "revision": 1,
        "repository": source["repository"],
        "supported_sources": [
            {"base_commit": source["base_commit"], "file_hashes": dict(source["file_hashes"])}
        ],
        "approved_paths": ["library.py"],
        "runtime": "python312",
        "tests": ["python", "-m", "pytest", "-q"],
        "test_description": "Unchanged synthetic integer tests",
        "module": "library.py",
        "export": "add",
        "requirements": [
            {
                "statement": excerpt,
                "expected_behavior": excerpt,
                "input_domain": "Small JSON integers",
                "assumptions": [],
                "ambiguities": [],
                "provenance": {
                    "origin": "owner_authored_property",
                    "reference": "fixture contract",
                    "excerpt": excerpt,
                    "excerpt_hash": digest(excerpt),
                    "justification": "Authored separately from both candidate patches",
                    "independent_of_candidate": True,
                },
            }
        ],
        "assertions": [{"id": "sum", "requirement_index": 0, "args": [1, 2], "expected": 3}],
    }


def test_two_patches_reuse_declarations_but_bind_distinct_plans_and_exact_evidence():
    source = fixture_source()
    first = candidate_for(source)
    from test_repository_audit import patch_for

    from workbench.repository_audit.admission import admit
    from workbench.repository_audit.contracts import Import

    second = admit(
        source,
        Import(
            snapshot_id=source["id"],
            approved_paths=["library.py"],
            patch=patch_for(source, replacement="def add(a, b):\n    return a * b\n"),
        ),
    )
    checklist = Checklist.model_validate(declaration(source))
    first_plan, first_checks, first_use = compile_plans(checklist, source, first, IMAGE)
    second_plan, second_checks, second_use = compile_plans(checklist, source, second, IMAGE)
    assert first_use["checklist_id"] == second_use["checklist_id"]
    assert first_checks["requirements"] == second_checks["requirements"]
    assert first_use["id"] != second_use["id"] and first_plan["id"] != second_plan["id"]
    validate_use(first_use, source, first, first_plan["plan"], first_checks)
    with pytest.raises(ValueError, match="bound"):
        validate_use(first_use, source, second, second_plan["plan"], second_checks)
    tampered = copy.deepcopy(first_use)
    tampered["checklist"]["assertions"][0]["expected"] = 99
    with pytest.raises(ValueError, match="identity"):
        validate_use(tampered, source, first, first_plan["plan"], first_checks)


@pytest.mark.parametrize(
    "change,status",
    [
        ("repository", "incompatible"),
        ("revision", "outdated"),
        ("hash", "incompatible"),
        ("scope", "incompatible"),
        ("verifier", "outdated"),
    ],
)
def test_incompatible_and_outdated_checklists_are_explicit_and_never_compile(change, status):
    source, candidate = fixture_source(), candidate_for()
    value = declaration(source)
    if change == "repository":
        value["repository"] = "other/project"
    if change == "revision":
        value["supported_sources"][0]["base_commit"] = "b" * 40
    if change == "hash":
        value["supported_sources"][0]["file_hashes"]["library.py"] = "c" * 64
    if change == "scope":
        value["approved_paths"] = ["other.py"]
    if change == "verifier":
        value["verifier_version"] = "json-observer-v1"
    obj = Checklist.model_validate(value)
    match = compatibility(obj, source, candidate)
    assert match["status"] == status and match["reasons"] and not match["execution_authorized"]
    with pytest.raises(ValueError):
        compile_plans(obj, source, candidate, IMAGE)


def test_fresh_execution_rejects_retired_verifier_but_historical_checklist_binding_reopens():
    source, candidate = fixture_source(), candidate_for()
    obj = Checklist.model_validate(declaration(source))
    ordinary, verification, use = compile_plans(obj, source, candidate, IMAGE)
    original = checklists.CURRENT_VERIFIER
    try:
        checklists.CURRENT_VERIFIER = "json-observer-next"
        assert compatibility(obj, source, candidate)["status"] == "outdated"
        validate_use(use, source, candidate, ordinary["plan"], verification)
        with pytest.raises(ValueError):
            validate_use(use, source, candidate, ordinary["plan"], verification, historical=False)
    finally:
        checklists.CURRENT_VERIFIER = original


@pytest.mark.parametrize("field", ["approval", "approve_exact_plan", "validation_run_id"])
def test_portable_checklists_cannot_embed_reusable_approvals(field):
    value = declaration()
    value[field] = True
    with pytest.raises(ValidationError):
        Checklist.model_validate(value)


async def test_checklist_routes_are_local_only_and_recorded_server_has_no_authority(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(settings, "guest_access", False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/repository-audits/checklists/validate", json=declaration()
        )
        assert response.status_code == 200 and not response.json()["execution_authorized"]
        monkeypatch.setattr(settings, "guest_access", True)
        assert (
            await client.post("/api/repository-audits/checklists/validate", json=declaration())
        ).status_code == 403
    assert not any(
        getattr(r, "path", "").startswith("/api/repository-audits") for r in recorded.routes
    )


def test_cli_rejects_changed_exact_preparation_before_any_execution(tmp_path, capsys):
    value = {"checklist_use": {"id": "a" * 64}}
    fingerprint = approval_id(value)
    value["checklist_use"]["id"] = "b" * 64
    prepared = tmp_path / "plan.json"
    prepared.write_text(json.dumps(value))
    assert (
        main(
            [
                "controls",
                "--preparation",
                str(prepared),
                "--approve-exact",
                fingerprint,
                "--out-dir",
                str(tmp_path / "evidence"),
            ]
        )
        == 2
    )
    assert "Approval fingerprint differs" in capsys.readouterr().out
    assert not (tmp_path / "evidence").exists()


def test_report_escapes_untrusted_fences_and_distinguishes_missing_checks():
    text = "x\n```md\n# malicious\n````\n"
    assert block(text).startswith("`````\n")
    source, candidate = fixture_source(), candidate_for()
    plan, _, _ = compile_plans(
        Checklist.model_validate(declaration(source)), source, candidate, IMAGE
    )
    audit = {
        "id": "example",
        "status": "running",
        "candidate_id": candidate["id"],
        "evidence": {
            "snapshot": source,
            "candidate": candidate,
            "plan": plan["plan"],
            "approval": {"local_owner": True},
        },
    }
    report = render_report(audit)
    assert "no completed evidence" in report and "not configured" in report
    assert "Passing applies only to declared checks" in report
    assert identity(plan["plan"]) == plan["id"]


def test_published_checklist_schema_matches_the_runtime_contract():
    from workbench.config import ROOT

    schema = json.loads((ROOT / "schemas/project-checklist-v1.schema.json").read_text())
    assert schema == Checklist.model_json_schema()


async def test_broker_rejects_forged_checklist_binding_before_execution():
    from workbench.repository_audit import independent
    from workbench.repository_audit.broker import install

    source, candidate = fixture_source(), candidate_for()
    ordinary, verification, use = compile_plans(
        Checklist.model_validate(declaration(source)), source, candidate, IMAGE
    )
    altered = copy.deepcopy(use)
    altered["checklist"]["assertions"][0]["expected"] = 99
    altered["id"] = identity({k: v for k, v in altered.items() if k != "id"})
    app = FastAPI()
    install(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/repository-audits/00000000-0000-0000-0000-000000000001",
            json={
                "snapshot": source,
                "candidate": candidate,
                "plan": ordinary["plan"],
                "engine_id": independent.engine_id(),
                "verification": verification,
                "stage": "validation",
                "checklist_use": altered,
                "approval": {
                    "local_owner": True,
                    "plan_id": ordinary["id"],
                    "candidate_id": candidate["id"],
                    "checklist_use_id": altered["id"],
                    "verification_id": verification["id"],
                    "stage": "validation",
                    "approve_independent_plan": True,
                },
            },
        )
    assert response.status_code == 422


def test_saved_checklist_approval_cannot_silently_lose_its_application():
    from workbench.repository_audit.service import validate_saved

    source, candidate = fixture_source(), candidate_for()
    ordinary, verification, use = compile_plans(
        Checklist.model_validate(declaration(source)), source, candidate, IMAGE
    )
    evidence = {
        "snapshot": source,
        "candidate": candidate,
        "plan": ordinary["plan"],
        "verification": verification,
        "checklist_use": use,
        "stage": "validation",
        "approval": {
            "local_owner": True,
            "plan_id": ordinary["id"],
            "candidate_id": candidate["id"],
            "approved_at": "2026-11-01T00:00:00Z",
            "verification_id": verification["id"],
            "stage": "validation",
            "approve_independent_plan": True,
            "checklist_use_id": use["id"],
        },
    }
    validate_saved(evidence, "example")
    del evidence["checklist_use"]
    with pytest.raises(ValueError, match="Missing checklist"):
        validate_saved(evidence, "example")
