"""Exact replay preparation, separate from frozen generated-v3 execution semantics."""

from uuid import UUID

from workbench.evaluator.catalog import identity
from workbench.repository_audit import execution, generated
from workbench.repository_audit.contracts import Contract
from workbench.repository_audit.generated import GeneratedPlan, Search
from workbench.repository_audit.service import validate_saved


class ReplayRequest(Contract):
    plan: GeneratedPlan


def original_plan(audit):
    """Accept only semantically validated, completed generated-v3 failure evidence."""
    try:
        evidence = audit["evidence"]
        validate_saved(evidence, UUID(audit["id"]))
        result = evidence["result"]
        plan = GeneratedPlan.model_validate(evidence["verification"]["plan"])
        if (
            audit["status"] != "assertions_failed"
            or result["status"] != audit["status"]
            or evidence["stage"] != "execution"
            or result["version"] != "repository-generated-result-v1"
            or not result["counterexample"]
            or audit["candidate_id"] != evidence["candidate"]["id"]
            or audit["plan_id"] != identity(evidence["plan"])
            or evidence["engine_id"] != generated.engine_id()
            or evidence["ordinary_engine_id"] != execution.engine_id()
        ):
            raise ValueError("Not a validated generated-v3 counterexample")
        return plan
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError(
            "Exact replay requires valid saved generated-v3 counterexample evidence"
        ) from error


def replay_plan(audit):
    plan = original_plan(audit).model_dump()
    plan["search"] = {
        **plan["search"],
        "replay_inputs": [audit["evidence"]["result"]["counterexample"]["input"]],
        "reduction_rounds": 0,
    }
    return GeneratedPlan.model_validate(plan).model_dump()


def prepare_replay(audit, preparation, search):
    """Reject conflicting CLI input; derive every executable field from original evidence."""
    expected = replay_plan(audit)
    original = audit["evidence"]
    ordinary = preparation["ordinary"]
    verification = preparation["verification"]
    selected = verification["plan"]
    if (
        ordinary["id"] != identity(original["plan"])
        or identity(ordinary["plan"]) != ordinary["id"]
        or verification["id"] != identity(selected)
        or identity(verification["requirements"])
        != identity(original["verification"]["requirements"])
        or any(
            identity(selected.get(key)) != identity(expected[key])
            for key in (
                "snapshot_id",
                "candidate_id",
                "candidate_hash",
                "ordinary_plan_id",
                "runtime",
                "image_id",
                "module",
                "export",
                "setup",
            )
        )
    ):
        raise ValueError(
            "Exact replay preparation conflicts with the original source, target or requirement"
        )
    supplied = Search.model_validate(search).model_dump()
    old_search = original["verification"]["plan"]["search"]
    if (
        supplied["reduction_rounds"] not in (old_search["reduction_rounds"], 0)
        or identity(supplied["replay_inputs"])
        not in (
            identity(old_search["replay_inputs"]),
            identity(expected["search"]["replay_inputs"]),
        )
        or identity(
            {
                **supplied,
                "reduction_rounds": 0,
                "replay_inputs": expected["search"]["replay_inputs"],
            }
        )
        != identity(expected["search"])
    ):
        raise ValueError(
            "Exact replay search conflicts with the original property, domain or budget"
        )
    if selected.get("version") == "generated-plan-v1":
        # A generated preparation also supplies verifier/settings identity, not just a target.
        if identity({**selected, "search": expected["search"]}) != identity(expected):
            raise ValueError("Exact replay verifier configuration differs from the original")
    return expected
