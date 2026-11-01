"""Exact replay identity regressions; synthetic transport, real saved-evidence validators."""

import ast
import copy
import json
import threading
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from test_generated_verifier import setup
from test_repository_audit import completed_result

from workbench.config import settings
from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import execution, generated, routes
from workbench.repository_audit.cli import main
from workbench.repository_audit.replay import prepare_replay, replay_plan
from workbench.repository_audit.service import validate_saved


@pytest.fixture
def saved_failure(monkeypatch, request):
    plan, e = setup()
    if getattr(request, "param", "first_truthy") == "integer_sort":
        from workbench.repository_audit.generated import GeneratedPlan, Search
        from workbench.repository_audit.verification import Requirement, record

        req = {k: v for k, v in e["verification"]["requirements"][0].items() if k != "id"}
        statement = "Return integers in ascending order, preserving duplicates."
        req.update(
            statement=statement, expected_behavior=statement, input_domain="Lists of zero and one"
        )
        req["provenance"].update(excerpt=statement, excerpt_hash=digest(statement))
        requirement = record(Requirement.model_validate(req))
        plan = GeneratedPlan.model_validate(
            {
                **plan.model_dump(),
                "requirement_id": requirement["id"],
                "search": Search(property="integer_sort", atoms=[0, 1]).model_dump(),
            }
        )
        e["verification"] = {
            "id": identity(plan.model_dump()),
            "plan": plan.model_dump(),
            "requirements": [requirement],
        }

    def transport(audit_id, snapshot, candidate, command, cancel, files=None):
        result = completed_result(snapshot, candidate, command, audit_id)
        result["container_id"] = str(uuid4())
        if files is not None:
            calls = json.loads(files["inputs.json"])["calls"]
            if "control.py" in files:
                assignment = ast.parse(files["control.py"]).body[1]
                values = json.loads(ast.literal_eval(assignment.value.args[0]))
            else:
                values = [
                    sorted(c["args"][0], reverse=True)
                    if plan.search.property == "integer_sort"
                    else next((v for v in c["args"][0] if v and not isinstance(v, str)), None)
                    for c in calls
                ]
            result["ordinary"]["stdout"] = json.dumps(
                {
                    "version": "observations-v1",
                    "observations": [
                        {"id": c["id"], "kind": "value", "value": v}
                        for c, v in zip(calls, values, strict=True)
                    ],
                }
            )
            result["verifier_hashes"] = {k: digest(v) for k, v in files.items()}
            result["sandbox"]["mounts"].append(
                {"Type": "volume", "Destination": "/verifier", "RW": False}
            )
        return result

    monkeypatch.setattr(execution, "evaluate", transport)
    e["ordinary_engine_id"] = execution.engine_id()
    e["stage"] = "validation"
    e["approval"] = {
        "local_owner": True,
        "candidate_id": e["candidate"]["id"],
        "plan_id": identity(e["plan"]),
        "approved_at": "2026-11-01T00:00:00+00:00",
        "verification_id": e["verification"]["id"],
        "stage": "validation",
        "approve_independent_plan": True,
    }
    control_id = uuid4()
    controls = generated.evaluate(control_id, e, threading.Event())
    generated.validate(controls, control_id, e)
    assert controls["status"] == "validation_passed"
    e["stage"] = e["approval"]["stage"] = "execution"
    e["validation"] = {"audit_id": str(control_id), "result": controls}
    audit_id = uuid4()
    result = generated.evaluate(audit_id, e, threading.Event())
    e.update(result=result, result_hash=identity(result))
    validate_saved(e, audit_id)
    assert result["counterexample"] is not None
    audit = {
        "id": str(audit_id),
        "status": result["status"],
        "candidate_id": plan.candidate_id,
        "plan_id": plan.ordinary_plan_id,
        "evidence": e,
    }
    prepared = {
        "ordinary": {"id": plan.ordinary_plan_id, "plan": e["plan"]},
        "verification": e["verification"],
    }
    return audit, copy.deepcopy(prepared), plan.search.model_dump()


