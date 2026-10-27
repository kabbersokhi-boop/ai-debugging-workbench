"""Independent-plan v1: finite JSON calls, explicit requirements, trusted host comparison."""

import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, JsonValue, field_validator, model_validator

from workbench.evaluator.catalog import digest, identity
from workbench.repository_audit.admission import check_plan
from workbench.repository_audit.contracts import HASH, POLICY, Contract, Plan, path
from workbench.repository_audit.verifiers import (
    CURRENT_VERIFIER,
    LEGACY_VERIFIER,
    verifier_hashes,
    verifier_sources,
)

ROOT = Path(__file__).parent
INTERPRETATION = "all-named-canonical-json-equalities-v1"
Note = Annotated[str, Field(min_length=1, max_length=500)]


def bounded_json(value):
    def visit(v, depth=0):
        if depth > 8:
            raise ValueError("JSON nesting exceeds eight levels")
        if isinstance(v, (dict, list)):
            if len(v) > 256:
                raise ValueError("JSON collection exceeds 256 items")
            for item in v.values() if isinstance(v, dict) else v:
                visit(item, depth + 1)

    visit(value)
    if len(json.dumps(value, allow_nan=False).encode()) > 16384:
        raise ValueError("JSON value exceeds 16 KiB")
    return value


class Provenance(Contract):
    origin: Literal[
        "upstream_documentation",
        "public_api_contract",
        "external_specification",
        "owner_authored_property",
        "model_proposed_hypothesis",
    ]
    reference: str = Field(min_length=1, max_length=1000)
    excerpt: str = Field(min_length=1, max_length=6000)
    excerpt_hash: HASH
    justification: str = Field(min_length=1, max_length=2000)
    independent_of_candidate: Literal[True]

    @field_validator("reference", "excerpt", "justification")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Requirement provenance cannot be blank")
        return value

    @model_validator(mode="after")
    def content_hash(self):
        if digest(self.excerpt) != self.excerpt_hash:
            raise ValueError("Requirement source excerpt hash mismatch")
        return self


class Requirement(Contract):
    version: Literal["behavioral-requirement-v1"] = "behavioral-requirement-v1"
    snapshot_id: HASH
    statement: str = Field(min_length=1, max_length=2000)
    expected_behavior: str = Field(min_length=1, max_length=2000)
    input_domain: str = Field(min_length=1, max_length=2000)
    assumptions: list[Note] = Field(max_length=16)
    ambiguities: list[Note] = Field(max_length=16)
    provenance: Provenance
    approval: Literal["unapproved", "owner_approved"] = "unapproved"

    @field_validator("statement", "expected_behavior", "input_domain")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Requirement descriptions cannot be blank")
        return value


class Assertion(Contract):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    requirement_id: HASH
    args: list[JsonValue] = Field(max_length=32)
    kwargs: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)
    expected: JsonValue

    @field_validator("args", "kwargs", "expected")
    @classmethod
    def bounded(cls, value):
        return bounded_json(value)


