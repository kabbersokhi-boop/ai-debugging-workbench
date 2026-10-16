import json
import threading
from pathlib import Path

import docker
import pytest

from workbench.evaluator.catalog import TASK_IDS, candidate, identity, task
from workbench.evaluator.runner import IMAGE, LABEL, evaluate, execute, verifier_id

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_evaluator_docker_controls():
    records = []
    folder = ROOT / "artifacts/evaluator/controls"
    folder.mkdir(parents=True, exist_ok=True)
    for task_id in TASK_IDS:
        for label in ("baseline", "reference", "negative", "alternate"):
            c = candidate(task_id + "-" + label)
            result = evaluate(task(task_id), c, threading.Event())
            (folder / (c["id"] + ".json")).write_text(json.dumps(result, indent=2) + "\n")
            records.append(
                {
                    "candidate": c["id"],
                    "status": result["status"],
                    "ordinary": result["ordinary"].get("outcome"),
                    "independent": (result.get("independent") or {}).get("outcome"),
                }
            )
            assert result["status"] == (
                "passed" if label in ("reference", "alternate") else "failed"
            ), records
            assert result["ordinary"]["outcome"] == "passed", records
            assert result["ordinary"]["executed_file_hashes"] == c["source_hashes"]
    (folder / "summary.json").write_text(json.dumps(records, indent=2) + "\n")
    client = docker.from_env()
    assert not client.containers.list(all=True, filters={"label": LABEL})
    assert not client.volumes.list(filters={"label": LABEL})
    client.close()


def test_evaluator_docker_negative_processes():
    client = docker.from_env()
    image_id = client.images.get(IMAGE).id
    assert image_id
    client.close()
    folder = ROOT / "artifacts/evaluator/processes"
    folder.mkdir(parents=True, exist_ok=True)
    cases = [
        ("hang", ["python", "-c", "while True: pass"], "timeout", 1),
        (
            "fake_success",
            ["python", "-c", "print('all tests passed'); raise SystemExit(1)"],
            "finished",
            10,
        ),
        (
            "missing_dependency",
            ["python", "-c", "import absent_evaluator_dependency"],
            "finished",
            10,
        ),
        ("startup_error", ["python", "/nonexistent.py"], "finished", 10),
        (
            "isolation",
            [
                "python",
                "-I",
                "-c",
                "import os, pathlib, socket\n"
                "assert os.getuid()==1000\n"
                "assert not pathlib.Path('/var/run/docker.sock').exists()\n"
                "assert 'NVIDIA_API_KEY' not in os.environ\n"
                "p=pathlib.Path('/source/immutable.txt')\n"
                "assert p.read_text()=='original'\n"
                "try: p.write_text('changed')\n"
                "except OSError: pass\n"
                "else: raise AssertionError('source writable')\n"
                "s=socket.socket(); s.settimeout(1)\n"
                "assert s.connect_ex(('1.1.1.1',443)) != 0\n"
                "print('isolation checks passed')",
            ],
            "finished",
            10,
        ),
    ]
    for name, command, status, timeout in cases:
        result = execute(
            {"immutable.txt": "original"}, command, image_id, threading.Event(), timeout
        )
        (folder / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        assert result["status"] == status
        if name in ("fake_success", "missing_dependency", "startup_error"):
            assert result["exit_code"] != 0
        if name == "isolation":
            assert result["exit_code"] == 0, result
    event = threading.Event()
    event.set()
    result = execute({}, ["python", "-c", "while True: pass"], image_id, event)
    assert result["status"] == "cancelled"
    (folder / "cancelled.json").write_text(json.dumps(result, indent=2) + "\n")


def test_evaluator_freeze():
    freeze = ROOT / "evaluation/freeze-v1.json"
    if not freeze.exists():
        pytest.skip("Initial task validation precedes freeze")
    value = json.loads(freeze.read_text())
    assert value["hash"] == identity(value["body"])
    for task_id in TASK_IDS:
        assert value["body"]["tasks"][task_id]["spec_hash"] == task(task_id)["spec_hash"]
        assert value["body"]["tasks"][task_id]["verifier_hash"] == verifier_id(task_id)
