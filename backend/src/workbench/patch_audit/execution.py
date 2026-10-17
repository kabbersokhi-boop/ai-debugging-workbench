"""Reuse fixed container adapters and frozen scoring; add cancellation to the two M2 adapters."""

import copy
import json
import threading
from pathlib import Path

import docker

from workbench.evaluator import catalog, experiment_behavior, runner
from workbench.evaluator.experiment_runner import compare, validate_result
from workbench.evaluator.experiment_runner import verifier_id as inherited_verifier_id

TERMINAL = {"passed", "failed", "timeout", "cancelled", "infrastructure_error", "invalid_candidate"}


def verifier_id(task_id):
    parent = inherited_verifier_id(task_id)
    if task_id in catalog.TASK_IDS:
        return parent
    return catalog.identity(
        {
            "version": "patch-audit-cancellable-m2-v1",
            "inherited": parent,
            "adapter_source": catalog.digest(Path(__file__).read_bytes()),
        }
    )


def validate(spec, value, result, expected_verifier=None):
    if result.get("status") not in TERMINAL:
        raise ValueError("Unknown or missing terminal outcome")
    if result.get("status") == "cancelled" and not result.get("binding"):
        if result != {"candidate_hash": value["candidate_hash"], "status": "cancelled"}:
            raise ValueError("Invalid pre-execution cancellation evidence")
        return
    if not result.get("binding") and result.get("status") != "infrastructure_error":
        raise ValueError("Missing execution binding")
    if result.get("binding"):
        if catalog.identity(result["binding"]) != result.get("binding_hash"):
            raise ValueError("Execution binding integrity failure")
        if result["binding"].get("verifier_hash") != (expected_verifier or verifier_id(spec["id"])):
            raise ValueError("Execution verifier differs from admitted procedure")
    checked = result
    if spec["id"] not in catalog.TASK_IDS and result.get("binding"):
        # Validate the inherited commands, observations and other binding fields using the
        # unchanged checker. This projection is validation-only; retained evidence stays intact.
        checked = copy.deepcopy(result)
        checked["binding"]["verifier_hash"] = inherited_verifier_id(spec["id"])
        checked["binding_hash"] = catalog.identity(checked["binding"])
    validate_result(spec, value, checked)
    if result["status"] in ("passed", "failed"):
        if result["ordinary"]["container_id"] == result["independent"]["container_id"]:
            raise ValueError("Checks did not run in fresh separate environments")
    if result["status"] == "passed" and not result.get("independent", {}).get("checks"):
        raise ValueError("Missing independent observations")


def evaluate(spec, value, cancel: threading.Event):
    if cancel.is_set():
        return {"candidate_hash": value["candidate_hash"], "status": "cancelled"}
    if spec["id"] in catalog.TASK_IDS:
        return {**runner.evaluate(spec, value, cancel), "candidate_hash": value["candidate_hash"]}
    client = docker.from_env()
    try:
        image = client.images.get(runner.IMAGE).id
        assert image
    finally:
        client.close()
    binding = {
        "task_id": spec["id"],
        "base_commit": spec["base_commit"],
        "spec_hash": spec["spec_hash"],
        "candidate_hash": value["candidate_hash"],
        "patch_hash": value["patch_hash"],
        "verifier_hash": verifier_id(spec["id"]),
        "policy_hash": catalog.identity(runner.POLICY),
        "executed_file_hashes": value["source_hashes"],
        "image_id": image,
    }
    result = {
        "candidate_hash": value["candidate_hash"],
        "binding": binding,
        "binding_hash": catalog.identity(binding),
        "ordinary": None,
        "independent": None,
    }
    ordinary = runner.execute(value["files"], spec["ordinary"], image, cancel)
    result["ordinary"] = ordinary
    if ordinary["status"] != "finished":
        return {**result, "status": ordinary["status"]}
    if (
        ordinary["exit_code"] not in (0, 1)
        or "ModuleNotFoundError" in ordinary["stdout"] + ordinary["stderr"]
    ):
        return {
            **result,
            "status": "infrastructure_error",
            "reason": "Ordinary checks did not complete",
        }
    ordinary["outcome"] = "passed" if ordinary["exit_code"] == 0 else "failed"
    sources = {p: v for p, v in value["files"].items() if not p.startswith("tests/")}
    independent = runner.execute(
        sources, ["python", "-I", "-B", "-c", experiment_behavior.probe(spec["id"])], image, cancel
    )
    result["independent"] = independent
    if independent["status"] != "finished":
        return {**result, "status": independent["status"]}
    if independent["exit_code"] != 0:
        independent["outcome"] = "failed"
    else:
        try:
            independent["checks"] = compare(spec["id"], independent["stdout"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return {
                **result,
                "status": "invalid_candidate",
                "reason": "Malformed or missing observations",
            }
        independent["outcome"] = (
            "passed" if all(c["status"] == "passed" for c in independent["checks"]) else "failed"
        )
    return {
        **result,
        "status": "passed"
        if ordinary["outcome"] == independent["outcome"] == "passed"
        else "failed",
    }
