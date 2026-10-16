"""Real Docker boundary and task controls; no model credentials are needed."""

import json
import threading

import docker
import pytest

from workbench.evaluator.catalog import digest
from workbench.evaluator.experiment_catalog import ROOT, candidate, task
from workbench.evaluator.experiment_runner import evaluate, validate_result
from workbench.evaluator.runner import IMAGE, execute

pytestmark = pytest.mark.integration


def test_producer_docker_access_boundary():
    client = docker.from_env()
    image = client.images.get(IMAGE).id
    client.close()
    assert image
    code = """
import os, pathlib, socket
root = pathlib.Path('/source')
assert sorted(p.name for p in root.iterdir()) == ['approved.txt']
for name in ['/app/evaluation', '/home/libertarian/ai-debugging-workbench',
             '/var/run/docker.sock', '/app/backend/.env', '/evaluation', '/source/.git']:
    assert not pathlib.Path(name).exists(), name
assert not any(k in os.environ for k in ['NVIDIA_API_KEY', 'OPENAI_API_KEY',
    'ANTHROPIC_API_KEY', 'GITHUB_TOKEN', 'DATABASE_URL'])
assert os.getuid() == 1000
s = socket.socket(); s.settimeout(1)
assert s.connect_ex(('1.1.1.1',443)) != 0
print('approved source only; no evaluator, references, history, credentials, socket or network')
"""
    result = execute(
        {"approved.txt": "development only"}, ["python", "-I", "-c", code], image, threading.Event()
    )
    from workbench.config import ROOT as PROJECT

    folder = PROJECT / "artifacts/evaluator-m02"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "producer-isolation.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["exit_code"] == 0, result
    assert result["executed_file_hashes"] == {"approved.txt": digest("development only")}


def test_comparison_new_task_controls():
    for task_id in ["more-seekable", "boltons-indexedset"]:
        for label in ["baseline", "reference", "negative", "alternate"]:
            value = candidate(task_id + "-" + label)
            result = evaluate(task(task_id), value)
            validate_result(task(task_id), value, result)
            assert result["status"] == (
                "passed" if label in ("reference", "alternate") else "failed"
            )
            assert result["ordinary"]["outcome"] == "passed"
            assert result["independent"]["outcome"] == (
                "passed" if label in ("reference", "alternate") else "failed"
            )


def test_frozen_comparison_and_actual_evidence_are_valid():
    from workbench.evaluator.experiment import assert_frozen, comparison, read_trial
    from workbench.evaluator.experiment_catalog import freeze

    if not (ROOT / "freeze.json").exists():
        pytest.skip("Pre-generation task validation")
    frozen = freeze()
    assert_frozen(frozen)
    records = [read_trial(c["id"]) for c in frozen["body"]["order"]]
    if any(r is None for r in records):
        pytest.skip("Frozen campaign not yet executed")
    result = comparison(records, frozen)
    assert result["attempted"] == result["scheduled"] == 24
    assert len(result["groups"]) == 2
    assert not result["controls_in_denominator"]
    for group in result["groups"]:
        assert sum(group["outcomes"].values()) == group["attempted"] == 12
    # Every retained trial is actual provider evidence, not the deterministic test fixtures.
    for record in records:
        assert record
        assert all(
            e["payload"].get("model") != "deterministic-fixture"
            for e in record["events"]
            if e["kind"] == "response"
        )
        assert json.loads(json.dumps(record)) == record
