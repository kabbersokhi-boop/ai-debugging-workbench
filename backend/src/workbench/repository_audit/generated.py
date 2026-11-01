"""Generated verifier v3: approved properties, bounded search and replayable reduction.

The host generates inputs and expected values. Candidate code runs only through the
existing restricted execution broker; no reference code or expectations enter its source.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit import execution, independent
from workbench.repository_audit.admission import check_plan
from workbench.repository_audit.contracts import HASH, POLICY, Contract
from workbench.repository_audit.verification import (
    Assertion,
    VerificationPlan,
    bounded_json,
    execution_plan,
    interpret,
    material,
    requirement,
)

VERSION = "json-generated-v3"
PROBE_HASH = "6d51a94d888bf9e884480b8205b12ec97fcf2aabc748653a36453e8f395d5cae"


def sources():
    value = (Path(__file__).parent / "verifiers/v3/probe.py").read_text()
    if digest(value) != PROBE_HASH:
        raise ValueError("Generated v3 observer archive integrity failure")
    return {"probe.py": value}


class Search(Contract):
    version: Literal["bounded-json-list-v1"] = "bounded-json-list-v1"
    property: Literal["first_truthy", "integer_sum", "integer_sort"]
    atoms: list[JsonValue] = Field(min_length=1, max_length=8)
    max_length: int = Field(default=8, ge=1, le=8)
    seed: int = Field(default=1, ge=0, le=2147483647)
    cases: int = Field(default=16, ge=1, le=32)
    reduction_rounds: int = Field(default=4, ge=0, le=4)
    replay_inputs: list[list[JsonValue]] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def domain(self):
        for atom in self.atoms:
            if not (
                atom is None
                or type(atom) is bool
                or type(atom) is int
                and -32 <= atom <= 32
                or type(atom) is str
                and len(atom) <= 16
            ):
                raise ValueError("Atoms must be null, booleans, small integers or short strings")
            if self.property != "first_truthy" and type(atom) is not int:
                raise ValueError("Integer properties require integer atoms")
        if len({identity(a) for a in self.atoms}) != len(self.atoms):
            raise ValueError("Duplicate generation atoms")
        if len(self.replay_inputs) > self.cases:
            raise ValueError("Replay inputs exceed the declared case budget")
        for value in self.replay_inputs:
            if not self.supports(value):
                raise ValueError("Replay input is outside the approved domain")
        return self

    def supports(self, value):
        return (
            isinstance(value, list)
            and len(value) <= self.max_length
            and all(identity(a) in {identity(v) for v in self.atoms} for a in value)
        )


class GeneratedPlan(Contract):
    version: Literal["generated-plan-v1"] = "generated-plan-v1"
    verifier_version: Literal["json-generated-v3"] = VERSION
    snapshot_id: HASH
    candidate_id: HASH
    candidate_hash: HASH
    ordinary_plan_id: HASH
    runtime: Literal["python312"] = "python312"
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    module: str = Field(max_length=240)
    export: str = Field(max_length=200)
    requirement_id: HASH
    property_approval: Literal["owner_approved"]
    stateless_function: Literal[True]
    search: Search
    setup: list[list[str]] = Field(default_factory=list, max_length=3)
    timeout_seconds: int = Field(default=5, ge=1, le=15)
    policy_hash: HASH = identity(POLICY)
    host_hash: HASH = Field(default_factory=lambda: digest(Path(__file__).read_bytes()))
    adapter_sources: dict[str, str] = Field(default_factory=sources)
    adapter_hashes: dict[str, str] = Field(default_factory=lambda: {"probe.py": PROBE_HASH})

    _module = field_validator("module")(VerificationPlan.module_path.__func__)


def oracle(search, value):
    if not search.supports(value):
        raise ValueError("Input outside approved generation domain")
    if search.property == "first_truthy":
        return next((v for v in value if v), None)
    if search.property == "integer_sum":
        return sum(value)
    return sorted(value)


def inputs(search):
    if search.replay_inputs:
        return search.replay_inputs
    # Counter-based SHA-256 selection is deterministic across Python runtime versions.
    cases = [search.atoms[: search.max_length], []]
    for index in range(search.cases):
        selector = bytes.fromhex(identity({"seed": search.seed, "index": index}))
        size = selector[0] % (search.max_length + 1)
        cases.append([search.atoms[selector[j + 1] % len(search.atoms)] for j in range(size)])
    return cases[: search.cases]


def complexity(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return len(text.encode()), text


def proposals(search, value):
    values = [[]]
    for size in sorted({len(value), max(1, len(value) // 2), 1}, reverse=True):
        for index in range(len(value)):
            values.append(value[:index] + value[index + size :])
    for index in range(len(value)):
        for atom in sorted(search.atoms, key=complexity):
            values.append(value[:index] + [atom] + value[index + 1 :])
    unique = {
        identity(v): v for v in values if search.supports(v) and complexity(v) < complexity(value)
    }
    return sorted(unique.values(), key=complexity)[:16]


def engine_id():
    return identity(
        {
            "version": VERSION,
            "ordinary_engine": execution.engine_id(),
            "host": digest(Path(__file__).read_bytes()),
            "observer": PROBE_HASH,
        }
    )


def admit(snapshot, candidate, ordinary, value, requirements):
    plan = GeneratedPlan.model_validate(value)
    check_plan(snapshot, candidate, ordinary)
    if (
        plan.snapshot_id != snapshot["id"]
        or plan.candidate_id != candidate["id"]
        or plan.candidate_hash != candidate["candidate_hash"]
        or plan.ordinary_plan_id != identity(ordinary)
        or plan.policy_hash != identity(POLICY)
    ):
        raise ValueError("Generated plan does not bind this source, patch and ordinary plan")
    if ordinary["runtime"] != "python312" or plan.image_id != ordinary["image_id"]:
        raise ValueError("Generation requires the same approved Python runtime image")
    if plan.module not in snapshot["files"] or not plan.module.endswith(".py") or not plan.export:
        raise ValueError("Generation requires an existing Python module and public function")
    VerificationPlan.public_export(plan.export)
    if plan.host_hash != digest(Path(__file__).read_bytes()):
        raise ValueError("Generated v3 host implementation differs; prepare and approve a new plan")
    if plan.adapter_sources != sources() or plan.adapter_hashes != {"probe.py": PROBE_HASH}:
        raise ValueError("Generated observation adapter was changed")
    if len(requirements) != 1 or requirements[0]["id"] != plan.requirement_id:
        raise ValueError("Generation requires exactly one independently approved requirement")
    if requirement(requirements[0]).snapshot_id != snapshot["id"]:
        raise ValueError("Generation requirement belongs to another source")
    execution_plan(snapshot, candidate, probe_plan(plan, inputs(plan.search), "initial"))
    return plan


def probe_plan(plan, values, label):
    return VerificationPlan(
        snapshot_id=plan.snapshot_id,
        candidate_id=plan.candidate_id,
        candidate_hash=plan.candidate_hash,
        ordinary_plan_id=plan.ordinary_plan_id,
        runtime="python312",
        image_id=plan.image_id,
        module=plan.module,
        export=plan.export,
        assertions=[
            Assertion(
                id=f"{label}_{i:03d}",
                requirement_id=plan.requirement_id,
                args=[value],
                expected=bounded_json(oracle(plan.search, value)),
            )
            for i, value in enumerate(values)
        ],
        setup=plan.setup,
        timeout_seconds=plan.timeout_seconds,
        adapter_sources=plan.adapter_sources,
        adapter_hashes=plan.adapter_hashes,
    )


def check(evidence, *, historical=False):
    verification = evidence["verification"]
    plan = admit(
        evidence["snapshot"],
        evidence["candidate"],
        evidence["plan"],
        verification["plan"],
        verification["requirements"],
    )
    if verification["id"] != identity(verification["plan"]):
        raise ValueError("Generated plan identity mismatch")
    approval = evidence["approval"]
    if (
        evidence["stage"] not in {"execution", "validation"}
        or approval.get("verification_id") != verification["id"]
        or approval.get("stage") != evidence["stage"]
        or approval.get("approve_independent_plan") is not True
    ):
        raise ValueError("Missing exact generated-plan approval")
    if evidence["stage"] == "execution":
        validated = evidence["validation"]
        validate(validated["result"], validated["audit_id"], {**evidence, "stage": "validation"})
        if validated["result"]["status"] != "validation_passed":
            raise ValueError("Generated checker controls did not pass")
    return plan


def process(audit_id, evidence, plan, execute, ordinary):
    result = {
        "version": "repository-generated-result-v1",
        "audit_id": str(audit_id),
        "snapshot_id": plan.snapshot_id,
        "candidate_id": plan.candidate_id,
        "candidate_hash": plan.candidate_hash,
        "plan_id": plan.ordinary_plan_id,
        "verification_id": evidence["verification"]["id"],
        "stage": evidence["stage"],
        "engine_id": evidence["engine_id"],
        "ordinary": None,
        "controls": [],
        "independent": {"status": "not_run", "checks": []},
        "generated_runs": [],
        "counterexample": None,
        "search": plan.search.model_dump(),
        "limitations": (
            "Bounded deterministic cases and local reduction only; "
            "no globally smallest input or universal correctness claim."
        ),
    }

    def probe(values, label, control=None):
        observer = probe_plan(plan, values, label)
        probe_execution = execution_plan(evidence["snapshot"], evidence["candidate"], observer)
        files = material(observer, control)
        run = execute(label, probe_execution, files)
        result["generated_runs"].append({"label": label, "execution": run})
        return interpret(observer, run)

    values = inputs(plan.search)
    if evidence["stage"] == "validation":
        for kind in ("positive", "negative"):
            observations = probe(values, kind, kind)
            result["controls"].append({"kind": kind, **observations})
            if observations["status"] not in {"checks_passed", "assertions_failed"}:
                break
        result["status"] = independent.validation_status(
            [
                {**c, "execution": result["generated_runs"][i]["execution"]}
                for i, c in enumerate(result["controls"])
            ]
        )
        return result
    result["ordinary"] = ordinary()
    if result["ordinary"]["status"] not in {"tests_passed", "tests_failed"}:
        result["status"] = result["ordinary"]["status"]
        return result
    initial = probe(values, "initial")
    result["independent"] = initial
    result["status"] = independent.execution_status(result["ordinary"], initial)
    if initial["status"] != "assertions_failed":
        return result
    failure = next(c for c in initial["checks"] if c["status"] == "failed")
    original = failure["input"]["args"][0]
    current, current_check = original, failure
    reproduced = probe([original], "original_replay")
    if reproduced["status"] != "assertions_failed" or identity(
        reproduced["checks"][0]["observed"]
    ) != identity(failure["observed"]):
        result["status"] = (
            "non_reproducible"
            if reproduced["status"] in {"checks_passed", "assertions_failed"}
            else reproduced["status"]
        )
        return result
    current_check = reproduced["checks"][0]
    for round_index in range(plan.search.reduction_rounds):
        choices = proposals(plan.search, current)
        if not choices:
            break
        reduced = probe(choices, f"reduce{round_index}")
        if reduced["status"] not in {"checks_passed", "assertions_failed"}:
            result["status"] = reduced["status"]
            return result
        selected = next((c for c in reduced["checks"] if c["status"] == "failed"), None)
        if selected is None:
            break
        current, current_check = selected["input"]["args"][0], selected
    for repetition in range(2):
        confirmed = probe([current], f"confirm{repetition}")
        if confirmed["status"] != "assertions_failed" or identity(
            confirmed["checks"][0]["observed"]
        ) != identity(current_check["observed"]):
            result["status"] = (
                "non_reproducible"
                if confirmed["status"] in {"checks_passed", "assertions_failed"}
                else confirmed["status"]
            )
            return result
    result["counterexample"] = {
        "requirement_id": plan.requirement_id,
        "original_input": original,
        "original_expected": failure["expected"],
        "original_observed": failure["observed"],
        "input": current,
        "expected": current_check["expected"],
        "observed": current_check["observed"],
        "reduced": complexity(current) < complexity(original),
        "fresh_reproductions": 2,
        "reproduction": {
            "args": [current],
            "kwargs": {},
            "property": plan.search.property,
            "replay_inputs": [current],
            "verification_id": evidence["verification"]["id"],
        },
    }
    return result


def evaluate(audit_id, evidence, cancel):
    plan = check(evidence)
    started = datetime.now(UTC).isoformat()

    def execute(label, probe_execution, files):
        return execution.evaluate(
            audit_id, evidence["snapshot"], evidence["candidate"], probe_execution, cancel, files
        )

    def ordinary():
        return execution.evaluate(
            audit_id, evidence["snapshot"], evidence["candidate"], evidence["plan"], cancel
        )

    result = process(audit_id, evidence, plan, execute, ordinary)
    return {**result, "started_at": started, "ended_at": datetime.now(UTC).isoformat()}


def validate(result, audit_id, evidence):
    plan = admit(
        evidence["snapshot"],
        evidence["candidate"],
        evidence["plan"],
        evidence["verification"]["plan"],
        evidence["verification"]["requirements"],
    )
    runs = iter(result["generated_runs"])
    container_ids = []

    def verify(run, execution_value, files=None):
        execution.validate(
            run,
            audit_id,
            evidence["snapshot"],
            evidence["candidate"],
            execution_value,
            evidence["ordinary_engine_id"],
            files,
        )
        if run.get("container_id"):
            container_ids.append(run["container_id"])
        return run

    def execute(label, execution_value, files):
        entry = next(runs, None)
        if entry is None or set(entry) != {"label", "execution"} or entry["label"] != label:
            raise ValueError("Missing, reordered or unexpected generated observation run")
        return verify(entry["execution"], execution_value, files)

    def ordinary():
        return verify(result["ordinary"], evidence["plan"])

    expected = process(audit_id, evidence, plan, execute, ordinary)
    if (
        next(runs, None) is not None
        or len(container_ids) != len(set(container_ids))
        or identity({k: v for k, v in result.items() if k not in {"started_at", "ended_at"}})
        != identity(expected)
        or not result.get("started_at")
        or not result.get("ended_at")
    ):
        raise ValueError("Generated search, reduction or reproduction evidence does not replay")
