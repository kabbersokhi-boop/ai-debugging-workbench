"""G2 deterministic contracts and oracle boundaries. No inference or project execution."""

import copy
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_repository_audit import candidate_for, completed_result, fixture_source, plan_for

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import independent
from workbench.repository_audit.contracts import Confirm
from workbench.repository_audit.execution import engine_id
from workbench.repository_audit.service import view
from workbench.repository_audit.verification import (
    Requirement,
    VerificationPlan,
    admit_plan,
    interpret,
    material,
    record,
    requirement,
)


def fixture_verification(runtime="python312", source=None, candidate=None, ordinary=None):
    source = source or fixture_source(runtime)
    candidate = candidate or candidate_for(source)
    ordinary = ordinary or (plan_for(source, candidate) | {"runtime": runtime})
    req = record(
        Requirement.model_validate(
            dict(
                snapshot_id=source["id"],
                statement="Addition returns the mathematical sum",
                expected_behavior="Integer sums including zeros and negative operands",
                input_domain="Finite integer operands in the declared examples",
                assumptions=["JSON integers"],
                ambiguities=[],
                approval="owner_approved",
                provenance={
                    "origin": "owner_authored_property",
                    "reference": "Synthetic arithmetic specification v1",
                    "excerpt": "add(a,b) returns a+b",
                    "excerpt_hash": digest("add(a,b) returns a+b"),
                    "justification": "Owner specification fixed independently of candidate",
                    "independent_of_candidate": True,
                },
            )
        )
    )
    plan = VerificationPlan.model_validate(
        dict(
            snapshot_id=source["id"],
            candidate_id=candidate["id"],
            candidate_hash=candidate["candidate_hash"],
            ordinary_plan_id=identity(ordinary),
            runtime=runtime,
            image_id=ordinary["image_id"],
            module="library.py" if runtime == "python312" else "index.js",
            export="add",
            assertions=[
                {"id": "zero", "requirement_id": req["id"], "args": [0, 0], "expected": 0},
                {"id": "negative", "requirement_id": req["id"], "args": [-3, 2], "expected": -1},
            ],
        )
    ).model_dump()
    verification = {"id": identity(plan), "plan": plan, "requirements": [req]}
    return {
        "snapshot": source,
        "candidate": candidate,
        "plan": ordinary,
        "verification": verification,
        "stage": "validation",
        "engine_id": independent.engine_id(),
        "ordinary_engine_id": engine_id(),
        "approval": {
            "local_owner": True,
            "candidate_id": candidate["id"],
            "plan_id": identity(ordinary),
            "approved_at": "2026-10-20T00:00:00+00:00",
            "verification_id": verification["id"],
            "stage": "validation",
            "approve_independent_plan": True,
        },
    }


def checked_plan(evidence):
    return admit_plan(
        evidence["snapshot"],
        evidence["candidate"],
        evidence["plan"],
        evidence["verification"]["plan"],
        evidence["verification"]["requirements"],
    )


def captured(plan, values):
    return {
        "status": "tests_passed",
        "ordinary": {
            "stdout": json.dumps(
                {
                    "version": "observations-v1",
                    "observations": [
                        {"id": a.id, "kind": "value", "value": v}
                        for a, v in zip(plan.assertions, values, strict=True)
                    ],
                }
            )
        },
    }


def test_versioned_identities_and_no_expected_values_in_probe_material():
    evidence = fixture_verification()
    plan = checked_plan(evidence)
    files = material(plan)
    inputs = json.loads(files["inputs.json"])
    assert set(inputs) == {"module", "export", "calls"}
    assert inputs["module"] == "/source/library.py"
    assert all(set(c) == {"id", "args", "kwargs"} for c in inputs["calls"])
    assert plan.adapter_hashes["probe.py"] == digest(files["probe.py"])
    mutated = copy.deepcopy(evidence["verification"]["plan"])
    mutated["assertions"][0]["expected"] = 42
    assert identity(mutated) != evidence["verification"]["id"]
    independent.check(evidence)


