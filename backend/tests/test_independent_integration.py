"""Stage A actual containers, no network/model inference or external repositories."""

import copy
import json
import threading
from uuid import uuid4

import pytest
from test_independent_verification import fixture_verification
from test_repository_audit import candidate_for, fixture_source, patch_for
from test_repository_audit_integration import actual_plan

from workbench.config import ROOT
from workbench.repository_audit import independent
from workbench.repository_audit.admission import admit
from workbench.repository_audit.contracts import Import

pytestmark = pytest.mark.integration
FOLDER = ROOT / "artifacts/repository-audit-g2"


def execute(evidence, name, cancel=None):
    audit_id = uuid4()
    result = independent.evaluate(audit_id, evidence, cancel or threading.Event())
    independent.validate(result, audit_id, evidence)
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / (name + "-" + str(audit_id) + ".json")).write_text(
        json.dumps({"audit_id": str(audit_id), "evidence": evidence, "result": result}, indent=2)
    )
    return str(audit_id), result


def validated(runtime="python312", candidate=None, **overrides):
    source = fixture_source(runtime)
    candidate = candidate or candidate_for(source)
    ordinary = actual_plan(source, candidate, runtime)
    e = fixture_verification(runtime, source, candidate, ordinary)
    e["verification"]["plan"].update(overrides)
    from workbench.evaluator.catalog import identity

    e["verification"]["id"] = identity(e["verification"]["plan"])
    e["approval"]["verification_id"] = e["verification"]["id"]
    aid, validation = execute(e, runtime + "-validation")
    assert validation["status"] == "validation_passed", validation
    e["stage"] = e["approval"]["stage"] = "execution"
    e["validation"] = {"audit_id": aid, "result": validation}
    return e


@pytest.mark.parametrize("runtime", ["python312", "node22"])
def test_independent_real_controls_and_separate_fresh_candidate_environments(runtime):
    e = validated(runtime)
    _, result = execute(e, runtime + "-positive")
    assert result["ordinary"]["status"] == "tests_passed", result
    assert result["independent"]["status"] == "checks_passed", result
    assert len(result["independent"]["checks"]) == 2
    normal, probe = result["ordinary"], result["independent"]["execution"]
    assert normal["container_id"] != probe["container_id"]
    assert normal["executed_source_hashes"] == probe["executed_source_hashes"]
    mounts = probe["sandbox"]["mounts"]
    assert any(m["Destination"] == "/verifier" and not m["RW"] for m in mounts)
    assert all(m["Type"] != "bind" for m in mounts)
    # Every resource is checked, including the extra verifier volume.
    assert all(item["confirmed_absent"] for item in probe["cleanup"])
    bad = copy.deepcopy(result)
    bad["independent"]["checks"][0]["expected"] = 100
    with pytest.raises(ValueError):
        independent.validate(bad, result["audit_id"], e)


@pytest.mark.parametrize("runtime", ["python312", "node22"])
def test_authored_ordinary_pass_independent_fail_controls(runtime):
    source = fixture_source(runtime)
    file = "library.py" if runtime == "python312" else "index.js"
    # Deliberately matches the ordinary (1,2) case, violates the fixed negative-input requirement.
    replacement = (
        "def add(a, b):\n    return a + b if a >= 0 else 999\n"
        if runtime == "python312"
        else ("exports.add = (a, b) => a >= 0 ? a + b : 999;\n")
    )
    candidate = admit(
        source,
        Import(
            snapshot_id=source["id"],
            patch=patch_for(source, file, replacement),
            approved_paths=[file],
            author_label="Authored Stage A negative control",
        ),
    )
    e = validated(runtime, candidate)
    _, result = execute(e, runtime + "-negative")
    assert result["ordinary"]["status"] == "tests_passed", result
    assert result["status"] == "assertions_failed", result
    assert result["independent"]["checks"][1]["observed"] == 999


def test_actual_verifier_load_failure_and_cancellation_are_not_passes():
    e = validated()
    e["verification"]["plan"]["export"] = "missing"
    from workbench.evaluator.catalog import identity

    # A changed plan must redo validation and approval; a stale validation cannot authorize it.
    e["verification"]["id"] = identity(e["verification"]["plan"])
    e["approval"]["verification_id"] = e["verification"]["id"]
    with pytest.raises(ValueError):
        independent.check(e)
    e["stage"] = e["approval"]["stage"] = "validation"
    aid, result = execute(e, "missing-export-validation")
    assert (
        result["status"] == "validation_passed"
    )  # controls validate engine, not target availability
    e["stage"] = e["approval"]["stage"] = "execution"
    e["validation"] = {"audit_id": aid, "result": result}
    _, result = execute(e, "missing-export")
    assert result["status"] == "check_execution_failed", result
    e = validated()
    cancelled = threading.Event()
    cancelled.set()
    _, result = execute(e, "cancelled", cancelled)
    assert result["status"] == "cancelled", result


def test_candidate_cannot_write_checker_inputs_or_code():
    source = fixture_source()
    replacement = """def add(a, b):
    import os
    if os.path.exists('/verifier'):
        for path in ('/verifier/inputs.json', '/verifier/probe.py'):
            try:
                with open(path, 'w') as stream:
                    stream.write('tampered')
                return 999
            except OSError:
                pass
    return a + b
"""
    candidate = admit(
        source,
        Import(
            snapshot_id=source["id"],
            patch=patch_for(source, replacement=replacement),
            approved_paths=["library.py"],
        ),
    )
    e = validated(candidate=candidate)
    _, result = execute(e, "actual-checker-write-rejection")
    assert result["status"] == "completed", result


def test_real_independent_timeout_and_setup_failure():
    source = fixture_source()
    replacement = """def add(a, b):
    if a < 0:
        import time
        time.sleep(10)
    return a + b
"""
    candidate = admit(
        source,
        Import(
            snapshot_id=source["id"],
            patch=patch_for(source, replacement=replacement),
            approved_paths=["library.py"],
        ),
    )
    e = validated(candidate=candidate, timeout_seconds=1)
    _, result = execute(e, "independent-timeout")
    assert result["ordinary"]["status"] == "tests_passed"
    assert result["status"] == "timeout", result
    e["stage"] = e["approval"]["stage"] = "validation"
    e["verification"]["plan"]["setup"] = [
        ["python", "-c", "raise RuntimeError('offline dependency unavailable')"]
    ]
    from workbench.evaluator.catalog import identity

    e["verification"]["id"] = identity(e["verification"]["plan"])
    e["approval"]["verification_id"] = e["verification"]["id"]
    _, result = execute(e, "verifier-preparation-failure")
    assert result["status"] == "validation_failed", result
    assert result["controls"][0]["status"] == "verifier_preparation_failed"
