"""Offline G1 boundaries. No GitHub, Docker daemon, project imports or model calls."""

import copy
import difflib
import gzip
import io
import tarfile
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from workbench.config import settings
from workbench.evaluator.catalog import identity
from workbench.repository_audit.admission import admit, check_plan, rebuild
from workbench.repository_audit.contracts import POLICY, Confirm, Import, Intake, Plan, production
from workbench.repository_audit.execution import engine_id, validate
from workbench.repository_audit.intake import (
    Rejected,
    blob_hash,
    bounded_get,
    decode_files,
    fetch,
    git_tree,
    snapshot_record,
    summary,
    unpack,
)
from workbench.repository_audit.routes import router
from workbench.repository_audit.service import view

SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64


def fixture_source(runtime="python312"):
    files = {
        "library.py": b"def add(a, b):\n    return a - b\n",
        "tests/test_library.py": (
            b"from library import add\n\ndef test_sum():\n    assert add(1, 2) == 3\n"
        ),
        "LICENSE": b"Synthetic MIT licensed fixture for deterministic G1 tests.\n",
    }
    if runtime == "node22":
        files = {
            "index.js": b"exports.add = (a, b) => a - b;\n",
            "test.js": (
                b"const {test} = require('node:test');\n"
                b"const assert = require('node:assert/strict');\n"
                b"const {add} = require('./index');\n"
                b"test('sum', () => assert.equal(add(1, 2), 3));\n"
            ),
            "LICENSE": files["LICENSE"],
        }
    modes = dict.fromkeys(files, "100644")
    return snapshot_record(
        "fixture/project",
        SHA,
        git_tree(files, modes),
        files,
        modes,
        {
            "license": {"spdx_id": "MIT"},
            "attribution_files": ["LICENSE"],
            "adapter": "offline-synthetic-fixture",
        },
    )


def patch_for(source, file="library.py", replacement=None):
    before = decode_files(source)[file].decode()
    after = replacement if replacement is not None else before.replace("a - b", "a + b")
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile="a/" + file,
            tofile="b/" + file,
        )
    )


def candidate_for(source=None):
    source = source or fixture_source()
    file = "library.py" if "library.py" in source["files"] else "index.js"
    return admit(
        source,
        Import(snapshot_id=source["id"], patch=patch_for(source, file), approved_paths=[file]),
    )


def plan_for(source, candidate, **kwargs):
    return Plan(
        snapshot_id=source["id"],
        candidate_hash=candidate["candidate_hash"],
        runtime="python312",
        image_id=IMAGE,
        tests=["python", "-m", "pytest", "-q"],
        test_description="Synthetic fixture upstream test",
        **kwargs,
    ).model_dump()