@pytest.mark.parametrize(
    "override",
    [
        {"version": "independent-plan-v0"},
        {"candidate_id": "f" * 64},
        {"snapshot_id": "f" * 64},
        {"candidate_hash": "f" * 64},
        {"ordinary_plan_id": "f" * 64},
        {"module": "../verifier/probe.py"},
        {"module": "missing.py"},
        {"export": "__dict__"},
        {"assertions": []},
        {"policy_hash": "f" * 64},
        {"adapter_hashes": {}},
        {"setup": [["python", "bad\x00argument"]]},
    ],
)
def test_invalid_unsupported_and_tampered_plans(override):
    e = fixture_verification()
    e["verification"]["plan"].update(override)
    with pytest.raises(ValueError):
        checked_plan(e)


def test_missing_duplicate_and_contradictory_assertions():
    for change in ("duplicate", "contradictory", "missing_requirement"):
        e = fixture_verification()
        checks = e["verification"]["plan"]["assertions"]
        if change == "duplicate":
            checks[1]["id"] = checks[0]["id"]
        elif change == "contradictory":
            checks[1]["args"] = checks[0]["args"]
        else:
            checks[0]["requirement_id"] = "f" * 64
        with pytest.raises(ValueError):
            checked_plan(e)


@pytest.mark.parametrize("change", ["unapproved", "ambiguous", "model_proposed", "tampered"])
def test_proposal_to_approval_boundary(change):
    # Deterministic model-output fixture: origin remains untrusted even after a checkbox.
    req = fixture_verification()["verification"]["requirements"][0]
    body = {k: v for k, v in req.items() if k != "id"}
    if change == "unapproved":
        body["approval"] = "unapproved"
    elif change == "ambiguous":
        body["ambiguities"] = ["Unresolved zero behavior"]
    elif change == "model_proposed":
        body["provenance"]["origin"] = "model_proposed_hypothesis"
    else:
        body["provenance"]["excerpt"] = "Candidate implementation says so"
    with pytest.raises(ValueError):
        requirement(record(Requirement.model_validate(body)))


def test_actual_assertions_required_and_host_comparison_distinguishes_controls():
    plan = checked_plan(fixture_verification())
    assert interpret(plan, captured(plan, [0, -1]))["status"] == "checks_passed"
    failed = interpret(plan, captured(plan, [0, 5]))
    assert failed["status"] == "assertions_failed"
    assert failed["checks"][1]["expected"] == -1
    assert failed["checks"][1]["observed"] == 5
    for output in (
        "",
        "{}",
        "[]",
        '{"version":"observations-v1","observations":[]}',
        captured(plan, [0, -1])["ordinary"]["stdout"] + "\n{}",
    ):
        assert (
            interpret(plan, {"status": "tests_passed", "ordinary": {"stdout": output}})["status"]
            == "invalid_evidence"
        )
    execution = captured(plan, [0, -1])
    execution["ordinary"]["output_truncated"] = True
    assert interpret(plan, execution)["status"] == "invalid_evidence"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("tests_failed", "check_execution_failed"),
        ("environment_preparation_failed", "verifier_preparation_failed"),
        ("timeout", "timeout"),
        ("cancelled", "cancelled"),
        ("infrastructure_error", "infrastructure_error"),
    ],
)
def test_nonbehavioral_failures_do_not_count_as_assertion_failure_or_pass(status, expected):
    assert interpret(checked_plan(fixture_verification()), {"status": status}) == {
        "status": expected,
        "checks": [],
    }


def test_explicit_approval_and_validation_required():
    e = fixture_verification()
    e["approval"]["approve_independent_plan"] = False
    with pytest.raises(ValueError):
        independent.check(e)
    e = fixture_verification()
    e["stage"] = e["approval"]["stage"] = "execution"
    with pytest.raises(KeyError):
        independent.check(e)
    with pytest.raises(ValueError):
        Confirm.model_validate(
            {
                "candidate_id": "a" * 64,
                "plan_id": "b" * 64,
                "approve_exact_plan": False,
                "confirm_local_execution": True,
            }
        )


