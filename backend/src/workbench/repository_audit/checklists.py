"""Portable project checklists; importing declarations grants no execution authority."""

from typing import Annotated, Literal, cast

from pydantic import Field, JsonValue, field_validator, model_validator

from workbench.evaluator.catalog import identity
from workbench.repository_audit.admission import check_plan
from workbench.repository_audit.contracts import (
    HASH,
    SHA,
    Command,
    Contract,
    Plan,
    path,
)
from workbench.repository_audit.contracts import (
    repository as validate_repository,
)
from workbench.repository_audit.verification import (
    Assertion,
    Provenance,
    Requirement,
    VerificationPlan,
    admit_plan,
    bounded_json,
    record,
)
from workbench.repository_audit.verifiers import CURRENT_VERIFIER, verifier_hashes, verifier_sources

Text = Annotated[str, Field(min_length=1, max_length=2000)]


class SupportedSource(Contract):
    base_commit: SHA
    file_hashes: dict[str, HASH] = Field(min_length=1, max_length=1000)

    @field_validator("file_hashes")
    @classmethod
    def paths(cls, value):
        for key in value:
            path(key)
        return value


class ChecklistRequirement(Contract):
    statement: Text
    expected_behavior: Text
    input_domain: Text
    assumptions: list[Text] = Field(max_length=16)
    ambiguities: list[Text] = Field(default_factory=list, max_length=16)
    provenance: Provenance


class ChecklistAssertion(Contract):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    requirement_index: int = Field(ge=0, le=31)
    args: list[JsonValue] = Field(max_length=32)
    kwargs: dict[str, JsonValue] = Field(default_factory=dict, max_length=32)
    expected: JsonValue

    @field_validator("args", "kwargs", "expected")
    @classmethod
    def bounded(cls, value):
        return bounded_json(value)


class Checklist(Contract):
    version: Literal["project-checklist-v1"] = "project-checklist-v1"
    name: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    repository: str
    supported_sources: list[SupportedSource] = Field(min_length=1, max_length=32)
    approved_paths: list[str] = Field(min_length=1, max_length=4)
    runtime: Literal["python312", "node22", "node22_compat"]
    verifier_version: str = Field(default=CURRENT_VERIFIER, max_length=80)
    working_directory: str = Field(default=".", max_length=240)
    setup: list[Command] = Field(default_factory=list, max_length=3)
    tests: Command
    test_description: str = Field(min_length=1, max_length=500)
    timeout_seconds: int = Field(default=45, ge=1, le=120)
    module: str
    export: str
    independent_setup: list[Command] = Field(default_factory=list, max_length=3)
    independent_timeout_seconds: int = Field(default=30, ge=1, le=120)
    requirements: list[ChecklistRequirement] = Field(min_length=1, max_length=32)
    assertions: list[ChecklistAssertion] = Field(min_length=1, max_length=32)

    _repository = field_validator("repository")(validate_repository)
    _module = field_validator("module")(path)

    @model_validator(mode="after")
    def declarations(self):
        if len({s.base_commit for s in self.supported_sources}) != len(self.supported_sources):
            raise ValueError("Duplicate supported revision")
        if len(set(self.approved_paths)) != len(self.approved_paths):
            raise ValueError("Duplicate approved path")
        for value in self.approved_paths:
            path(value)
        if {a.requirement_index for a in self.assertions} != set(range(len(self.requirements))):
            raise ValueError("Every requirement must be used by named checks")
        if len({a.id for a in self.assertions}) != len(self.assertions):
            raise ValueError("Duplicate named check")
        return self


class CompatibilityRequest(Contract):
    checklist: Checklist
    candidate_id: HASH


class PrepareRequest(CompatibilityRequest):
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    approve_requirements: Literal[True]


