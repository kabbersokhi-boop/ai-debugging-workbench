"""Real restricted capsule runtime; synthetic fixture only, no external campaign trials."""

import json
import threading
from uuid import uuid4

import docker
import pytest
from test_repository_audit import candidate_for, fixture_source

from workbench.config import ROOT
from workbench.repository_audit.contracts import RUNTIMES, Plan
from workbench.repository_audit.execution import evaluate, validate

pytestmark = pytest.mark.integration


def test_compatibility_capsule_is_immutable_offline_and_source_paths_are_literal():
    source = fixture_source("node22")
    candidate = candidate_for(source)
    client = docker.from_env()
    try:
        image = client.images.get(RUNTIMES["node22_compat"])
        assert image.id
        image_id = image.id
    finally:
        client.close()
    script = (
        "const f=require('fs'),a=require('assert');"
        "a.equal(require('array-flatten/package.json').version,'1.0.0');"
        "for(const p of ['/source/index.js',require.resolve('array-flatten')])"
        "a.throws(()=>f.writeFileSync(p,'bad'));"
        "a.equal(process.env.NODE_PATH,'/opt/test-tools/node_modules');"
        "a.equal(f.existsSync('/var/run/docker.sock'),false);"
        "a.deepEqual(require('array-flatten')([1,[2]]),[1,2]);"
    )
    plan = Plan(
        snapshot_id=source["id"],
        candidate_hash=candidate["candidate_hash"],
        runtime="node22_compat",
        image_id=image_id,
        tests=["node", "-e", script],
        test_description="Synthetic compatibility capsule restriction regression",
    ).model_dump()
    run_id = uuid4()
    result = evaluate(run_id, source, candidate, plan, threading.Event())
    validate(result, run_id, source, candidate, plan)
    output = ROOT / "artifacts/repository-audit-g3c"
    output.mkdir(parents=True, exist_ok=True)
    (output / "capsule-security-regression.json").write_text(json.dumps(result, indent=2) + "\n")
    assert result["status"] == "tests_passed", result