def archive_for(files, special=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        root = tarfile.TarInfo("repo-sha")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        for p, data in files.items():
            entry = tarfile.TarInfo("repo-sha/" + p)
            entry.size = len(data)
            entry.mode = 0o644
            if special:
                entry.type = special
                entry.linkname = "/outside"
                entry.size = 0
            archive.addfile(entry, io.BytesIO(data))
    return gzip.compress(stream.getvalue())


@pytest.mark.parametrize(
    "repo",
    [
        "https://github.com/a/b",
        "http://127.0.0.1/x",
        "git@github.com:a/b",
        "a/b.git",
        "a/../x",
        "a/b?x",
        "user:secret@github.com/a",
        "a/b#main",
        "a/.git",
        "a/b/c",
        "a/..",
        "a%2fb/c",
        "localhost:8000/x",
    ],
)
def test_invalid_repository_identifiers(repo):
    with pytest.raises(ValidationError):
        Intake(repository=repo, base_commit=SHA)


@pytest.mark.parametrize("commit", ["main", "v1.0", "a" * 7, "A" * 40, "a" * 39, "a" * 41])
def test_only_full_immutable_commit_allowed(commit):
    with pytest.raises(ValidationError):
        Intake(repository="owner/repo", base_commit=commit)
    assert Intake(repository="Owner/Repo", base_commit=SHA).repository == "owner/repo"


async def test_bounded_adapter_verifies_commit_tree_blob_and_license():
    source = fixture_source()
    files = decode_files(source)
    tree = source["git_tree"]
    observed = []

    def handler(request):
        observed.append(request)
        if request.url.host == "codeload.github.com":
            return httpx.Response(200, content=archive_for(files))
        endpoint = request.url.path
        if endpoint.endswith("/commits/" + SHA):
            return httpx.Response(200, json={"sha": SHA, "commit": {"tree": {"sha": tree}}})
        if "/git/trees/" in endpoint:
            return httpx.Response(
                200,
                json={
                    "sha": tree,
                    "truncated": False,
                    "tree": [
                        {
                            "path": p,
                            "mode": "100644",
                            "type": "blob",
                            "sha": blob_hash(v),
                            "size": len(v),
                        }
                        for p, v in files.items()
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "private": False,
                "full_name": "fixture/project",
                "size": 1,
                "license": {"spdx_id": "MIT"},
            },
        )

    fetched = await fetch(
        Intake(repository="fixture/project", base_commit=SHA), httpx.MockTransport(handler)
    )
    assert decode_files(fetched) == files
    assert fetched["git_tree"] == tree
    assert fetched["base_commit"] == SHA
    assert summary(fetched)["license_texts"]["LICENSE"].startswith("Synthetic")
    assert len(observed) == 4
    assert all(r.url.scheme == "https" and "authorization" not in r.headers for r in observed)


@pytest.mark.parametrize(
    "change",
    [
        "redirect",
        "private",
        "oversize",
        "wrong_commit",
        "truncated",
        "submodule",
        "symlink",
        "wrong_tree",
        "wrong_blob",
    ],
)
async def test_adapter_fail_closed(change):
    source = fixture_source()
    files = decode_files(source)

    def handler(request):
        if change == "redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/secret"})
        if request.url.host == "codeload.github.com":
            return httpx.Response(200, content=archive_for(files))
        if "/commits/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sha": "b" * 40 if change == "wrong_commit" else SHA,
                    "commit": {"tree": {"sha": source["git_tree"]}},
                },
            )
        if "/git/trees/" in request.url.path:
            entries = [
                {"path": p, "mode": "100644", "type": "blob", "sha": blob_hash(v), "size": len(v)}
                for p, v in files.items()
            ]
            if change in ("symlink", "submodule"):
                entries[0].update(
                    mode="120000" if change == "symlink" else "160000",
                    type="blob" if change == "symlink" else "commit",
                )
            if change == "wrong_blob":
                entries[0]["sha"] = "c" * 40
            return httpx.Response(
                200,
                json={
                    "sha": "d" * 40 if change == "wrong_tree" else source["git_tree"],
                    "truncated": change == "truncated",
                    "tree": entries,
                },
            )
        return httpx.Response(
            200,
            json={
                "private": change == "private",
                "size": 20001 if change == "oversize" else 1,
                "full_name": "fixture/project",
            },
        )

    with pytest.raises(Rejected):
        await fetch(
            Intake(repository="fixture/project", base_commit=SHA), httpx.MockTransport(handler)
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.github.com/x",
        "https://evil.example/x",
        "https://api.github.com:444/x",
        "https://user:pass@api.github.com/x",
        "https://127.0.0.1/x",
        "file:///etc/passwd",
    ],
)
async def test_transport_does_not_request_unsafe_url(url):
    def handler(request):
        pytest.fail("Unsafe URL reached transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Rejected):
            await bounded_get(client, url, 20)


async def test_fetch_deadline_and_response_budget(monkeypatch):
    async def handler(request):
        return httpx.Response(200, content=b"x" * 21)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Rejected):
            await bounded_get(client, "https://api.github.com/x", 20)


@pytest.mark.parametrize(
    "special", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]
)
def test_archive_special_files_rejected(special):
    with pytest.raises(Rejected):
        unpack(archive_for({"file.py": b"x"}, special))


@pytest.mark.parametrize(
    "files",
    [
        {"../outside": b"x"},
        {"/absolute": b"x"},
        {".git/config": b"x"},
        {".gitmodules": b"x"},
        {"file": b"version https://git-lfs.github.com/spec/v1\n"},
        {"large": b"x" * 1000001},
        {f"file{i}": b"x" for i in range(1001)},
    ],
)
def test_unsupported_or_oversized_archive(files):
    with pytest.raises(ValueError):
        unpack(archive_for(files))