def compatibility(checklist: Checklist, snapshot, candidate, *, historical=False):
    reasons = []
    outdated = False
    if not historical and checklist.verifier_version != CURRENT_VERIFIER:
        outdated = True
        reasons.append("Checklist uses a retired or unsupported verifier; review a new revision")
    if checklist.repository != snapshot["repository"]:
        reasons.append("Checklist belongs to another repository")
    source = next(
        (s for s in checklist.supported_sources if s.base_commit == snapshot["base_commit"]), None
    )
    if source is None:
        outdated = True
        reasons.append("Source revision is outside the checklist's supported revisions")
    elif any(snapshot["file_hashes"].get(p) != h for p, h in source.file_hashes.items()):
        reasons.append("Required source paths or their hashes differ")
    if not set(candidate["affected_files"]) <= set(checklist.approved_paths):
        reasons.append("Patch changes files outside the declared checklist scope")
    if checklist.module not in snapshot["files"]:
        reasons.append("Declared function target is missing")
    if any(
        r.ambiguities or r.provenance.origin == "model_proposed_hypothesis"
        for r in checklist.requirements
    ):
        reasons.append("Ambiguous requirements or model hypotheses cannot authorize checks")
    return {
        "status": "outdated" if outdated else "incompatible" if reasons else "compatible",
        "reasons": reasons,
        "checklist_id": identity(checklist.model_dump()),
        "revision": checklist.revision,
        "execution_authorized": False,
    }


def compile_plans(checklist: Checklist, snapshot, candidate, image_id: str, *, historical=False):
    match = compatibility(checklist, snapshot, candidate, historical=historical)
    if match["status"] != "compatible":
        raise ValueError("; ".join(match["reasons"]))
    ordinary = Plan(
        snapshot_id=snapshot["id"],
        candidate_hash=candidate["candidate_hash"],
        runtime=checklist.runtime,
        image_id=image_id,
        working_directory=checklist.working_directory,
        setup=checklist.setup,
        tests=checklist.tests,
        test_description=checklist.test_description,
        timeout_seconds=checklist.timeout_seconds,
    ).model_dump()
    check_plan(snapshot, candidate, ordinary)
    requirements = [
        record(Requirement(snapshot_id=snapshot["id"], **r.model_dump(), approval="owner_approved"))
        for r in checklist.requirements
    ]
    independent = VerificationPlan(
        verifier_version=cast(
            Literal["json-observer-v1", "json-observer-v2"], checklist.verifier_version
        ),
        adapter_hashes=verifier_hashes(checklist.verifier_version),
        adapter_sources=verifier_sources(checklist.verifier_version),
        snapshot_id=snapshot["id"],
        candidate_id=candidate["id"],
        candidate_hash=candidate["candidate_hash"],
        ordinary_plan_id=identity(ordinary),
        runtime=checklist.runtime,
        image_id=image_id,
        module=checklist.module,
        export=checklist.export,
        setup=checklist.independent_setup,
        timeout_seconds=checklist.independent_timeout_seconds,
        assertions=[
            Assertion(
                requirement_id=requirements[a.requirement_index]["id"],
                **a.model_dump(exclude={"requirement_index"}),
            )
            for a in checklist.assertions
        ],
    ).model_dump()
    admit_plan(
        snapshot, candidate, ordinary, independent, requirements, for_execution=not historical
    )
    verification = {"id": identity(independent), "plan": independent, "requirements": requirements}
    use_body = {
        "version": "project-checklist-use-v1",
        "checklist": checklist.model_dump(),
        "checklist_id": match["checklist_id"],
        "snapshot_id": snapshot["id"],
        "candidate_id": candidate["id"],
        "plan_id": identity(ordinary),
        "verification_id": verification["id"],
    }
    return (
        {"id": identity(ordinary), "plan": ordinary},
        verification,
        {
            "id": identity(use_body),
            **use_body,
        },
    )


def validate_use(use, snapshot, candidate, plan, verification, *, historical=True):
    body = {k: v for k, v in use.items() if k != "id"}
    if identity(body) != use["id"]:
        raise ValueError("Checklist use identity mismatch")
    checklist = Checklist.model_validate(use["checklist"])
    expected_plan, expected_verification, expected_use = compile_plans(
        checklist, snapshot, candidate, plan["image_id"], historical=historical
    )
    if (
        expected_use != use
        or expected_plan["plan"] != plan
        or expected_verification != verification
    ):
        raise ValueError("Checklist is not bound to these exact source, patch and plans")
