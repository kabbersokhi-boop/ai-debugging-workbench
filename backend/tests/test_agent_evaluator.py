import copy
import json

import pytest

from workbench.evaluator import behavior
from workbench.evaluator.catalog import TASK_IDS, apply, candidate, identity, task
from workbench.evaluator.runner import POLICY, verifier_id
from workbench.evaluator.service import validate_binding


def test_frozen_sources_and_control_hashes():
    for task_id in TASK_IDS:
        spec = task(task_id)
        for label in ("baseline", "reference", "negative", "alternate"):
            value = candidate(task_id + "-" + label)
            assert value["spec_hash"] == spec["spec_hash"]
            assert value["kind"] == "control"
            assert len(value["candidate_hash"]) == 64


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_more.py",
        "../verifier.py",
        "/etc/passwd",
        "manifest.json",
        "more_itertools/recipes.py",
    ],
)
def test_no_trusted_path_changes(path):
    with pytest.raises(ValueError, match="Unauthorized"):
        apply(task("more-bucket"), [{"path": path, "old": "anything", "new": "passed"}])


def test_nonapplying_patch():
    with pytest.raises(ValueError, match="does not apply"):
        apply(
            task("more-bucket"),
            [{"path": "more_itertools/more.py", "old": "this source is not present", "new": ""}],
        )


def test_success_claims_and_missing_observations_are_not_passes():
    for value in ("all tests passed", "{}", "[]", '{"passed": true}'):
        with pytest.raises((ValueError, TypeError)):
            behavior.compare("more-bucket", value)
    observed = behavior.expected("more-bucket")
    observed["rejected_membership"] = 0  # JSON boolean and numeric zero differ.
    checks = behavior.compare("more-bucket", json.dumps(observed))
    assert any(c["status"] == "failed" for c in checks)


def test_result_binding_rejects_other_candidates_and_missing_pass_evidence():
    spec = task("more-bucket")
    c = candidate("more-bucket-reference")
    evidence = {"task": spec, "candidate": c}
    binding = {
        "image_id": "sha256:" + "b" * 64,
        "task_id": spec["id"],
        "spec_hash": spec["spec_hash"],
        "base_commit": spec["base_commit"],
        "candidate_hash": c["candidate_hash"],
        "patch_hash": c["patch_hash"],
        "executed_file_hashes": c["source_hashes"],
        "verifier_hash": verifier_id(spec["id"]),
        "policy_hash": identity(POLICY),
    }
    result = {
        "status": "passed",
        "candidate_hash": c["candidate_hash"],
        "binding": binding,
        "binding_hash": identity(binding),
        "ordinary": {
            "outcome": "passed",
            "exit_code": 0,
            "status": "finished",
            "image_id": binding["image_id"],
            "container_id": "ordinary-container",
            "executed_file_hashes": c["source_hashes"],
        },
        "independent": {
            "image_id": binding["image_id"],
            "container_id": "behavior-container",
            "executed_file_hashes": {
                k: v for k, v in c["source_hashes"].items() if not k.startswith("tests/")
            },
            "checks": behavior.compare("more-bucket", json.dumps(behavior.expected("more-bucket"))),
            "stdout": json.dumps(behavior.expected("more-bucket")),
            "exit_code": 0,
            "status": "finished",
        },
    }
    validate_binding(evidence, result, c["candidate_hash"])
    wrong = copy.deepcopy(result)
    wrong["binding"]["candidate_hash"] = "a" * 64
    wrong["binding_hash"] = identity(wrong["binding"])
    with pytest.raises(ValueError):
        validate_binding(evidence, wrong, c["candidate_hash"])
    wrong = {**result, "independent": None}
    with pytest.raises(ValueError):
        validate_binding(evidence, wrong, c["candidate_hash"])

    wrong = copy.deepcopy(result)
    wrong["binding"].pop("image_id")
    wrong["binding_hash"] = identity(wrong["binding"])
    with pytest.raises(ValueError, match="environment identity"):
        validate_binding(evidence, wrong, c["candidate_hash"])
    wrong = copy.deepcopy(result)
    wrong["independent"]["image_id"] = "sha256:" + "c" * 64
    with pytest.raises(ValueError, match="different environment"):
        validate_binding(evidence, wrong, c["candidate_hash"])
    wrong = copy.deepcopy(result)
    wrong["independent"].pop("executed_file_hashes")
    with pytest.raises(ValueError, match="Missing executed source"):
        validate_binding(evidence, wrong, c["candidate_hash"])
