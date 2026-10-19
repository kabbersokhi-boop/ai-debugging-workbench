"""Trusted broker: fixed Docker policy, exact argv commands and bounded stream capture."""

import io
import struct
import tarfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.types import LogConfig, Ulimit
from requests.exceptions import RequestException

from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.runner import LABEL
from workbench.repository_audit.admission import check_plan, rebuild
from workbench.repository_audit.contracts import POLICY, RUNTIMES


def engine_id():
    return identity(
        {
            name: digest(Path(__file__).with_name(name).read_bytes())
            for name in ("execution.py", "admission.py", "contracts.py", "intake.py")
        }
    )


def runtimes():
    client = docker.from_env(timeout=5)
    try:
        result = []
        for runtime, tag in RUNTIMES.items():
            try:
                image = client.images.get(tag)
                result.append(
                    {"runtime": runtime, "image_id": image.id, "tag": tag, "available": True}
                )
            except ImageNotFound:
                result.append({"runtime": runtime, "tag": tag, "available": False})
        return result
    finally:
        client.close()


def verify_sandbox(sandbox):
    config = sandbox["host_config"]
    expected = {
        "NetworkMode": "none",
        "ReadonlyRootfs": True,
        "Memory": 536870912,
        "MemorySwap": 536870912,
        "NanoCpus": 1000000000,
        "PidsLimit": 64,
        "ShmSize": 8388608,
    }
    if (
        sandbox["user"] != "1000:1000"
        or any(config.get(k) != v for k, v in expected.items())
        or config.get("CapDrop") != ["ALL"]
        or "no-new-privileges:true" not in config.get("SecurityOpt", [])
    ):
        raise ValueError("Docker did not establish the approved resource/security limits")
    mounts = sandbox["mounts"]
    source = [m for m in mounts if m["Destination"] == "/source"]
    if (
        len(source) != 1
        or source[0]["Type"] != "volume"
        or source[0]["RW"]
        or any(
            m["Type"] not in ("volume", "tmpfs")
            or m["Destination"] not in ("/source", "/work", "/tmp")
            for m in mounts
        )
    ):
        raise ValueError("Unexpected or writable source/host mount")
    if config.get("Tmpfs") != {
        "/work": "rw,nosuid,nodev,size=128m,mode=1777",
        "/tmp": "rw,nosuid,nodev,size=8m,mode=1777",
    }:
        raise ValueError("Scratch storage limits differ from the approved policy")