def test_unchanged_exact_replay_derives_original_identity_and_only_retained_input(saved_failure):
    audit, prepared, search = saved_failure
    before = copy.deepcopy(audit)
    result = prepare_replay(audit, prepared, search)
    original = audit["evidence"]["verification"]["plan"]
    assert result == {
        **original,
        "search": {**original["search"], "replay_inputs": [["a"]], "reduction_rounds": 0},
    }
    assert audit == before
    assert identity(result) != identity(original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("property", "integer_sort"),
        ("atoms", [0, 1]),
        ("max_length", 2),
        ("seed", 2),
        ("cases", 8),
        ("replay_inputs", [["ready"]]),
        ("reduction_rounds", 2),
    ],
)
def test_exact_replay_rejects_changed_property_domain_and_search(saved_failure, field, value):
    audit, prepared, search = saved_failure
    with pytest.raises(ValueError):
        prepare_replay(audit, prepared, {**search, field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("module", "other.py"),
        ("export", "other"),
        ("snapshot_id", "a" * 64),
        ("candidate_id", "a" * 64),
        ("candidate_hash", "a" * 64),
        ("ordinary_plan_id", "a" * 64),
        ("image_id", "sha256:" + "a" * 64),
        ("host_hash", "a" * 64),
        ("timeout_seconds", 10),
    ],
)
def test_exact_replay_rejects_changed_target_source_candidate_and_verifier(
    saved_failure, field, value
):
    audit, prepared, search = saved_failure
    prepared["verification"]["plan"][field] = value
    prepared["verification"]["id"] = identity(prepared["verification"]["plan"])
    with pytest.raises(ValueError, match="Exact replay"):
        prepare_replay(audit, prepared, search)


def test_exact_replay_rejects_changed_requirement_and_ordinary_plan(saved_failure):
    audit, prepared, search = saved_failure
    prepared["verification"]["requirements"][0]["id"] = "a" * 64
    with pytest.raises(ValueError):
        prepare_replay(audit, prepared, search)
    prepared["verification"] = audit["evidence"]["verification"]
    prepared["ordinary"]["plan"] = {**prepared["ordinary"]["plan"], "test_description": "different"}
    prepared["ordinary"]["id"] = identity(prepared["ordinary"]["plan"])
    with pytest.raises(ValueError):
        prepare_replay(audit, prepared, search)


@pytest.mark.parametrize(
    "change",
    ["missing", "forged", "ordinary", "status", "stage", "id", "version", "engine", "malformed"],
)
def test_invalid_or_non_generated_saved_evidence_cannot_authorize_replay(saved_failure, change):
    audit, _, _ = saved_failure
    if change == "missing":
        audit["evidence"]["result"]["counterexample"] = None
    elif change == "forged":
        audit["evidence"]["result"]["counterexample"]["expected"] = "forged"
    elif change == "ordinary":
        audit["plan_id"] = "a" * 64
    elif change == "status":
        audit["status"] = "invalid_evidence"
    elif change == "stage":
        audit["evidence"]["stage"] = "validation"
    elif change == "id":
        audit["id"] = str(uuid4())
    elif change == "version":
        audit["evidence"]["verification"]["plan"]["version"] = "independent-plan-v1"
    elif change == "engine":
        audit["evidence"]["engine_id"] = "a" * 64
    else:
        audit["evidence"]["result"]["generated_runs"] = None
    audit["evidence"]["result_hash"] = identity(audit["evidence"]["result"])
    with pytest.raises(ValueError, match="valid saved generated-v3"):
        replay_plan(audit)


