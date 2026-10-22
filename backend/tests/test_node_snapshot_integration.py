"""Real pinned Node 22 sandbox regressions, admitted G2 plans, controls and host interpretation."""

import copy
import json
import threading
from uuid import uuid4

import pytest
from test_independent_verification import fixture_verification
from test_node_observation_snapshot import CASES
from test_repository_audit import fixture_source, patch_for
from test_repository_audit_integration import actual_plan

from workbench.config import ROOT
from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import independent
from workbench.repository_audit.admission import admit
from workbench.repository_audit.contracts import Import
from workbench.repository_audit.verification import Requirement, VerificationPlan, record

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_real_node_snapshot_through_approved_g2_execution(case):
    execute_case(case)


def execute_case(case):
    name, program, arguments, expected, outcome = case
    source = fixture_source("node22")
    program += ";\nmodule.exports.add=(a,b)=>a+b;\n"
    candidate = admit(
        source,
        Import(
            snapshot_id=source["id"],
            patch=patch_for(source, "index.js", program),
            approved_paths=["index.js"],
            author_label="Authored observation-integrity regression: " + name,
        ),
    )
    ordinary = actual_plan(source, candidate, "node22")
    e = fixture_verification("node22", source, candidate, ordinary)
    statement = "Capture each completed call as independent JSON data before subsequent mutation"
    req = record(
        Requirement.model_validate(
            {
                "snapshot_id": source["id"],
                "statement": statement,
                "expected_behavior": "Named calls retain their declared call-time JSON values",
                "input_domain": "Authored synthetic review regression: " + name,
                "assumptions": ["Sequential calls; JSON data, not JavaScript object identity"],
                "ambiguities": [],
                "approval": "owner_approved",
                "provenance": {
                    "origin": "external_specification",
                    "reference": "G2 observation-integrity review",
                    "excerpt": statement,
                    "excerpt_hash": digest(statement),
                    "justification": "Owner review supplied the independent observation contract",
                    "independent_of_candidate": True,
                },
            }
        )
    )
    plan = VerificationPlan.model_validate(
        {
            **e["verification"]["plan"],
            "export": "",
            "assertions": [
                {"id": f"call{i}", "requirement_id": req["id"], "args": args, "expected": want}
                for i, (args, want) in enumerate(zip(arguments, expected, strict=True))
            ],
        }
    )
    e["verification"] = {
        "id": identity(plan.model_dump()),
        "plan": plan.model_dump(),
        "requirements": [req],
    }
    e["approval"]["verification_id"] = e["verification"]["id"]
    control_id = uuid4()
    controls = independent.evaluate(control_id, e, threading.Event())
    independent.validate(controls, control_id, e)
    assert controls["status"] == "validation_passed", controls
    validation_evidence = copy.deepcopy(e)
    e["stage"] = e["approval"]["stage"] = "execution"
    e["validation"] = {"audit_id": str(control_id), "result": controls}
    audit_id = uuid4()
    result = independent.evaluate(audit_id, e, threading.Event())
    independent.validate(result, audit_id, e)
    assert result["ordinary"]["status"] == "tests_passed", result
    assert result["independent"]["status"] == outcome, result
    if name != "unsupported":
        observations = [c["observed"] for c in result["independent"]["checks"]]
        assert observations == (
            expected if name != "hidden_early_failure" else [{"value": 0}, {"value": 1}]
        )
    else:
        checks = result["independent"]["checks"]
        assert all(c["status"] == "check_execution_failed" for c in checks[:-1])
        assert checks[-1]["observed"] == 7
    children = [c["execution"] for c in controls["controls"]]
    children += [result["ordinary"], result["independent"]["execution"]]
    assert len({c["container_id"] for c in children}) == 4
    assert all(r["confirmed_absent"] for c in children for r in c["cleanup"])
    folder = ROOT / "artifacts/repository-audit-g2/observation-fix"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}-{audit_id}.json").write_text(
        json.dumps(
            {
                "audit_id": str(audit_id),
                "evidence": e,
                "result": result,
                "validation_audit_id": str(control_id),
                "validation_evidence": validation_evidence,
                "validation_result": controls,
            },
            indent=2,
        )
    )


def test_real_node_unsupported_and_serialization_errors_never_pass():
    program = """const bad=[()=>undefined,()=>NaN,()=>1n,()=>new Date(0),
()=>{const a={};a.self=a;return a},()=>({get value(){throw Error('read')}}),
()=>({toJSON(){return undefined}}),()=>Array(2),()=>Array(257).fill(0),
()=> '\\u0000'.repeat(3000)];module.exports=i=>i===bad.length?7:bad[i]();"""
    execute_case(
        (
            "unsupported",
            program,
            [[i] for i in range(11)],
            [None] * 10 + [7],
            "check_execution_failed",
        )
    )
