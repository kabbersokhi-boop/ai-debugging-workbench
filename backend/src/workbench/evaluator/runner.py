"""Docker-only task adapter. No code executes in the API/coordinator process."""

import io
import json
import tarfile
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import docker
from docker.types import LogConfig, Ulimit

from workbench.evaluator import behavior
from workbench.evaluator.catalog import digest, identity

IMAGE = "ai-agent-evaluator:python312-v1"
LABEL = "ai-debugging-workbench.evaluator"
POLICY = {
    "version": "python312-v1",
    "network": "none",
    "rootfs": "read-only",
    "source": "read-only named volume",
    "uid": 1000,
    "cpu": 1,
    "memory_bytes": 268435456,
    "pids": 32,
    "tmp_bytes": 33554432,
    "log_bytes": 131072,
    "timeout_seconds": 25,
    "capabilities": [],
    "host_mounts": [],
    "credentials": False,
    "docker_socket": False,
}


def verifier_id(task_id: str) -> str:
    return identity(
        {
            "probe": behavior.probe(task_id),
            "expected": behavior.expected(task_id),
            "engine": digest(__file_source()),
            "policy": POLICY,
        }
    )


def __file_source() -> str:
    from pathlib import Path

    folder = Path(__file__).parent
    return "".join(
        (folder / name).read_text()
        for name in ("runner.py", "behavior.py", "catalog.py", "service.py")
    )


def cleanup_all() -> None:
    """On coordinator restart, reap only this adapter's labeled disposable resources."""
    client = docker.from_env()
    try:
        for container in client.containers.list(all=True, filters={"label": LABEL}):
            container.remove(force=True)
        for volume in client.volumes.list(filters={"label": LABEL}):
            volume.remove(force=True)
    finally:
        client.close()


def execute(
    files: dict[str, str],
    command: list[str],
    image_id: str,
    cancel: threading.Event,
    timeout: float = 25,
) -> dict[str, Any]:
    client = docker.from_env()
    key = str(uuid4())
    labels = {LABEL: key}
    volume = init = container = None
    started = time.monotonic()
    record: dict[str, Any] = {
        "command": command,
        "image_id": image_id,
        "policy": POLICY,
        "started_at": datetime.now(UTC).isoformat(),
        "resource_usage": {
            "cpu_ns": None,
            "peak_memory_bytes_observed": None,
            "note": "Fast processes may exit before a Docker stats sample is available",
        },
    }
    try:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            for path, content in files.items():
                data = content.encode()
                info = tarfile.TarInfo(path)
                info.size, info.mode, info.uid, info.gid = len(data), 0o444, 0, 0
                archive.addfile(info, io.BytesIO(data))
        if payload.tell() > 2_000_000:
            raise ValueError("Approved source budget exceeded")
        volume = client.volumes.create(labels=labels)
        common: dict[str, Any] = dict(
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit="256m",
            memswap_limit="256m",
            nano_cpus=1_000_000_000,
            pids_limit=32,
            labels=labels,
            log_config=LogConfig(type="json-file", config={"max-size": "128k", "max-file": "1"}),
        )
        # Trusted initialization only; generated source is never imported by this process.
        init = client.containers.create(
            image_id,
            command=["sleep", "30"],
            user="0:0",
            volumes={volume.name: {"bind": "/source", "mode": "rw"}},
            **common,
        )
        init.start()
        if not init.put_archive("/source", payload.getvalue()):
            raise RuntimeError("Source initialization failed")
        stream, _ = init.get_archive("/source")
        observed = {}
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    source = archive.extractfile(member)
                    assert source is not None
                    observed[member.name.removeprefix("source/")] = digest(source.read())
        if observed != {p: digest(v) for p, v in files.items()}:
            raise ValueError("Actual initialized source differs from admitted candidate")
        record["executed_file_hashes"] = observed
        init.remove(force=True)
        init = None
        container = client.containers.create(
            image_id,
            command=command,
            user="1000:1000",
            working_dir="/source",
            environment={
                "HOME": "/tmp",
                "LANG": "C.UTF-8",
                "TZ": "UTC",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                "PYTHONPATH": "/source",
            },
            volumes={volume.name: {"bind": "/source", "mode": "ro"}},
            tmpfs={"/tmp": "rw,nosuid,nodev,noexec,size=32m,mode=1777"},
            ulimits=[
                Ulimit(name="fsize", soft=1048576, hard=1048576),
                Ulimit(name="nofile", soft=128, hard=128),
            ],
            **common,
        )
        record["container_id"] = container.id
        container.start()
        while True:
            container.reload()
            if container.status in ("exited", "dead"):
                break
            if cancel.is_set():
                record["status"] = "cancelled"
                container.kill()
                break
            if time.monotonic() - started >= timeout:
                record["status"] = "timeout"
                container.kill()
                break
            stats: Any = container.stats(stream=False, one_shot=True)
            cpu = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage")
            memory = stats.get("memory_stats", {}).get("usage")
            if cpu:
                record["resource_usage"]["cpu_ns"] = cpu
            if memory:
                previous = record["resource_usage"]["peak_memory_bytes_observed"] or 0
                record["resource_usage"]["peak_memory_bytes_observed"] = max(previous, memory)
            time.sleep(0.1)
        container.reload()
        record.update(
            exit_code=container.attrs["State"].get("ExitCode"),
            oom_killed=container.attrs["State"].get("OOMKilled", False),
        )
        record["stdout"] = container.logs(stdout=True, stderr=False).decode(errors="replace")[
            -65536:
        ]
        record["stderr"] = container.logs(stdout=False, stderr=True).decode(errors="replace")[
            -65536:
        ]
        record.setdefault("status", "finished")
        if record["oom_killed"]:
            record["status"] = "infrastructure_error"
        return record
    finally:
        record["ended_at"] = datetime.now(UTC).isoformat()
        record["duration_ms"] = round((time.monotonic() - started) * 1000)
        try:
            if container is not None:
                container.remove(force=True)
            if init is not None:
                init.remove(force=True)
        finally:
            if volume is not None:
                volume.remove(force=True)
            client.close()