def test_expansion_and_source_limits():
    with pytest.raises(Rejected, match="Expanded"):
        unpack(gzip.compress(b"x" * 16000001))
    with pytest.raises(Rejected, match="Compressed"):
        unpack(b"x" * 8000001)
    with pytest.raises(Rejected):
        unpack(archive_for({f"file{i}": b"x" * 999999 for i in range(9)}))


def test_exact_patch_and_candidate_identity_separate_from_repository():
    source = fixture_source()
    candidate = candidate_for(source)
    assert rebuild(source, candidate)["library.py"] == b"def add(a, b):\n    return a + b\n"
    assert source["id"] != candidate["id"] != candidate["candidate_hash"]
    assert candidate["submitted_patch_hash"] != candidate["candidate_hash"]
    altered = admit(
        source,
        Import(
            snapshot_id=source["id"],
            patch=candidate["patch"],
            approved_paths=["library.py"],
            author_label="User claims tool X",
        ),
    )
    assert altered["candidate_hash"] == candidate["candidate_hash"]
    assert altered["id"] != candidate["id"]
    assert altered["provenance"]["category"] == "user_declared"
    mutated = copy.deepcopy(candidate)
    mutated["modified"]["library.py"] = "malicious override"
    with pytest.raises(ValueError):
        rebuild(source, mutated)


@pytest.mark.parametrize(
    "transform",
    [
        lambda p: p.replace("a - b", "stale"),
        lambda p: p.replace("library.py", "../out.py"),
        lambda p: p.replace("library.py", "tests/test_library.py"),
        lambda p: "GIT binary patch\n" + p,
        lambda p: p + p,
        lambda p: "\ufeff" + p,
        lambda p: p.replace("\n", "\r\n"),
        lambda p: p.replace("+++ b/library.py", "+++ /dev/null"),
        lambda p: "new file mode 120000\n" + p,
    ],
)
def test_patch_rejections(transform):
    source = fixture_source()
    with pytest.raises(ValueError):
        admit(
            source,
            Import(
                snapshot_id=source["id"],
                patch=transform(patch_for(source)),
                approved_paths=["library.py"],
            ),
        )


@pytest.mark.parametrize(
    "p",
    [
        "tests/a.py",
        "test.js",
        "src/a.test.js",
        "setup.py",
        ".github/tool.py",
        "scripts/start.js",
        "package.json",
        "conftest.py",
        "pytest.config.js",
    ],
)
def test_execution_sensitive_scope_is_unsupported(p):
    assert not production(p)


def test_no_project_import_during_intake_or_admission(tmp_path):
    marker = tmp_path / "HOST_EXECUTED"
    files = {
        "library.py": (
            f"from pathlib import Path\nPath({str(marker)!r}).touch()\nvalue = 1\n"
        ).encode()
    }
    modes = {"library.py": "100644"}
    source = snapshot_record(
        "fixture/malicious", SHA, git_tree(files, modes), files, modes, {"attribution_files": []}
    )
    patch = patch_for(
        source, replacement=files["library.py"].decode().replace("value = 1", "value = 2")
    )
    candidate = admit(
        source, Import(snapshot_id=source["id"], patch=patch, approved_paths=["library.py"])
    )
    rebuild(source, candidate)
    assert not marker.exists()