def remove_confirmed(client, resource, kind):
    """A timeout/409 is an uncertain removal: poll the same Docker identity until absent."""
    key = resource.name if kind == "volumes" else resource.id
    collection = getattr(client, kind)
    deadline = time.monotonic() + 20
    while True:
        try:
            current = collection.get(key)
        except NotFound:
            return True
        except (APIError, RequestException):
            current = None
        if current is not None:
            try:
                current.remove(force=True)
            except NotFound:
                return True
            except (APIError, RequestException):
                pass
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def command(client, container, argv, cwd, cancel, deadline):
    started = time.monotonic()
    record: dict[str, Any] = {
        "argv": argv,
        "working_directory": cwd,
        "started_at": datetime.now(UTC).isoformat(),
        "stdout": "",
        "stderr": "",
        "exit_code": None,
        "counts": None,
        "counts_note": "Framework counts are not parsed; inspect the exact retained output.",
        "output_truncated": False,
    }
    execution = client.api.exec_create(container.id, argv, workdir=cwd, user="1000:1000")
    stream = client.api.exec_start(execution["Id"], socket=True)
    sock = stream._sock
    sock.settimeout(0.2)
    buffers = {1: bytearray(), 2: bytearray()}
    pending = bytearray()
    try:
        while True:
            if cancel.is_set() or time.monotonic() >= deadline:
                record["status"] = "cancelled" if cancel.is_set() else "timeout"
                container.kill()
                break
            try:
                chunk = sock.recv(16384)
            except TimeoutError:
                continue
            if not chunk:
                break
            pending.extend(chunk)
            while len(pending) >= 8:
                channel, size = pending[0], struct.unpack(">I", pending[4:8])[0]
                if size > 16_777_216 or channel not in (1, 2):
                    raise ValueError("Invalid Docker output frame")
                if len(pending) < size + 8:
                    break
                payload = pending[8 : size + 8]
                del pending[: size + 8]
                buf = buffers[channel]
                remaining = POLICY["output_bytes_per_stream"] - len(buf)
                buf.extend(payload[: max(0, remaining)])
                if len(payload) > remaining:
                    record["output_truncated"] = True
            if len(pending) > 16_777_224:
                raise ValueError("Docker output frame limit exceeded")
        state = client.api.exec_inspect(execution["Id"])
        record["exit_code"] = state.get("ExitCode")
        record.setdefault("status", "finished" if not state["Running"] else "infrastructure_error")
    finally:
        stream.close()
        record.update(
            stdout=bytes(buffers[1]).decode(errors="replace"),
            stderr=bytes(buffers[2]).decode(errors="replace"),
            ended_at=datetime.now(UTC).isoformat(),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
    return record


def evaluate(audit_id, snapshot, candidate, plan_value, cancel: threading.Event):
    files = rebuild(snapshot, candidate)
    plan = check_plan(snapshot, candidate, plan_value)
    started = time.monotonic()
    result: dict[str, Any] = {
        "version": "repository-result-v1",
        "audit_id": str(audit_id),
        "candidate_id": candidate["id"],
        "candidate_hash": candidate["candidate_hash"],
        "snapshot_id": snapshot["id"],
        "source_binding": {
            "repository": snapshot["repository"],
            "base_commit": snapshot["base_commit"],
            "git_tree": snapshot["git_tree"],
            "source_tree_hash": snapshot["source_tree_hash"],
            "submitted_patch_hash": candidate["submitted_patch_hash"],
        },
        "plan_id": identity(plan_value),
        "engine_id": engine_id(),
        "policy": POLICY,
        "independent": {"status": "not_configured"},
        "ordinary": {"status": "not_run", "counts": None},
        "commands": [],
        "status": "infrastructure_error",
        "started_at": datetime.now(UTC).isoformat(),
    }
    client = None
    volume = init = container = None
    try:
        client = docker.from_env(timeout=5)
        if cancel.is_set():
            result["status"] = "cancelled"
            return result
        image = client.images.get(RUNTIMES[plan.runtime])
        assert image.id is not None
        if image.id != plan.image_id:
            raise ValueError("Approved runtime image changed; review a new plan")
        result["runtime"] = {
            "image_id": image.id,
            "repo_digests": image.attrs.get("RepoDigests", []),
            "runtime": plan.runtime,
            "tag": RUNTIMES[plan.runtime],
        }
        labels = {LABEL: "repository-" + str(uuid4())}
        common: dict[str, Any] = dict(
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=POLICY["memory_bytes"],
            memswap_limit=POLICY["memory_bytes"],
            nano_cpus=1_000_000_000,
            pids_limit=POLICY["pids"],
            labels=labels,
            log_config=LogConfig(type="none"),
            use_config_proxy=False,
            shm_size="8m",
            ulimits=[
                Ulimit(name="fsize", soft=POLICY["file_bytes"], hard=POLICY["file_bytes"]),
                Ulimit(name="nofile", soft=128, hard=128),
            ],
        )
        volume = client.volumes.create(labels=labels)
        init = client.containers.create(
            image.id,
            ["sleep", "180"],
            user="0:0",
            volumes={volume.name: {"bind": "/source", "mode": "rw"}},
            **common,
        )
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
            for p, data in files.items():
                member = tarfile.TarInfo(p)
                member.size, member.mode = (
                    len(data),
                    0o555 if snapshot["modes"][p] == "100755" else 0o444,
                )
                archive.addfile(member, io.BytesIO(data))
        init.start()
        if not init.put_archive("/source", archive_bytes.getvalue()):
            raise RuntimeError("Source initialization failed")
        observed = {}
        stream, _ = init.get_archive("/source")
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as archive:
            for member in archive:
                if member.isfile():
                    reader = archive.extractfile(member)
                    assert reader is not None
                    observed[member.name.removeprefix("source/")] = digest(reader.read())
        if observed != candidate["applied_source_hashes"]:
            raise ValueError("Actual initialized source differs from admitted candidate")
        result["executed_source_hashes"] = observed
        if not remove_confirmed(client, init, "containers"):
            raise RuntimeError("Source initializer cleanup could not be confirmed")
        init = None
        if cancel.is_set():
            result["status"] = "cancelled"
            return result
        container = client.containers.create(
            image.id,
            ["sleep", "180"],
            user="1000:1000",
            working_dir="/work",
            environment={
                "HOME": "/tmp",
                "LANG": "C.UTF-8",
                "TZ": "UTC",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONPATH": "/work/deps:/source",
                "NODE_PATH": "/work/node_modules:/opt/test-tools/node_modules",
                "PIP_NO_INDEX": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "npm_config_offline": "true",
                "npm_config_cache": "/tmp/npm",
            },
            volumes={volume.name: {"bind": "/source", "mode": "ro"}},
            tmpfs={
                "/work": "rw,nosuid,nodev,size=128m,mode=1777",
                "/tmp": "rw,nosuid,nodev,size=8m,mode=1777",
            },
            **common,
        )
        result["container_id"] = container.id
        container.start()
        container.reload()
        host = container.attrs["HostConfig"]
        result["sandbox"] = {
            "user": container.attrs["Config"]["User"],
            "host_config": {
                k: host.get(k)
                for k in (
                    "NetworkMode",
                    "ReadonlyRootfs",
                    "CapDrop",
                    "SecurityOpt",
                    "Memory",
                    "MemorySwap",
                    "NanoCpus",
                    "PidsLimit",
                    "Tmpfs",
                    "ShmSize",
                )
            },
            "mounts": [
                {k: m.get(k) for k in ("Type", "Name", "Destination", "RW")}
                for m in container.attrs["Mounts"]
            ],
        }
        verify_sandbox(result["sandbox"])
        deadline = time.monotonic() + plan.timeout_seconds
        cwd = "/source" if plan.working_directory == "." else "/source/" + plan.working_directory
        for phase, argv in [("setup", c) for c in plan.setup] + [("tests", plan.tests)]:
            if cancel.is_set():
                result["status"] = "cancelled"
                return result
            entry = {"phase": phase, **command(client, container, argv, cwd, cancel, deadline)}
            result["commands"].append(entry)
            if phase == "tests":
                result["ordinary"] = entry
            if entry["status"] != "finished":
                result["status"] = entry["status"]
                return result
            if entry["exit_code"] != 0:
                result["status"] = (
                    "environment_preparation_failed" if phase == "setup" else "tests_failed"
                )
                return result
        result["status"] = "tests_passed"
        return result
    except Exception as error:
        result.update(
            status="infrastructure_error",
            reason=(
                f"Sandbox unavailable or execution failed: {type(error).__name__}: "
                f"{str(error)[:300]}"
            ),
        )
        return result
    finally:
        cleanup = []
        if container is not None:
            try:
                container.reload()
                result["container_state"] = {
                    k: container.attrs["State"].get(k) for k in ("OOMKilled", "Error")
                }
                if container.attrs["State"].get("OOMKilled"):
                    result["status"] = "infrastructure_error"
            except (APIError, RequestException):
                pass
        if client is not None:
            for kind, resource in (
                ("containers", container),
                ("containers", init),
                ("volumes", volume),
            ):
                if resource is not None:
                    try:
                        removed = remove_confirmed(client, resource, kind)
                    except Exception:
                        removed = False
                    cleanup.append(
                        {
                            "kind": kind,
                            "id": resource.name if kind == "volumes" else resource.id,
                            "confirmed_absent": removed,
                        }
                    )
            client.close()
        result["cleanup"] = cleanup
        if any(not item["confirmed_absent"] for item in cleanup):
            result.update(
                status="infrastructure_error",
                reason="Docker resource cleanup could not be confirmed",
            )
        result.update(
            ended_at=datetime.now(UTC).isoformat(),
            duration_ms=round((time.monotonic() - started) * 1000),
        )


def validate(result, audit_id, snapshot, candidate, plan_value, expected_engine=None):
    plan = check_plan(snapshot, candidate, plan_value)
    for key, value in {
        "audit_id": str(audit_id),
        "snapshot_id": snapshot["id"],
        "candidate_id": candidate["id"],
        "candidate_hash": candidate["candidate_hash"],
        "plan_id": identity(plan_value),
    }.items():
        if result.get(key) != value:
            raise ValueError(f"Result {key} binding mismatch")
    if (
        result.get("engine_id") != (expected_engine or engine_id())
        or result.get("policy") != POLICY
    ):
        raise ValueError("Execution engine or sandbox policy mismatch")
    if result.get("independent") != {"status": "not_configured"}:
        raise ValueError("G1 has no independent behavioral verification")
    status = result.get("status")
    if status not in {
        "tests_passed",
        "tests_failed",
        "environment_preparation_failed",
        "timeout",
        "cancelled",
        "infrastructure_error",
    }:
        raise ValueError("Unknown terminal execution status")
    binding = {
        "repository": snapshot["repository"],
        "base_commit": snapshot["base_commit"],
        "git_tree": snapshot["git_tree"],
        "source_tree_hash": snapshot["source_tree_hash"],
        "submitted_patch_hash": candidate["submitted_patch_hash"],
    }
    if result.get("source_binding") != binding:
        raise ValueError("Repository, base or patch binding mismatch")
    commands = result.get("commands", [])
    expected = [("setup", a) for a in plan.setup] + [("tests", plan.tests)]
    if len(commands) > len(expected):
        raise ValueError("Unexpected executed commands")
    for entry, (phase, argv) in zip(commands, expected, strict=False):
        if any(
            not isinstance(entry.get(k), str) or len(entry[k].encode()) > 262144
            for k in ("stdout", "stderr")
        ):
            raise ValueError("Missing or oversized execution logs")
        if entry["phase"] != phase or entry["argv"] != argv:
            raise ValueError("Executed command differs from approved plan")
        cwd = "/source" if plan.working_directory == "." else "/source/" + plan.working_directory
        if entry.get("working_directory") != cwd:
            raise ValueError("Executed working directory differs from approved plan")
    if status in ("tests_passed", "tests_failed", "environment_preparation_failed"):
        verify_sandbox(result.get("sandbox", {}))
        if result.get("runtime", {}).get("image_id") != plan.image_id or not result.get(
            "container_id"
        ):
            raise ValueError("Missing executed runtime identity")
        if result.get("executed_source_hashes") != candidate["applied_source_hashes"]:
            raise ValueError("Executed source differs from admitted candidate")
    if status in ("tests_passed", "tests_failed"):
        cleanup = result.get("cleanup")
        if not cleanup or any(item.get("confirmed_absent") is not True for item in cleanup):
            raise ValueError("Disposable resource cleanup was not confirmed")
        if len(commands) != len(expected) or not commands:
            raise ValueError("Missing test execution")
        if any(c["status"] != "finished" or c["exit_code"] != 0 for c in commands[:-1]):
            raise ValueError("Dependency preparation did not complete")
        ordinary = result.get("ordinary")
        if (
            ordinary != commands[-1]
            or ordinary["status"] != "finished"
            or ordinary["exit_code"] is None
        ):
            raise ValueError("Missing ordinary process outcome")
        if (ordinary["exit_code"] == 0) != (status == "tests_passed"):
            raise ValueError("Test outcome differs from exit status")
    if not result.get("ended_at") or result.get("duration_ms", -1) < 0:
        raise ValueError("Missing execution timing")
