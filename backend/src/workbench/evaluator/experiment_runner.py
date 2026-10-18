"""M2 adds approved task adapters using the unchanged M1 container execution policy."""

import json
import re
import threading
from pathlib import Path
from typing import Any

import docker

from workbench.evaluator import behavior, catalog, experiment_behavior, runner


def verifier_id(task_id: str) -> str:
    if task_id in catalog.TASK_IDS:
        return runner.verifier_id(task_id)
    folder = Path(__file__).parent
    return catalog.identity(
        {
            "version": "m02-v1",
            "parent_engine": runner.verifier_id("more-bucket"),
            "sources": {
                n: catalog.digest((folder / n).read_bytes())
                for n in ("experiment_runner.py", "experiment_behavior.py", "experiment_catalog.py")
            },
            "probe": experiment_behavior.probe(task_id),
            "expected": experiment_behavior.expected(task_id),
        }
    )


def compare(task_id: str, output: str):
    return (behavior if task_id in catalog.TASK_IDS else experiment_behavior).compare(
        task_id, output
    )


def evaluate(spec: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if spec["id"] in catalog.TASK_IDS:
        result = runner.evaluate(spec, candidate, threading.Event())
        return {**result, "candidate_hash": candidate["candidate_hash"]}
    client = docker.from_env()
    try:
        image_id = client.images.get(runner.IMAGE).id
        assert image_id
    finally:
        client.close()
    binding = {
        "task_id": spec["id"],
        "base_commit": spec["base_commit"],
        "spec_hash": spec["spec_hash"],
        "candidate_hash": candidate["candidate_hash"],
        "patch_hash": candidate["patch_hash"],
        "verifier_hash": verifier_id(spec["id"]),
        "image_id": image_id,
        "policy_hash": catalog.identity(runner.POLICY),
        "executed_file_hashes": candidate["source_hashes"],
    }
    result: dict[str, Any] = {
        "candidate_hash": candidate["candidate_hash"],
        "binding": binding,
        "binding_hash": catalog.identity(binding),
        "ordinary": None,
        "independent": None,
    }
    ordinary = runner.execute(candidate["files"], spec["ordinary"], image_id, threading.Event())
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
    sources = {p: v for p, v in candidate["files"].items() if not p.startswith("tests/")}
    independent = runner.execute(
        sources,
        ["python", "-I", "-B", "-c", experiment_behavior.probe(spec["id"])],
        image_id,
        threading.Event(),
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
            return {**result, "status": "invalid_candidate", "reason": "Malformed observations"}
        independent["outcome"] = (
            "passed" if all(c["status"] == "passed" for c in independent["checks"]) else "failed"
        )
    result["status"] = (
        "passed" if ordinary["outcome"] == independent["outcome"] == "passed" else "failed"
    )
    result["reason"] = "Frozen behavioral observations compared outside the candidate container"
    return result


def validate_result(spec, candidate, result, expected_image=None):
    """Validate failures as well as passes before any aggregation; never trust a scorecard."""
    if result.get("candidate_hash") != candidate["candidate_hash"]:
        raise ValueError("Result candidate mismatch")
    if result.get("status") == "infrastructure_error" and not result.get("binding"):
        return
    binding = result["binding"]
    wanted = {
        "task_id": spec["id"],
        "base_commit": spec["base_commit"],
        "spec_hash": spec["spec_hash"],
        "candidate_hash": candidate["candidate_hash"],
        "patch_hash": candidate["patch_hash"],
        "verifier_hash": verifier_id(spec["id"]),
        "policy_hash": catalog.identity(runner.POLICY),
        "executed_file_hashes": candidate["source_hashes"],
    }
    if catalog.identity(binding) != result["binding_hash"] or any(
        binding.get(k) != v for k, v in wanted.items()
    ):
        raise ValueError("Evaluation binding mismatch")
    image_id = binding.get("image_id", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) or (
        expected_image and image_id != expected_image
    ):
        raise ValueError("Execution image mismatch")
    for name in ("ordinary", "independent"):
        phase = result.get(name)
        if not phase:
            continue
        hashes = candidate["source_hashes"]
        if name == "independent":
            hashes = {k: v for k, v in hashes.items() if not k.startswith("tests/")}
        command = (
            spec["ordinary"]
            if name == "ordinary"
            else [
                "python",
                "-I",
                "-B",
                "-c",
                (behavior if spec["id"] in catalog.TASK_IDS else experiment_behavior).probe(
                    spec["id"]
                ),
            ]
        )
        if (
            phase.get("command") != command
            or phase.get("image_id") != image_id
            or phase.get("executed_file_hashes") != hashes
            or not phase.get("container_id")
            or phase.get("policy") != runner.POLICY
        ):
            raise ValueError("Phase environment/source identity mismatch")
    if result["status"] in ("passed", "failed", "invalid_candidate"):
        ordinary = result["ordinary"]
        if ordinary.get("status") != "finished" or ordinary.get("exit_code") not in (0, 1):
            raise ValueError("Ordinary evidence incomplete")
        if ordinary.get("outcome") != ("passed" if ordinary["exit_code"] == 0 else "failed"):
            raise ValueError("Ordinary outcome differs from exit code")
        independent = result["independent"]
        if independent.get("status") != "finished":
            raise ValueError("Independent evidence incomplete")
        if independent["exit_code"] == 0:
            try:
                checks = compare(spec["id"], independent["stdout"])
            except (ValueError, TypeError, KeyError):
                if result["status"] != "invalid_candidate":
                    raise ValueError("Invalid observations mislabeled") from None
                return
            if checks != independent.get("checks"):
                raise ValueError("Stored observations differ from recomputed evidence")
            outcome = "passed" if all(c["status"] == "passed" for c in checks) else "failed"
        else:
            outcome = "failed"
        if independent.get("outcome") != outcome:
            raise ValueError("Independent outcome mismatch")
        status = "passed" if ordinary["outcome"] == outcome == "passed" else "failed"
        if result["status"] != status:
            raise ValueError("Overall outcome mismatch")