def completed_result(source, candidate, plan, audit_id):
    entry = {
        "phase": "tests",
        "argv": plan["tests"],
        "working_directory": "/source",
        "status": "finished",
        "exit_code": 0,
        "stdout": "exact output",
        "stderr": "",
        "counts": None,
    }
    return {
        "audit_id": str(audit_id),
        "snapshot_id": source["id"],
        "source_binding": {
            "repository": source["repository"],
            "base_commit": source["base_commit"],
            "git_tree": source["git_tree"],
            "source_tree_hash": source["source_tree_hash"],
            "submitted_patch_hash": candidate["submitted_patch_hash"],
        },
        "candidate_id": candidate["id"],
        "candidate_hash": candidate["candidate_hash"],
        "plan_id": identity(plan),
        "engine_id": engine_id(),
        "policy": POLICY,
        "independent": {"status": "not_configured"},
        "ordinary": entry,
        "commands": [entry],
        "status": "tests_passed",
        "runtime": {"image_id": IMAGE},
        "sandbox": {
            "user": "1000:1000",
            "host_config": {
                "NetworkMode": "none",
                "ReadonlyRootfs": True,
                "Memory": 536870912,
                "MemorySwap": 536870912,
                "NanoCpus": 1000000000,
                "PidsLimit": 64,
                "ShmSize": 8388608,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
                "Tmpfs": {
                    "/work": "rw,nosuid,nodev,size=128m,mode=1777",
                    "/tmp": "rw,nosuid,nodev,size=8m,mode=1777",
                },
            },
            "mounts": [{"Type": "volume", "Destination": "/source", "RW": False}],
        },
        "cleanup": [{"kind": "containers", "id": "container", "confirmed_absent": True}],
        "container_id": "container",
        "executed_source_hashes": candidate["applied_source_hashes"],
        "ended_at": datetime.now(UTC).isoformat(),
        "duration_ms": 1,
    }


def test_evidence_bindings_and_missing_logs_counts_setup():
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    audit_id = uuid4()
    result = completed_result(source, candidate, plan, audit_id)
    validate(result, audit_id, source, candidate, plan)
    assert result["ordinary"]["counts"] is None
    for key in (
        "candidate_id",
        "candidate_hash",
        "snapshot_id",
        "plan_id",
        "engine_id",
        "executed_source_hashes",
        "runtime",
        "commands",
        "independent",
        "ended_at",
        "sandbox",
        "source_binding",
    ):
        bad = copy.deepcopy(result)
        bad.pop(key)
        with pytest.raises((ValueError, KeyError)):
            validate(bad, audit_id, source, candidate, plan)
    for field in ("argv", "exit_code", "status", "working_directory"):
        bad = copy.deepcopy(result)
        bad["commands"][0][field] = "wrong"
        with pytest.raises(ValueError):
            validate(bad, audit_id, source, candidate, plan)
    dependency_plan = plan_for(
        source, candidate, setup=[["pip", "install", "--no-index", "missing"]]
    )
    with pytest.raises(ValueError):
        validate(
            result | {"plan_id": identity(dependency_plan)},
            audit_id,
            source,
            candidate,
            dependency_plan,
        )
    row = SimpleNamespace(
        id=audit_id,
        candidate_id=candidate["id"],
        plan_id=identity(plan),
        status="tests_passed",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        evidence={
            "snapshot": source,
            "candidate": candidate,
            "plan": plan,
            "engine_id": engine_id(),
            "approval": {
                "local_owner": True,
                "candidate_id": candidate["id"],
                "plan_id": identity(plan),
                "approved_at": datetime.now(UTC).isoformat(),
            },
            "result": result,
            "result_hash": identity(result),
        },
    )
    assert view(row)["status"] == "tests_passed"
    for missing in ("result", "approval"):
        damaged = copy.deepcopy(row)
        damaged.evidence.pop(missing)
        assert view(damaged)["status"] == "invalid_evidence"
        assert "result" not in view(damaged)["evidence"]
    row.evidence["result"]["status"] = "infrastructure_error"
    assert view(row)["status"] == "invalid_evidence"
    assert "result" not in view(row)["evidence"]


def test_plan_cannot_inherit_other_candidate_or_directory_or_policy():
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    check_plan(source, candidate, plan)
    for override in (
        {"candidate_hash": "c" * 64},
        {"snapshot_id": "d" * 64},
        {"working_directory": "../escape"},
        {"working_directory": "missing"},
        {"policy_hash": "e" * 64},
        {"tests": "python -m pytest"},
        {"tests": ["python", "bad\x00"]},
    ):
        with pytest.raises(ValueError):
            check_plan(source, candidate, plan | override)
    with pytest.raises(ValidationError):
        Confirm.model_validate(
            {
                "candidate_id": candidate["id"],
                "plan_id": identity(plan),
                "approve_exact_plan": False,
                "confirm_local_execution": True,
            }
        )