async def test_trusted_replay_endpoint_rejects_conflicting_plan_and_invalid_original(
    saved_failure, monkeypatch
):
    audit, _, _ = saved_failure
    monkeypatch.setattr(settings, "guest_access", False)
    expected = replay_plan(audit)
    stored = []

    async def saved(_):
        return audit

    async def material(*_):
        return tuple(audit["evidence"][k] for k in ("snapshot", "candidate", "plan"))

    async def load(*_):
        return audit["evidence"]["verification"]["requirements"][0]

    async def store(_, value):
        stored.append(value)

    monkeypatch.setattr(routes, "saved", saved)
    monkeypatch.setattr(routes, "material", material)
    monkeypatch.setattr(routes, "load", load)
    monkeypatch.setattr(routes, "store", store)
    app = FastAPI()
    app.include_router(routes.router)
    path = f"/api/repository-audits/runs/{audit['id']}/generated-replay-plans"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for field, value in [
            ("module", "other.py"),
            ("export", "other"),
            ("requirement_id", "a" * 64),
            ("candidate_id", "a" * 64),
            ("ordinary_plan_id", "a" * 64),
            ("snapshot_id", "a" * 64),
        ]:
            assert (
                await client.post(path, json={"plan": {**expected, field: value}})
            ).status_code == 422
        assert (
            await client.post(
                path,
                json={
                    "plan": {
                        **expected,
                        "search": {**expected["search"], "property": "integer_sort"},
                    }
                },
            )
        ).status_code == 422
        assert not stored
        response = await client.post(path, json={"plan": expected})
        assert response.status_code == 201, response.text
        assert response.json()["replay_of"] == audit["id"]
        assert response.json()["approval"] == "not_approved"
        assert response.json()["validation"] == "awaiting_controls"
        audit["status"] = "invalid_evidence"
        assert (await client.post(path, json={"plan": expected})).status_code == 422
        monkeypatch.setattr(settings, "guest_access", True)
        assert (await client.post(path, json={"plan": expected})).status_code == 403


def test_cli_replay_validates_original_and_uses_trusted_endpoint(
    saved_failure, monkeypatch, tmp_path
):
    audit, prepared, search = saved_failure
    calls = []

    def request(_client, method, path, payload=None):
        calls.append((method, path, payload))
        if method == "GET":
            return audit
        assert path.endswith("/generated-replay-plans")
        assert payload is not None
        return {
            "id": identity(payload["plan"]),
            "plan": payload["plan"],
            "requirements": audit["evidence"]["verification"]["requirements"],
        }

    from workbench.repository_audit import cli

    monkeypatch.setattr(cli, "request", request)
    preparation = tmp_path / "base.json"
    preparation.write_text(json.dumps(prepared))
    search_file = tmp_path / "search.json"
    search_file.write_text(json.dumps(search))
    output = tmp_path / "replay.json"
    args = [
        "generated-prepare",
        "--preparation",
        str(preparation),
        "--search",
        str(search_file),
        "--approve-property",
        "--replay-audit",
        audit["id"],
        "--out",
        str(output),
    ]
    assert main(args) == 0
    assert json.loads(output.read_text())["verification"]["plan"] == replay_plan(audit)
    search_file.write_text(json.dumps({**search, "property": "integer_sort"}))
    calls.clear()
    assert main(args) == 2
    assert [c[0] for c in calls] == ["GET"]


@pytest.mark.parametrize("saved_failure", ["integer_sort"], indirect=True)
def test_integer_sort_failure_cannot_be_reinterpreted_as_sum(saved_failure):
    audit, prepared, search = saved_failure
    assert audit["evidence"]["result"]["counterexample"]["input"] == [0, 1]
    assert audit["evidence"]["result"]["counterexample"]["expected"] == [0, 1]
    with pytest.raises(ValueError, match="Exact replay search"):
        prepare_replay(audit, prepared, {**search, "property": "integer_sum"})


async def test_broker_preserves_replay_reference_and_rejects_mismatched_approval(
    saved_failure, monkeypatch, tmp_path
):
    from workbench.repository_audit import broker

    audit, _, _ = saved_failure
    e = audit["evidence"]
    body = {k: v for k, v in e.items() if k in broker.Approved.model_fields}
    body["replay_of"] = audit["id"]
    body["approval"] = {**e["approval"], "replay_audit_id": audit["id"]}
    assert broker.Approved.model_validate(body).model_dump()["replay_of"] == audit["id"]
    body["approval"]["replay_audit_id"] = str(uuid4())
    monkeypatch.setattr(broker.broker, "ROOT", tmp_path)
    monkeypatch.setattr(
        broker.independent, "evaluate", lambda *_: pytest.fail("Mismatched replay must not execute")
    )
    app = FastAPI()
    broker.install(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.post(f"/repository-audits/{uuid4()}", json=body)).status_code == 422