def evaluate(spec: dict[str, Any], candidate: dict[str, Any], cancel: threading.Event):
    client = docker.from_env()
    try:
        image = client.images.get(IMAGE)
        image_id = image.id
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
        "policy_hash": identity(POLICY),
        "executed_file_hashes": candidate["source_hashes"],
    }
    result: dict[str, Any] = {
        "binding": binding,
        "binding_hash": identity(binding),
        "ordinary": None,
        "independent": None,
    }
    ordinary = execute(candidate["files"], spec["ordinary"], image_id, cancel)
    result["ordinary"] = ordinary
    if ordinary["status"] != "finished":
        result["status"] = ordinary["status"]
        return result
    # pytest usage/startup/collection and no-tests outcomes are never code failures or passes.
    if ordinary["exit_code"] not in (0, 1):
        result.update(status="infrastructure_error", reason="Ordinary checks did not complete")
        return result
    if "ModuleNotFoundError" in ordinary["stdout"] + ordinary["stderr"]:
        result.update(
            status="infrastructure_error", reason="Approved environment lacks a dependency"
        )
        return result
    ordinary["outcome"] = "passed" if ordinary["exit_code"] == 0 else "failed"
    # Only production source enters this phase. No tests, expected answers or scoring code.
    sources = {p: v for p, v in candidate["files"].items() if not p.startswith("tests/")}
    independent = execute(
        sources, ["python", "-I", "-B", "-c", behavior.probe(spec["id"])], image_id, cancel
    )
    result["independent"] = independent
    if independent["status"] != "finished":
        result["status"] = independent["status"]
    elif independent["exit_code"] != 0:
        result.update(
            status="failed", reason="Candidate raised an exception during behavioral checks"
        )
        independent["outcome"] = "failed"
    else:
        try:
            independent["checks"] = behavior.compare(spec["id"], independent["stdout"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            result.update(status="invalid_candidate", reason="Malformed or missing observations")
            return result
        independent["outcome"] = (
            "passed" if all(c["status"] == "passed" for c in independent["checks"]) else "failed"
        )
        result["status"] = (
            "passed" if (ordinary["outcome"] == independent["outcome"] == "passed") else "failed"
        )
        result["reason"] = "Behavioral observations compared outside the candidate container"
    return result