class VerificationPlan(Contract):
    version: Literal["independent-plan-v1"] = "independent-plan-v1"
    verifier_version: Literal["json-observer-v1", "json-observer-v2"] = CURRENT_VERIFIER
    snapshot_id: HASH
    candidate_id: HASH
    candidate_hash: HASH
    ordinary_plan_id: HASH
    runtime: Literal["python312", "node22", "node22_compat"]
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    module: str = Field(max_length=240)
    export: str = Field(max_length=200)
    assertions: list[Assertion] = Field(min_length=1, max_length=32)
    setup: list[list[str]] = Field(default_factory=list, max_length=3)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    policy_hash: HASH = identity(POLICY)
    adapter_hashes: dict[str, str] = Field(default_factory=lambda: verifier_hashes())
    adapter_sources: dict[str, str] = Field(default_factory=lambda: verifier_sources())
    interpretation: Literal["all-named-canonical-json-equalities-v1"] = INTERPRETATION

    @field_validator("module")
    @classmethod
    def module_path(cls, value):
        return path(value)

    @field_validator("export")
    @classmethod
    def public_export(cls, value):
        if value and (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*", value)):
            raise ValueError("Only public dotted exports are supported")
        return value


def record(value):
    body = value.model_dump()
    return {"id": identity(body), **body}


def requirement(value):
    obj = Requirement.model_validate({k: v for k, v in value.items() if k != "id"})
    if record(obj) != value:
        raise ValueError("Requirement identity mismatch")
    if obj.approval != "owner_approved" or obj.ambiguities:
        raise ValueError("Requirement is unapproved or ambiguous")
    if obj.provenance.origin == "model_proposed_hypothesis":
        raise ValueError("Model hypotheses need a separately supported, approved requirement")
    return obj


def admit_plan(snapshot, candidate, ordinary, value, requirements, *, for_execution=True):
    version = value.get("verifier_version", LEGACY_VERIFIER)
    if for_execution and version != CURRENT_VERIFIER:
        raise ValueError(
            "Historical observation verifier is read-only; prepare the current plan, "
            "run fresh controls, and explicitly approve new execution"
        )
    normalized = {**value, "verifier_version": version}
    if version == LEGACY_VERIFIER and not for_execution:
        # Early G2 records stored trusted adapter hashes before embedding sources. Reconstruct
        # only the pinned shipped archive; never execute or accept arbitrary supplied code.
        normalized.setdefault("adapter_sources", verifier_sources(LEGACY_VERIFIER))
    plan = VerificationPlan.model_validate(normalized)
    check_plan(snapshot, candidate, ordinary)
    if (
        plan.snapshot_id != snapshot["id"]
        or plan.candidate_id != candidate["id"]
        or plan.candidate_hash != candidate["candidate_hash"]
        or plan.ordinary_plan_id != identity(ordinary)
        or plan.policy_hash != identity(POLICY)
    ):
        raise ValueError("Independent source/candidate/ordinary-plan/policy binding mismatch")
    if plan.adapter_hashes != verifier_hashes(version) or plan.adapter_sources != verifier_sources(
        version
    ):
        raise ValueError("Unsupported or tampered observation adapter hashes")
    if plan.module not in snapshot["files"]:
        raise ValueError("Independent target must be an existing source file")
    if plan.runtime == "python312":
        if not plan.module.endswith(".py") or not plan.export:
            raise ValueError("Python checks require a .py file and public callable")
    elif not plan.module.endswith((".js", ".cjs", ".mjs")) or any(
        a.kwargs for a in plan.assertions
    ):
        raise ValueError("Node checks require JS files and positional JSON arguments")
    used = {a.requirement_id for a in plan.assertions}
    if used != {r["id"] for r in requirements} or len(requirements) != len(used):
        raise ValueError("Missing, duplicate or unused requirements")
    for r in requirements:
        if requirement(r).snapshot_id != plan.snapshot_id:
            raise ValueError("Requirement belongs to another immutable source")
    if len({a.id for a in plan.assertions}) != len(plan.assertions):
        raise ValueError("Duplicate named assertion")
    seen = {}
    for a in plan.assertions:
        key = identity({"args": a.args, "kwargs": a.kwargs})
        if key in seen and seen[key] != identity(a.expected):
            raise ValueError("Contradictory expected results for identical inputs")
        seen[key] = identity(a.expected)
    # Reuse the ordinary typed argv validation for independent offline setup.
    execution_plan(snapshot, candidate, plan)
    return plan


def material(plan, control=None):
    python = plan.runtime == "python312"
    adapter = "probe.py" if python else "probe.cjs"
    calls = [a.model_dump(include={"id", "args", "kwargs"}) for a in plan.assertions]
    module, export = "/source/" + plan.module, plan.export
    files = {adapter: plan.adapter_sources[adapter].encode()}
    if control is not None:
        values = [
            a.expected if control == "positive" else {"negative_control": a.expected}
            for a in plan.assertions
        ]
        module, export = "/verifier/control." + ("py" if python else "cjs"), "control"
        source = (
            (
                "import json\nvalues = json.loads(" + repr(json.dumps(values)) + ")\n"
                "def control(i):\n    return values[i]\n"
            )
            if python
            else ("const values = " + json.dumps(values) + ";\nexports.control = i => values[i];\n")
        )
        files[module.rsplit("/", 1)[1]] = source.encode()
        calls = [{"id": a.id, "args": [i], "kwargs": {}} for i, a in enumerate(plan.assertions)]
    files["inputs.json"] = json.dumps({"module": module, "export": export, "calls": calls}).encode()
    return files


def execution_plan(snapshot, candidate, plan):
    return Plan(
        snapshot_id=snapshot["id"],
        candidate_hash=candidate["candidate_hash"],
        runtime=plan.runtime,
        image_id=plan.image_id,
        setup=plan.setup,
        tests=["python", "-I", "-B", "/verifier/probe.py"]
        if plan.runtime == "python312"
        else ["node", "/verifier/probe.cjs"],
        test_description="JSON observation collection; host compares approved expectations",
        timeout_seconds=plan.timeout_seconds,
    ).model_dump()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON observation key")
        value[key] = item
    return value


def interpret(plan, execution):
    if execution["status"] != "tests_passed":
        return {
            "status": {
                "tests_failed": "check_execution_failed",
                "environment_preparation_failed": "verifier_preparation_failed",
            }.get(execution["status"], execution["status"]),
            "checks": [],
        }
    output = execution["ordinary"]
    try:
        if output.get("output_truncated"):
            raise ValueError("Truncated observations")
        value = json.loads(
            output["stdout"],
            object_pairs_hook=unique_object,
            parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)),
        )
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "observations"}
            or value["version"] != "observations-v1"
        ):
            raise ValueError("Invalid observation envelope")
        observations = value["observations"]
        if not isinstance(observations, list) or len(observations) != len(plan.assertions):
            raise ValueError("Missing assertions")
        checks = []
        for a, observation in zip(plan.assertions, observations, strict=True):
            if not isinstance(observation, dict) or observation.get("id") != a.id:
                raise ValueError("Missing, duplicate or reordered assertion")
            if observation.get("kind") == "execution_error":
                if (
                    set(observation) != {"id", "kind", "error"}
                    or not isinstance(observation["error"], str)
                    or len(observation["error"]) > 200
                ):
                    raise ValueError("Malformed check error")
                checks.append(
                    {
                        "id": a.id,
                        "requirement_id": a.requirement_id,
                        "status": "check_execution_failed",
                        "error": observation["error"],
                    }
                )
                continue
            if set(observation) != {"id", "kind", "value"} or observation["kind"] != "value":
                raise ValueError("Unsupported observation")
            actual = bounded_json(observation["value"])
            checks.append(
                {
                    "id": a.id,
                    "requirement_id": a.requirement_id,
                    "input": {"args": a.args, "kwargs": a.kwargs},
                    "expected": a.expected,
                    "observed": actual,
                    "status": "passed" if identity(actual) == identity(a.expected) else "failed",
                }
            )
        status = (
            "checks_passed"
            if all(c["status"] == "passed" for c in checks)
            else (
                "check_execution_failed"
                if any(c["status"] == "check_execution_failed" for c in checks)
                else "assertions_failed"
            )
        )
        return {"status": status, "checks": checks}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {
            "status": "invalid_evidence",
            "checks": [],
            "reason": "Expected exactly one bounded JSON observation for every named assertion",
        }