def synthetic_validated_execution(monkeypatch):
    e = fixture_verification()
    plan = checked_plan(e)

    def execute(audit_id, snapshot, candidate, command_plan, cancel, verifier_files=None):
        result = completed_result(snapshot, candidate, command_plan, audit_id)
        result["container_id"] = str(uuid4())
        if verifier_files is not None:
            values = [a.expected for a in plan.assertions]
            if any(
                b"negative_control" in v
                for k, v in verifier_files.items()
                if k.startswith("control.")
            ):
                values = [{"negative_control": v} for v in values]
            result["ordinary"]["stdout"] = captured(plan, values)["ordinary"]["stdout"]
            result["verifier_hashes"] = {k: digest(v) for k, v in verifier_files.items()}
            result["sandbox"]["mounts"].append(
                {"Type": "volume", "Destination": "/verifier", "RW": False}
            )
        return result

    monkeypatch.setattr(independent.execution, "evaluate", execute)
    import threading

    aid = uuid4()
    validation = independent.evaluate(aid, e, threading.Event())
    independent.validate(validation, aid, e)
    assert validation["status"] == "validation_passed"
    e["stage"] = e["approval"]["stage"] = "execution"
    e["validation"] = {"audit_id": str(aid), "result": validation}
    aid = uuid4()
    result = independent.evaluate(aid, e, threading.Event())
    independent.validate(result, aid, e)
    assert result["status"] == "completed"
    return aid, e, result


def test_saved_g2_evidence_rechecks_every_identity_and_approval(monkeypatch):
    aid, e, result = synthetic_validated_execution(monkeypatch)
    row = SimpleNamespace(
        id=aid,
        candidate_id=e["candidate"]["id"],
        plan_id=identity(e["plan"]),
        status=result["status"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        evidence={**e, "result": result, "result_hash": identity(result)},
    )
    assert view(row)["status"] == "completed"
    for field in ("result", "approval", "validation", "verification"):
        broken = copy.deepcopy(row)
        broken.evidence.pop(field)
        assert view(broken)["status"] == "invalid_evidence"
        assert "result" not in view(broken)["evidence"]
    for field in (
        "candidate_id",
        "candidate_hash",
        "snapshot_id",
        "plan_id",
        "verification_id",
        "engine_id",
        "stage",
    ):
        broken = copy.deepcopy(row)
        broken.evidence["result"][field] = "wrong"
        broken.evidence["result_hash"] = identity(broken.evidence["result"])
        assert view(broken)["status"] == "invalid_evidence"
    for change in ("expected", "observation", "empty", "container", "controls"):
        broken = copy.deepcopy(row)
        if change == "expected":
            broken.evidence["verification"]["plan"]["assertions"][0]["expected"] = 99
        elif change == "observation":
            broken.evidence["result"]["independent"]["checks"][0]["observed"] = 99
        elif change == "empty":
            broken.evidence["result"]["independent"]["checks"] = []
        elif change == "container":
            broken.evidence["result"]["independent"]["execution"]["container_id"] = result[
                "ordinary"
            ]["container_id"]
        else:
            broken.evidence["validation"]["result"]["controls"] = []
        broken.evidence["result_hash"] = identity(broken.evidence["result"])
        assert view(broken)["status"] == "invalid_evidence"


async def test_g2_routes_absent_from_recorded_and_local_only(monkeypatch, tmp_path):
    import httpx
    from fastapi import FastAPI

    from workbench import release
    from workbench.repository_audit.routes import router

    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for route in ("requirements", "verification-plans"):
            assert (
                await client.post("/api/repository-audits/" + route, json={})
            ).status_code == 422
            assert (
                await client.post(
                    "/api/repository-audits/" + route,
                    json={},
                    headers={"Origin": "https://outside.example"},
                )
            ).status_code == 403
    (tmp_path / "index.html").write_text("recorded fixture")
    monkeypatch.setattr(release, "WEB", tmp_path)
    release.requests.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=release.app), base_url="http://release"
    ) as client:
        for route in ("requirements", "verification-plans", "runs"):
            assert (await client.get("/api/repository-audits/" + route)).status_code == 404
            assert (
                await client.post("/api/repository-audits/" + route, json={})
            ).status_code == 405
