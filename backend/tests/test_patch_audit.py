"""Offline boundary/evidence regressions. Real candidate execution lives in the browser suite."""

import copy
import difflib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from workbench.config import ROOT, settings
from workbench.evaluator.catalog import identity
from workbench.evaluator.experiment_catalog import task
from workbench.patch_audit.admission import MAX_PATCH_BYTES, admit, apply_patch, rebuild
from workbench.patch_audit.curated import FAIL, PASS, examples
from workbench.patch_audit.execution import validate, verifier_id
from workbench.patch_audit.routes import router
from workbench.patch_audit.service import AuditManager, validate_envelope, view


def test_exact_multihunk_application_and_git_header():
    base = "".join(f"line {i}\n" for i in range(50))
    changed = base.replace("line 5\n", "replacement 5\n").replace("line 40\n", "replacement 40\n")
    patch = "".join(
        difflib.unified_diff(
            base.splitlines(True),
            changed.splitlines(True),
            fromfile="a/source.py",
            tofile="b/source.py",
        )
    )
    assert patch.count("@@ -") == 2
    spec = {
        "files": {"source.py": base, "tests/test.py": "trusted"},
        "allowed_paths": ["source.py"],
    }
    assert apply_patch(spec, patch) == {"source.py": changed, "tests/test.py": "trusted"}
    header = "diff --git a/source.py b/source.py\nindex 123abc..456def 100644\n"
    assert apply_patch(spec, header + patch)["source.py"] == changed
    with pytest.raises(ValueError, match="stale"):
        apply_patch(spec, patch.replace("@@ -3,", "@@ -4,", 1))


@pytest.mark.parametrize(
    "transform",
    [
        lambda p: "",
        lambda p: p + "garbage\n",
        lambda p: p.replace("boltons/dictutils.py", "../outside.py"),
        lambda p: p.replace("boltons/dictutils.py", "/absolute.py"),
        lambda p: p.replace("boltons/dictutils.py", "tests/test_dictutils.py"),
        lambda p: p.replace("boltons/dictutils.py", "LICENSE"),
        lambda p: p.replace("--- a/boltons/dictutils.py", "--- /dev/null"),
        lambda p: p.replace("+++ b/boltons/dictutils.py", "+++ /dev/null"),
        lambda p: p.replace("+++ b/boltons/dictutils.py", "+++ b/boltons/urlutils.py"),
        lambda p: "old mode 100644\nnew mode 100755\n" + p,
        lambda p: (
            "diff --git a/boltons/dictutils.py b/boltons/dictutils.py\nindex 123..456 120000\n" + p
        ),
        lambda p: "GIT binary patch\n" + p,
        lambda p: p.replace("Called ``addlist``", "Wrong pinned context", 1),
        lambda p: p + "\\ No newline at end of file\n",
        lambda p: p.replace("\n", "\r\n"),
        lambda p: p + "\x00",
        lambda p: p + p,
        lambda p: "x" * (MAX_PATCH_BYTES + 1),
    ],
)
def test_malformed_stale_oversized_and_unauthorized_patches(transform):
    patch = examples()[FAIL]["candidate"]["patch"]
    with pytest.raises(ValueError):
        apply_patch(task("boltons-addlist"), transform(patch))


def test_genuine_source_identity_and_user_declared_provenance_are_separate():
    retained = examples()[FAIL]["candidate"]
    assert (
        retained["candidate_hash"]
        == "5cab12b5c1b25239d4418e84aae45f166041390a6895d24f2a6ae1d1d85d6246"
    )
    imported = admit(
        "boltons-addlist", retained["patch"], {"category": "user_declared", "producer": "Codex"}
    )
    assert imported["candidate_hash"] == retained["candidate_hash"]
    assert imported["id"] != retained["id"]
    assert imported == admit("boltons-addlist", retained["patch"], imported["provenance"])
    assert imported["provenance"]["category"] == "user_declared"
    assert (
        rebuild(imported)["files"]["tests/test_dictutils.py"]
        == task("boltons-addlist")["files"]["tests/test_dictutils.py"]
    )
    changed = copy.deepcopy(imported)
    changed["modified"]["boltons/urlutils.py"] += "\n# changed\n"
    with pytest.raises(ValueError):
        rebuild(changed)
    assert (
        examples()[PASS]["candidate"]["candidate_hash"]
        == "ad55f9039233a94d71447bbf043e94537de73ca0aa7d2b5174b9753abcb90f29"
    )
    assert "temperature=0" in retained["provenance"]["metadata_note"]
    assert retained["provenance"]["request_settings"]["temperature"] == 1


