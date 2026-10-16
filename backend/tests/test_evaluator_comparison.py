"""Deterministic provider fixtures only. Actual NVIDIA transcripts are separately retained."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from workbench.evaluator import behavior, producer, runner
from workbench.evaluator.catalog import candidate, digest, identity, task
from workbench.evaluator.experiment import comparison, validate_trial
from workbench.evaluator.experiment_catalog import exclusive_json
from workbench.evaluator.producer import BUDGET, Journal, Workspace, generate
from workbench.rag.provider import ProviderError

IMAGE = "sha256:" + "a" * 64


def phase(files, command, image, cancel):
    return {
        "command": command,
        "image_id": image,
        "container_id": "deterministic-fixture-" + identity(command),
        "executed_file_hashes": {p: digest(v) for p, v in files.items()},
        "policy": runner.POLICY,
        "exit_code": 0,
        "status": "finished",
        "duration_ms": 1,
        "stdout": "fixture",
        "stderr": "",
    }


class FixtureProvider:
    """No credentials, network, or live model requests."""

    def __init__(self, responses, fail=False):
        self.responses, self.fail, self.calls = iter(responses), fail, []

    async def request(self, workload, url, payload):
        self.calls.append(
            {
                "attempt": 1,
                "model": payload["model"],
                "latency_ms": 1,
                "status": 503 if self.fail else 200,
                **(
                    {}
                    if self.fail
                    else {
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
                    }
                ),
            }
        )
        if self.fail:
            raise ProviderError("fixture_failure", "Deterministic fixture")
        return {
            "model": "deterministic-fixture",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"actions": next(self.responses)})},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }


def fixture_freeze():
    config = {
        "id": "fixture",
        "model": "deterministic-fixture",
        "temperature": 0,
        "label": "Deterministic fixture",
    }
    coordinate = {
        "id": "fixture-trial",
        "task_id": "more-bucket",
        "configuration_id": "fixture",
        "trial": 1,
        "order": 0,
    }
    body = {
        "id": "fixture",
        "image_id": IMAGE,
        "configurations": {"fixture": config},
        "order": [coordinate],
        "limitations": ["Fixture"],
    }
    return {"body": body, "hash": identity(body)}, config, coordinate


async def fixture_record(tmp_path, monkeypatch, fail=False, invalid=False):
    monkeypatch.setattr(producer, "execute", phase)
    frozen, config, coordinate = fixture_freeze()
    edits = candidate("more-bucket-reference")["edits"]
    actions = (
        [[{"tool": "unknown"}]] * 12
        if invalid
        else [[{"tool": "edit", "edits": edits}, {"tool": "test"}, {"tool": "submit"}]]
    )
    provider = FixtureProvider(actions, fail=fail)
    generation = await generate(task("more-bucket"), config, coordinate, frozen, tmp_path, provider)
    record = {
        "generation": generation,
        "events": [json.loads(p.read_text()) for p in sorted(tmp_path.glob("event-*.json"))],
        "candidate": json.loads((tmp_path / "candidate.json").read_text())
        if (tmp_path / "candidate.json").exists()
        else None,
        "result": None,
    }
    validate_trial(record, frozen)
    return record, frozen


def test_source_namespace_and_trusted_paths():
    workspace = Workspace(task("more-bucket"), IMAGE)
    for path in [
        "../reference.json",
        "/app/evaluation/freeze-v3.json",
        "/etc/passwd",
        "backend/.env",
        "/var/run/docker.sock",
        "evaluation/candidates/more-bucket-reference.json",
    ]:
        with pytest.raises(ValueError, match="outside approved"):
            workspace.action({"tool": "read", "path": path, "start": 1, "end": 20})
    for path in ["tests/test_more.py", "../probe.py"]:
        with pytest.raises(ValueError, match="Unauthorized"):
            workspace.action({"tool": "edit", "edits": [{"path": path, "old": "a", "new": "b"}]})
    assert not workspace.action({"tool": "search", "query": "reference_commit"})["hits"]
    with pytest.raises(ValueError):
        workspace.action({"tool": "shell", "command": "cat /app/evaluation"})


def test_trial_claims_and_files_do_not_mix(tmp_path):
    def claim(_):
        try:
            Journal(tmp_path / "same", "same")
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim, range(2))) == [False, True]
    first, second = Journal(tmp_path / "first", "first"), Journal(tmp_path / "second", "second")
    first.append("fixture", {"value": 1})
    second.append("fixture", {"value": 2})
    assert first.head != second.head
    with pytest.raises(FileExistsError):
        exclusive_json(tmp_path / "first" / "event-0000.json", {})


async def test_identity_fair_recording_and_validated_tools(tmp_path, monkeypatch):
    record, frozen = await fixture_record(tmp_path, monkeypatch)
    assert record["generation"]["requests"] == 1
    assert record["candidate"]["kind"] == "agent"
    assert comparison([record], frozen)["groups"][0]["awaiting_evaluation"] == 1
    for mutate in [
        lambda r: r["generation"].update(configuration_hash="bad"),
        lambda r: r["candidate"].update(kind="control"),
        lambda r: r["candidate"].update(candidate_hash="b" * 64),
        lambda r: r["events"][1]["payload"].update(reserved_tokens=0),
        lambda r: r["events"][3]["payload"].update(source_hashes={}),
    ]:
        altered = copy.deepcopy(record)
        mutate(altered)
        with pytest.raises((ValueError, KeyError)):
            validate_trial(altered, frozen)
    with pytest.raises(ValueError, match="Duplicate"):
        comparison([record, record], frozen)


async def test_budget_invalid_outputs_and_provider_failure_retained(tmp_path, monkeypatch):
    invalid, frozen = await fixture_record(tmp_path / "invalid", monkeypatch, invalid=True)
    failed, _ = await fixture_record(tmp_path / "failed", monkeypatch, fail=True)
    assert invalid["generation"]["requests"] <= BUDGET["requests"]
    assert invalid["generation"]["generation_status"] in (
        "request_budget_exhausted",
        "token_budget_exhausted",
    )
    assert failed["generation"]["requests"] == 1
    assert len(failed["generation"]["provider_calls"]) == 1
    summary = comparison([failed], frozen)["groups"][0]
    assert summary["attempted"] == 1 and summary["completed"] == 0
    assert summary["outcomes"]["infrastructure_or_provider_failure"] == 1
    assert summary["usage_missing_requests"] == 1 and summary["monetary_cost"] is None
    assert summary["incremental_denominator"] == 0


def test_ordinary_failure_gets_feedback_before_submission(monkeypatch):
    def failing(*args):
        return {**phase(*args), "exit_code": 1}

    monkeypatch.setattr(producer, "execute", failing)
    workspace = Workspace(task("more-bucket"), IMAGE)
    workspace.action({"tool": "edit", "edits": candidate("more-bucket-reference")["edits"]})
    workspace.action({"tool": "test"})
    with pytest.raises(ValueError, match="next turn"):
        workspace.action({"tool": "submit"})
    workspace.feedback_seen = True
    assert workspace.action({"tool": "submit"})["status"] == "submitted"


async def test_incremental_denominators_and_failure_evidence_validation(tmp_path, monkeypatch):
    from workbench.evaluator.experiment_runner import verifier_id

    record, frozen = await fixture_record(tmp_path, monkeypatch)
    c = candidate("more-bucket-reference")
    spec = task("more-bucket")
    binding = {
        "image_id": IMAGE,
        "task_id": spec["id"],
        "base_commit": spec["base_commit"],
        "spec_hash": spec["spec_hash"],
        "candidate_hash": c["candidate_hash"],
        "patch_hash": c["patch_hash"],
        "verifier_hash": verifier_id(spec["id"]),
        "policy_hash": identity(runner.POLICY),
        "executed_file_hashes": c["source_hashes"],
    }
    ordinary = phase(c["files"], spec["ordinary"], IMAGE, None)
    ordinary["outcome"] = "passed"
    sources = {p: v for p, v in c["files"].items() if not p.startswith("tests/")}
    independent = phase(
        sources, ["python", "-I", "-B", "-c", behavior.probe("more-bucket")], IMAGE, None
    )
    observations = behavior.expected("more-bucket")
    observations["rejected_membership"] = True
    independent.update(
        stdout=json.dumps(observations),
        outcome="failed",
        checks=behavior.compare("more-bucket", json.dumps(observations)),
    )
    record["result"] = {
        "binding": binding,
        "binding_hash": identity(binding),
        "candidate_hash": c["candidate_hash"],
        "status": "failed",
        "ordinary": ordinary,
        "independent": independent,
    }
    from workbench.evaluator.experiment import trial_binding

    binding = trial_binding(record, frozen)
    record["result"]["trial_binding_hash"] = identity(binding)
    record["scoring"] = {
        "trial_binding": binding,
        "trial_binding_hash": identity(binding),
        "result_hash": identity(record["result"]),
        "result": record["result"],
    }
    summary = comparison([record], frozen)["groups"][0]
    assert summary["incremental_numerator"] == summary["incremental_denominator"] == 1
    assert summary["completed"] == summary["attempted"] == 1
    record["result"]["independent"]["checks"][0]["status"] = "passed"
    record["result"]["independent"]["stdout"] = "{}"
    with pytest.raises(ValueError):
        comparison([record], frozen)


async def test_resealed_transcript_omissions_and_changed_metadata_rejected(tmp_path, monkeypatch):
    record, frozen = await fixture_record(tmp_path, monkeypatch)

    def reseal(value):
        head = "0" * 64
        for event in value["events"]:
            event["previous_hash"] = head
            event["hash"] = identity({k: v for k, v in event.items() if k != "hash"})
            head = event["hash"]
        value["generation"]["events_head"] = head
        value["candidate"]["events_head"] = head

    altered = copy.deepcopy(record)
    message = altered["events"][3]["payload"]["message"]
    body = json.loads(message["content"])
    body["tool_results"].pop()
    message["content"] = json.dumps(body)
    reseal(altered)
    with pytest.raises(ValueError, match="Tools differ"):
        validate_trial(altered, frozen)
    altered = copy.deepcopy(record)
    altered["generation"]["provider_calls"][0]["usage"]["total_tokens"] = 1
    with pytest.raises(ValueError, match="usage"):
        validate_trial(altered, frozen)
    for key in ["producer", "experiment_id", "trial_id", "spec_hash"]:
        altered = copy.deepcopy(record)
        altered["candidate"][key] = "changed"
        with pytest.raises(ValueError):
            validate_trial(altered, frozen)
    with pytest.raises(ValueError, match="entire scored"):
        comparison([record], frozen, require_complete=True)


async def test_failed_test_batch_defers_correction_to_next_decision(tmp_path, monkeypatch):
    def failing(*args):
        return {**phase(*args), "exit_code": 1}

    monkeypatch.setattr(producer, "execute", failing)
    frozen, config, coordinate = fixture_freeze()
    edits = candidate("more-bucket-reference")["edits"]
    provider = FixtureProvider(
        [
            [{"tool": "edit", "edits": edits}, {"tool": "test"}, {"tool": "submit"}],
            [{"tool": "submit"}],
        ]
    )
    result = await generate(task("more-bucket"), config, coordinate, frozen, tmp_path, provider)
    assert result["requests"] == 2 and result["generation_status"] == "submitted"
    tools = json.loads(
        json.loads((tmp_path / "event-0003.json").read_text())["payload"]["message"]["content"]
    )
    assert "next turn" in tools["tool_results"][-1]["error"]


async def test_identical_patch_scores_cannot_be_swapped_between_trials(tmp_path, monkeypatch):
    from workbench.evaluator.experiment import trial_binding
    from workbench.evaluator.experiment_catalog import build_candidate
    from workbench.evaluator.experiment_runner import verifier_id

    monkeypatch.setattr(producer, "execute", phase)
    frozen, config, first = fixture_freeze()
    second = {**first, "id": "fixture-second", "trial": 2, "order": 1}
    frozen["body"]["order"].append(second)
    frozen["hash"] = identity(frozen["body"])
    records = []
    for coordinate in [first, second]:
        folder = tmp_path / coordinate["id"]
        edits = candidate("more-bucket-reference")["edits"]
        provider = FixtureProvider(
            [[{"tool": "edit", "edits": edits}, {"tool": "test"}, {"tool": "submit"}]]
        )
        gen = await generate(task("more-bucket"), config, coordinate, frozen, folder, provider)
        c = json.loads((folder / "candidate.json").read_text())
        full = build_candidate(task("more-bucket"), c)
        sources = {p: v for p, v in full["files"].items() if not p.startswith("tests/")}
        ordinary = phase(full["files"], task("more-bucket")["ordinary"], IMAGE, None)
        independent = phase(
            sources, ["python", "-I", "-B", "-c", behavior.probe("more-bucket")], IMAGE, None
        )
        independent["stdout"] = json.dumps(behavior.expected("more-bucket"))
        independent["checks"] = behavior.compare("more-bucket", independent["stdout"])
        for name, p in [("ordinary", ordinary), ("independent", independent)]:
            p["container_id"] = coordinate["id"] + "-" + name
            p["outcome"] = "passed"
        binding = {
            "image_id": IMAGE,
            "task_id": "more-bucket",
            "base_commit": task("more-bucket")["base_commit"],
            "spec_hash": full["spec_hash"],
            "candidate_hash": full["candidate_hash"],
            "patch_hash": full["patch_hash"],
            "verifier_hash": verifier_id("more-bucket"),
            "policy_hash": identity(runner.POLICY),
            "executed_file_hashes": full["source_hashes"],
        }
        r = {
            "generation": gen,
            "candidate": c,
            "events": [json.loads(p.read_text()) for p in sorted(folder.glob("event-*.json"))],
        }
        provenance = trial_binding(r, frozen)
        result = {
            "binding": binding,
            "binding_hash": identity(binding),
            "candidate_hash": full["candidate_hash"],
            "status": "passed",
            "ordinary": ordinary,
            "independent": independent,
            "trial_binding_hash": identity(provenance),
        }
        r["result"] = result
        r["scoring"] = {
            "trial_binding": provenance,
            "trial_binding_hash": identity(provenance),
            "result_hash": identity(result),
            "result": result,
        }
        validate_trial(r, frozen)
        records.append(r)
    assert records[0]["candidate"]["candidate_hash"] == records[1]["candidate"]["candidate_hash"]
    assert comparison(records, frozen, require_complete=True)["complete"]
    records[0]["result"] = records[1]["result"]
    records[0]["scoring"] = records[1]["scoring"]
    with pytest.raises(ValueError, match="different trial"):
        comparison(records, frozen, require_complete=True)