async def test_local_only_unapproved_plans_and_recorded_boundary(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        assert (await client.post("/api/repository-audits/runs", json={})).status_code == 422
        assert (
            await client.post(
                "/api/repository-audits/sources",
                json={"repository": "a/b", "base_commit": SHA},
                headers={"Origin": "https://outside.example"},
            )
        ).status_code == 403
        monkeypatch.setattr(settings, "guest_access", True)
        assert (await client.get("/api/repository-audits/runs")).status_code == 403
    monkeypatch.setattr(settings, "guest_access", False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://public.example"
    ) as client:
        assert (await client.get("/api/repository-audits/runs")).status_code == 403
    from workbench import release

    (tmp_path / "index.html").write_text("fixture")
    monkeypatch.setattr(release, "WEB", tmp_path)
    release.requests.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=release.app), base_url="http://release"
    ) as client:
        for endpoint in ("sources", "candidates", "plans", "runs", "runtimes"):
            assert (await client.get("/api/repository-audits/" + endpoint)).status_code == 404
            assert (
                await client.post("/api/repository-audits/" + endpoint, json={})
            ).status_code == 405


@pytest.mark.parametrize(
    "key,value",
    [
        ("NetworkMode", "host"),
        ("Memory", 0),
        ("PidsLimit", 0),
        ("ReadonlyRootfs", False),
        ("NanoCpus", 0),
        ("CapDrop", []),
        ("Tmpfs", {}),
    ],
)
def test_unestablished_actual_sandbox_policy_cannot_pass(key, value):
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    audit_id = uuid4()
    result = completed_result(source, candidate, plan, audit_id)
    result["sandbox"]["host_config"][key] = value
    with pytest.raises(ValueError):
        validate(result, audit_id, source, candidate, plan)


def test_missing_output_is_not_valid_evidence_even_with_zero_exit():
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    audit_id = uuid4()
    result = completed_result(source, candidate, plan, audit_id)
    result["commands"][0].pop("stdout")
    with pytest.raises(ValueError):
        validate(result, audit_id, source, candidate, plan)


def test_uncertain_docker_removal_polls_same_identity_until_confirmed_absent(monkeypatch):
    from docker.errors import APIError, NotFound

    from workbench.repository_audit.execution import remove_confirmed

    calls = []

    class Collection:
        def get(self, key):
            calls.append(key)
            if len(calls) == 3:
                raise NotFound("gone")
            return SimpleNamespace(
                remove=lambda **kwargs: (_ for _ in ()).throw(
                    APIError("removal already in progress")
                )
            )

    monkeypatch.setattr("workbench.repository_audit.execution.time.sleep", lambda value: None)
    assert remove_confirmed(
        SimpleNamespace(containers=Collection()), SimpleNamespace(id="same-id"), "containers"
    )
    assert calls == ["same-id"] * 3


def test_unconfirmed_cleanup_cannot_be_saved_as_passing_evidence():
    source = fixture_source()
    candidate = candidate_for(source)
    plan = plan_for(source, candidate)
    audit_id = uuid4()
    result = completed_result(source, candidate, plan, audit_id)
    result["cleanup"][0]["confirmed_absent"] = False
    with pytest.raises(ValueError, match="cleanup"):
        validate(result, audit_id, source, candidate, plan)


@pytest.mark.parametrize("invalid_result", [False, True])
async def test_transport_loss_is_infrastructure_error_and_invalid_result_is_retained(
    monkeypatch, invalid_result
):
    from workbench.repository_audit import service

    original = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(200, json={"broken": "result"})
            if invalid_result
            else httpx.Response(500)
        )
    )
    monkeypatch.setattr(
        service.httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    outcomes = []

    class Manager(service.RepositoryAuditManager):
        async def stop(self, audit_id):
            pass

        async def wait_terminal(self, audit_id, trace=None):
            if invalid_result:
                return {"broken": "result"}
            raise TimeoutError

        async def finish(self, audit_id, result=None, failure=None, unvalidated=None):
            if result is not None:
                raise ValueError("bad binding")
            outcomes.append((failure, unvalidated))

    manager = Manager()
    await manager.run(uuid4(), {})
    assert (
        outcomes == [("invalid_evidence", {"broken": "result"})]
        if invalid_result
        else outcomes == [("infrastructure_error", None)]
    )