async def test_import_has_no_execution_and_cannot_claim_captured_authorship(monkeypatch):
    from workbench.patch_audit import routes

    stored = []

    async def save(c):
        stored.append(c)
        return c

    monkeypatch.setattr(routes, "store_candidate", save)
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        payload = {
            "task_id": "boltons-addlist",
            "patch": examples()[FAIL]["candidate"]["patch"],
            "producer": "Codex",
            "category": "user_declared",
        }
        r = await c.post("/api/patch-audits/candidates", json=payload)
        assert r.status_code == 201 and len(stored) == 1
        assert r.json()["provenance"]["category"] == "user_declared"
        assert not hasattr(app.state, "patch_audits")  # No executor/manager needed for import.
        assert (
            await c.post(
                "/api/patch-audits/candidates", json=payload | {"category": "retained_model"}
            )
        ).status_code == 422
        assert (
            await c.post("/api/patch-audits/candidates", json=payload | {"patch": "invalid"})
        ).status_code == 422
        assert len(stored) == 1
        assert (
            await c.post(
                "/api/patch-audits/candidates",
                json=payload,
                headers={"Origin": "https://outside.example"},
            )
        ).status_code == 403
        monkeypatch.setattr(settings, "guest_access", True)
        assert (await c.post("/api/patch-audits/candidates", json=payload)).status_code == 403
        assert (await c.get("/api/patch-audits/tasks")).status_code == 403


