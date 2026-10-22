"""G2 lifecycle: validate controls, then ordinary and independent runs in fresh sandboxes."""

from datetime import UTC, datetime
from pathlib import Path

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import execution
from workbench.repository_audit.verification import (
    admit_plan,
    execution_plan,
    interpret,
    material,
    verifier_hashes,
)


def engine_id():
    return identity(
        {
            "ordinary_engine": execution.engine_id(),
            "adapters": verifier_hashes(),
            "sources": {
                name: digest(Path(__file__).with_name(name).read_bytes())
                for name in ("verification.py", "independent.py", "verifiers.py")
            },
        }
    )


def check(evidence, *, historical=False):
    plan = admit_plan(
        evidence["snapshot"],
        evidence["candidate"],
        evidence["plan"],
        evidence["verification"]["plan"],
        evidence["verification"]["requirements"],
        for_execution=not historical,
    )
    if evidence["verification"]["id"] != identity(evidence["verification"]["plan"]):
        raise ValueError("Independent plan identity mismatch")
    if evidence["stage"] not in ("validation", "execution"):
        raise ValueError("Unsupported independent stage")
    approval = evidence["approval"]
    if (
        approval.get("verification_id") != evidence["verification"]["id"]
        or approval.get("approve_independent_plan") is not True
        or approval.get("stage") != evidence["stage"]
    ):
        raise ValueError("Missing independent plan/stage approval")
    if evidence["stage"] == "execution":
        validation = evidence["validation"]
        # Replay structural and semantic evidence validation; a client cannot self-certify.
        validate(validation["result"], validation["audit_id"], {**evidence, "stage": "validation"})
        if validation["result"]["status"] != "validation_passed":
            raise ValueError("Independent verifier has not passed its controls")
    return plan


def evaluate(audit_id, evidence, cancel):
    plan = check(evidence)
    result = {
        "version": "repository-independent-result-v1",
        "audit_id": str(audit_id),
        "snapshot_id": evidence["snapshot"]["id"],
        "candidate_id": evidence["candidate"]["id"],
        "candidate_hash": evidence["candidate"]["candidate_hash"],
        "plan_id": identity(evidence["plan"]),
        "verification_id": evidence["verification"]["id"],
        "stage": evidence["stage"],
        "engine_id": engine_id(),
        "started_at": datetime.now(UTC).isoformat(),
        "ordinary": None,
        "independent": {"status": "not_run", "checks": []},
        "controls": [],
    }
    snapshot, candidate = evidence["snapshot"], evidence["candidate"]
    probe_plan = execution_plan(snapshot, candidate, plan)
    if evidence["stage"] == "validation":
        for control in ("positive", "negative"):
            run = execution.evaluate(
                audit_id, snapshot, candidate, probe_plan, cancel, material(plan, control)
            )
            observations = interpret(plan, run)
            result["controls"].append({"kind": control, "execution": run, **observations})
            if cancel.is_set() or run["status"] not in ("tests_passed", "tests_failed"):
                break
        result["status"] = validation_status(result["controls"])
    else:
        ordinary = execution.evaluate(audit_id, snapshot, candidate, evidence["plan"], cancel)
        result["ordinary"] = ordinary
        if ordinary["status"] not in ("tests_passed", "tests_failed"):
            result["status"] = ordinary["status"]
        else:
            run = execution.evaluate(
                audit_id, snapshot, candidate, probe_plan, cancel, material(plan)
            )
            result["independent"] = {**interpret(plan, run), "execution": run}
            result["status"] = execution_status(ordinary, result["independent"])
    result["ended_at"] = datetime.now(UTC).isoformat()
    return result


def execution_status(ordinary, independent):
    if independent["status"] != "checks_passed":
        return independent["status"]
    return "completed" if ordinary["status"] == "tests_passed" else "ordinary_failed"


def validation_status(controls):
    if (
        len(controls) == 2
        and controls[0]["kind"] == "positive"
        and controls[0]["status"] == "checks_passed"
        and controls[1]["kind"] == "negative"
        and controls[1]["status"] == "assertions_failed"
        and all(c["status"] == "failed" for c in controls[1]["checks"])
    ):
        return "validation_passed"
    for c in controls:
        if c["status"] in ("timeout", "cancelled", "infrastructure_error"):
            return c["status"]
    return "validation_failed"


def validate(result, audit_id, evidence):
    # Avoid recursive approval validation here: all nested executions are independently checked.
    snapshot, candidate, ordinary = evidence["snapshot"], evidence["candidate"], evidence["plan"]
    plan = admit_plan(
        snapshot,
        candidate,
        ordinary,
        evidence["verification"]["plan"],
        evidence["verification"]["requirements"],
        for_execution=False,
    )
    for key, value in {
        "version": "repository-independent-result-v1",
        "audit_id": str(audit_id),
        "snapshot_id": snapshot["id"],
        "candidate_id": candidate["id"],
        "candidate_hash": candidate["candidate_hash"],
        "plan_id": identity(ordinary),
        "verification_id": evidence["verification"]["id"],
        "stage": evidence["stage"],
        "engine_id": evidence["engine_id"],
    }.items():
        if result.get(key) != value:
            raise ValueError(f"Independent result {key} binding mismatch")
    probe_plan = execution_plan(snapshot, candidate, plan)
    executed = []

    def validate_probe(run, control=None):
        execution.validate(
            run,
            audit_id,
            snapshot,
            candidate,
            probe_plan,
            evidence["ordinary_engine_id"],
            material(plan, control),
        )
        executed.append(run)
        return interpret(plan, run)

    if evidence["stage"] == "validation":
        if result.get("ordinary") is not None or result.get("independent") != {
            "status": "not_run",
            "checks": [],
        }:
            raise ValueError("Validation cannot claim candidate behavioral correctness")
        controls = result["controls"]
        if len(controls) > 2:
            raise ValueError("Unexpected validation controls")
        for entry, kind in zip(controls, ("positive", "negative"), strict=False):
            expected = validate_probe(entry["execution"], kind)
            if entry != {"kind": kind, "execution": entry["execution"], **expected}:
                raise ValueError("Invalid validation control observations")
        expected_status = validation_status(controls)
    else:
        if result.get("controls") != []:
            raise ValueError("Execution cannot substitute controls for approved candidate checks")
        run = result["ordinary"]
        execution.validate(
            run, audit_id, snapshot, candidate, ordinary, evidence["ordinary_engine_id"]
        )
        executed.append(run)
        if run["status"] not in ("tests_passed", "tests_failed"):
            expected_status = run["status"]
            if result["independent"] != {"status": "not_run", "checks": []}:
                raise ValueError("Independent evidence after incomplete ordinary run")
        else:
            independent = result["independent"]
            expected = validate_probe(independent["execution"])
            if independent != {**expected, "execution": independent["execution"]}:
                raise ValueError("Independent scores differ from approved host assertions")
            expected_status = execution_status(run, expected)
    if (
        result.get("status") != expected_status
        or not result.get("ended_at")
        or not result.get("started_at")
    ):
        raise ValueError("Missing or inconsistent independent terminal outcome")
    ids = [r["container_id"] for r in executed if r.get("container_id")]
    if len(ids) != len(set(ids)):
        raise ValueError("Independent execution reused a container")
