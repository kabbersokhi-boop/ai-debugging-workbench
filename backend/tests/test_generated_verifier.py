"""Authored bounded-generator controls; no candidate code is executed by offline tests."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from test_project_checklists import declaration
from test_repository_audit import IMAGE, candidate_for, fixture_source, plan_for

from workbench.config import settings
from workbench.evaluator.catalog import digest, identity
from workbench.release import app as recorded
from workbench.repository_audit import generated, verification_dispatch
from workbench.repository_audit.generated import GeneratedPlan, Search
from workbench.repository_audit.routes import router
from workbench.repository_audit.verification import Requirement, record


def setup():
    source = fixture_source()
    candidate = candidate_for(source)
    ordinary = plan_for(source, candidate)
    template = declaration(source)["requirements"][0]
    template.update(
        statement="First truthy scalar from a finite list, or null.",
        expected_behavior="Python truthiness, with None when no element is truthy.",
        input_domain="Finite lists drawn from the explicit scalar palette",
    )
    template["provenance"].update(
        excerpt=template["statement"], excerpt_hash=digest(template["statement"])
    )
    req = record(Requirement(snapshot_id=source["id"], approval="owner_approved", **template))
    plan = GeneratedPlan(
        snapshot_id=source["id"],
        candidate_id=candidate["id"],
        candidate_hash=candidate["candidate_hash"],
        ordinary_plan_id=identity(ordinary),
        image_id=IMAGE,
        module="library.py",
        export="add",
        requirement_id=req["id"],
        property_approval="owner_approved",
        stateless_function=True,
        search=Search(property="first_truthy", atoms=[0, False, None, "ready", "a", 1, -1]),
    )
    verification = {
        "id": identity(plan.model_dump()),
        "plan": plan.model_dump(),
        "requirements": [req],
    }
    evidence = {
        "snapshot": source,
        "candidate": candidate,
        "plan": ordinary,
        "verification": verification,
        "stage": "execution",
        "engine_id": generated.engine_id(),
    }
    return plan, evidence


def run_authored(plan, evidence, *, negative=False, unstable=False, infrastructure=None):
    # Synthetic observation transport only. Real Docker controls are tested separately.
    def execute(label, command, files):
        if infrastructure and label.startswith("reduce"):
            return {"status": infrastructure}
        data = json.loads(files["inputs.json"])
        observations = []
        for i, call in enumerate(data["calls"]):
            if label in {"positive", "negative"}:
                value = generated.oracle(plan.search, generated.inputs(plan.search)[i])
                if label == "negative":
                    value = {"wrong": value}
            else:
                values = call["args"][0]
                value = (
                    next((v for v in values if v and not isinstance(v, str)), None)
                    if negative
                    else generated.oracle(plan.search, values)
                )
                if unstable and label.startswith("confirm"):
                    value = "inconsistent fresh result"
            observations.append({"id": call["id"], "kind": "value", "value": value})
        return {
            "status": "tests_passed",
            "ordinary": {
                "stdout": json.dumps({"version": "observations-v1", "observations": observations}),
                "output_truncated": False,
            },
        }

    return generated.process(
        str(uuid4()), evidence, plan, execute, lambda: {"status": "tests_passed"}
    )


def test_authored_generation_failure_reduction_and_reproduction():
    plan, evidence = setup()
    result = run_authored(plan, evidence, negative=True)
    assert result["status"] == "assertions_failed"
    case = result["counterexample"]
    assert case["original_input"] == plan.search.atoms
    assert case["input"] == ["a"] and case["expected"] == "a" and case["observed"] is None
    assert case["reduced"] and case["fresh_reproductions"] == 2
    assert len(result["generated_runs"]) <= 8
    assert result["generated_runs"][-2]["label"] == "confirm0"
    assert result["generated_runs"][-1]["label"] == "confirm1"
    assert "globally smallest" in result["limitations"]


def test_authored_positive_and_control_validation_remain_scoped():
    plan, evidence = setup()
    positive = run_authored(plan, evidence)
    assert positive["status"] == "completed" and positive["counterexample"] is None
    assert len(positive["independent"]["checks"]) == plan.search.cases
    controls = run_authored(plan, {**evidence, "stage": "validation"})
    assert controls["status"] == "validation_passed" and controls["counterexample"] is None
    assert [c["status"] for c in controls["controls"]] == ["checks_passed", "assertions_failed"]
    assert controls["ordinary"] is None


@pytest.mark.parametrize("error", ["timeout", "cancelled", "infrastructure_error"])
def test_reduction_infrastructure_never_becomes_a_verified_counterexample(error):
    plan, evidence = setup()
    result = run_authored(plan, evidence, negative=True, infrastructure=error)
    assert result["status"] == error and result["counterexample"] is None


def test_unstable_fresh_reproduction_never_claims_reproducibility():
    plan, evidence = setup()
    result = run_authored(plan, evidence, negative=True, unstable=True)
    assert result["status"] == "non_reproducible" and result["counterexample"] is None


def test_seed_generation_and_replay_are_deterministic_and_bounded():
    plan, _ = setup()
    assert generated.inputs(plan.search) == generated.inputs(
        Search.model_validate(plan.search.model_dump())
    )
    values = generated.inputs(plan.search)
    assert len(values) == 16 and all(plan.search.supports(v) for v in values)
    replay = Search.model_validate(
        {**plan.search.model_dump(), "replay_inputs": [["a"]], "reduction_rounds": 0}
    )
    assert generated.inputs(replay) == [["a"]]
    proposals = generated.proposals(plan.search, values[0])
    assert len(proposals) <= 16 and all(
        generated.complexity(v) < generated.complexity(values[0]) for v in proposals
    )
    assert generated.inputs(Search(property="integer_sum", atoms=[-1, 0, 1], cases=32))
    assert generated.oracle(Search(property="integer_sum", atoms=[1, 2]), [1, 2]) == 3
    assert generated.oracle(Search(property="integer_sort", atoms=[1, 2]), [2, 1]) == [1, 2]


@pytest.mark.parametrize(
    "override",
    [
        {"atoms": [{}]},
        {"atoms": [1.1]},
        {"atoms": [33]},
        {"atoms": ["x" * 17]},
        {"cases": 33},
        {"reduction_rounds": 5},
        {"max_length": 9},
        {"property": "arbitrary_code"},
        {"replay_inputs": [["undeclared"]]},
        {"property": "integer_sum", "atoms": [True]},
    ],
)
def test_unsupported_or_unbounded_search_is_rejected(override):
    plan, _ = setup()
    with pytest.raises(ValidationError):
        Search.model_validate({**plan.search.model_dump(), **override})


def test_exact_property_requirement_adapter_and_policy_binding():
    plan, evidence = setup()
    generated.admit(
        evidence["snapshot"],
        evidence["candidate"],
        evidence["plan"],
        plan.model_dump(),
        evidence["verification"]["requirements"],
    )
    for key, value in (
        ("candidate_hash", "a" * 64),
        ("adapter_sources", {"probe.py": "print('fake')"}),
        ("policy_hash", "f" * 64),
        ("host_hash", "f" * 64),
    ):
        altered = {**plan.model_dump(), key: value}
        with pytest.raises(ValueError):
            generated.admit(
                evidence["snapshot"],
                evidence["candidate"],
                evidence["plan"],
                altered,
                evidence["verification"]["requirements"],
            )
    value = plan.model_dump()
    del value["property_approval"]
    with pytest.raises(ValidationError):
        GeneratedPlan.model_validate(value)
    assert verification_dispatch.handler(evidence["verification"]) is generated
    assert verification_dispatch.engine_id() != generated.engine_id()
    assert (
        generated.sources()["probe.py"]
        and digest(generated.sources()["probe.py"]) == generated.PROBE_HASH
    )


async def test_generated_plan_routes_keep_local_owner_and_recorded_boundaries(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(settings, "guest_access", True)
    plan, _ = setup()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (
            await client.post("/api/repository-audits/generated-plans", json=plan.model_dump())
        ).status_code == 403
    assert not any(
        getattr(r, "path", "").startswith("/api/repository-audits") for r in recorded.routes
    )


def test_published_generated_schema_matches_the_versioned_contract():
    from workbench.config import ROOT

    assert (
        json.loads((ROOT / "schemas/generated-plan-v1.schema.json").read_text())
        == GeneratedPlan.model_json_schema()
    )