def test_binding_missing_evidence_and_execution_failures_are_not_passes():
    c = examples()[FAIL]["candidate"]
    result = examples()[FAIL]["recorded_result"]
    audit_id = uuid4()
    envelope = {
        "audit_id": str(audit_id),
        "candidate_id": c["id"],
        "record_hash": c["record_hash"],
        "result": result,
    }
    validate_envelope(audit_id, c, envelope)
    for changed in (envelope | {"audit_id": str(uuid4())}, envelope | {"candidate_id": "wrong"}):
        with pytest.raises(ValueError):
            validate_envelope(audit_id, c, changed)
    bad = copy.deepcopy(envelope)
    bad["result"]["binding"]["candidate_hash"] = "0" * 64
    with pytest.raises(ValueError):
        validate_envelope(audit_id, c, bad)
    evidence = {
        "task": {k: v for k, v in task(c["task_id"]).items() if k != "files"},
        "candidate": c,
    }
    row = SimpleNamespace(
        id=audit_id,
        candidate_id=c["id"],
        candidate_hash=c["candidate_hash"],
        status="passed",
        evidence=evidence,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert view(row)["status"] == "invalid_evidence"
    row.status = "infrastructure_error"
    row.evidence = evidence | {"reason": "Missing image"}
    assert view(row)["status"] == "infrastructure_error"
    row.status = "interrupted"
    assert view(row)["status"] == "interrupted"
    row.status = "failed"
    row.evidence = evidence | {"envelope": envelope, "envelope_hash": identity(envelope)}
    assert view(row)["status"] == "failed"
    row.evidence["envelope_hash"] = "0" * 64
    invalid = view(row)
    assert invalid["status"] == "invalid_evidence"
    assert invalid["evidence"]["unvalidated_envelope"] == envelope
    assert "envelope" not in invalid["evidence"]
    assert verifier_id("more-seekable") != __import__(
        "workbench.evaluator.experiment_runner", fromlist=["verifier_id"]
    ).verifier_id("more-seekable")
    with pytest.raises(ValueError):
        validate(
            task("boltons-addlist"),
            rebuild(c),
            {"status": "passed", "candidate_hash": c["candidate_hash"]},
        )


async def test_bounded_terminal_reconciliation_waits_for_publication(monkeypatch):
    manager = AuditManager()
    seen = []

    async def terminal(_):
        seen.append(1)
        return {"result": "terminal"} if len(seen) == 3 else None

    monkeypatch.setattr(manager, "terminal", terminal)
    assert await manager.wait_terminal(uuid4()) == {"result": "terminal"}
    assert len(seen) == 3


async def test_recorded_audits_are_explicit_hashed_and_have_no_live_authority(
    monkeypatch, tmp_path
):
    from workbench import release

    release.guests.clear()
    release.requests.clear()
    manifest = json.loads((ROOT / "recordings/patch-audit-manifest.json").read_text())
    assert [r["id"] for r in manifest["records"]] == [FAIL, PASS]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=release.app), base_url="http://testserver"
    ) as c:
        for item in manifest["records"]:
            r = await c.get("/api/recorded-audits/" + item["id"])
            assert r.status_code == 200
            saved = r.json()
            assert saved["execution_mode"] == "recorded"
            assert saved["evidence"]["source_validation"]["result_hash"] == identity(
                saved["evidence"]["envelope"]["result"]
            )
            assert (
                saved["evidence"]["candidate"]["candidate_hash"]
                == examples()[item["id"]]["candidate"]["candidate_hash"]
            )
        for path in (
            "/api/patch-audits/tasks",
            "/api/patch-audits/candidates",
            "/api/patch-audits/runs",
        ):
            assert (await c.get(path)).status_code == 404
            assert (await c.post(path, json={})).status_code == 405
        data = ROOT / "recordings" / manifest["records"][0]["file"]
        (tmp_path / "patch-audit-manifest.json").write_text(json.dumps(manifest))
        (tmp_path / data.name).write_bytes(data.read_bytes() + b" ")
        monkeypatch.setattr(release, "RECORDINGS", tmp_path)
        assert (await c.get("/api/recorded-audits/" + FAIL)).status_code == 503
    release.guests.clear()
    release.requests.clear()


def test_patch_admission_does_not_import_candidate_python():
    spec = task("more-bucket")
    path = spec["allowed_paths"][0]
    changed = (
        spec["files"][path]
        + "\nraise AssertionError('candidate must never execute during admission')\n"
    )
    patch = "".join(
        difflib.unified_diff(
            spec["files"][path].splitlines(True),
            changed.splitlines(True),
            fromfile="a/" + path,
            tofile="b/" + path,
        )
    )
    value = admit(spec["id"], patch, {"category": "unknown"})
    assert rebuild(value)["files"][path] == changed


def test_new_adapter_checks_original_binding_hash_and_admitted_verifier_snapshot():
    from workbench.evaluator.runner import POLICY

    spec = task("more-seekable")
    value = rebuild(examples()["more-seekable-reference"]["candidate"])
    historical = "a" * 64  # Deterministic procedure-snapshot fixture; no execution claim.
    binding = {
        "task_id": spec["id"],
        "base_commit": spec["base_commit"],
        "spec_hash": spec["spec_hash"],
        "candidate_hash": value["candidate_hash"],
        "patch_hash": value["patch_hash"],
        "verifier_hash": historical,
        "policy_hash": identity(POLICY),
        "executed_file_hashes": value["source_hashes"],
        "image_id": "sha256:" + "b" * 64,
    }
    result = {
        "candidate_hash": value["candidate_hash"],
        "status": "infrastructure_error",
        "binding": binding,
        "binding_hash": identity(binding),
        "ordinary": None,
        "independent": None,
    }
    validate(spec, value, result, expected_verifier=historical)
    with pytest.raises(ValueError, match="verifier"):
        validate(spec, value, result)
    with pytest.raises(ValueError, match="integrity"):
        validate(spec, value, result | {"binding_hash": "0" * 64}, expected_verifier=historical)
