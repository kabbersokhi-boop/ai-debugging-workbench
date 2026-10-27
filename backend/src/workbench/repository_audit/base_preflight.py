"""Owner-only unchanged-base compatibility probe. No HTTP routes or behavioral scorer."""

import io
import tarfile
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import docker
from docker.types import LogConfig, Ulimit

from workbench.evaluator.catalog import digest, identity
from workbench.evaluator.runner import LABEL
from workbench.repository_audit.contracts import POLICY, RUNTIMES
from workbench.repository_audit.execution import command, remove_confirmed, verify_sandbox
from workbench.repository_audit.intake import decode_files


def review(snapshot, image_id, tests, capsule):
    decode_files(snapshot)
    return {
        "version": "unchanged-base-preflight-v1",
        "snapshot_id": snapshot["id"],
        "base_commit": snapshot["base_commit"],
        "git_tree": snapshot["git_tree"],
        "source_tree_hash": snapshot["source_tree_hash"],
        "runtime": "node22_compat",
        "image_id": image_id,
        "tests": tests,
        "capsule": capsule,
        "policy_hash": identity(POLICY),
        "timeout_seconds": 45,
    }


def execute(snapshot, plan, approved_plan_id):
    if (
        identity(plan) != approved_plan_id
        or review(snapshot, plan["image_id"], plan["tests"], plan["capsule"]) != plan
    ):
        raise ValueError("Unchanged-base preflight needs approval of its exact source/runtime plan")
    files = decode_files(snapshot)
    result: dict[str, Any] = {
        "version": "unchanged-base-preflight-result-v1",
        "plan": plan,
        "approval": {
            "plan_id": approved_plan_id,
            "approved_at": datetime.now(UTC).isoformat(),
            "actor": "Codex under owner-delegated compatibility task authorization",
        },
        "started_at": datetime.now(UTC).isoformat(),
        "status": "infrastructure_error",
        "commands": [],
    }
    client = docker.from_env(timeout=10)
    volume = init = container = None
    try:
        image = client.images.get(RUNTIMES["node22_compat"])
        assert image.id is not None
        if image.id != plan["image_id"]:
            raise ValueError("Preflight runtime changed")
        labels = {LABEL: "repository-preflight-" + str(uuid4())}
        common: dict[str, Any] = dict(
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=POLICY["memory_bytes"],
            memswap_limit=POLICY["memory_bytes"],
            nano_cpus=1_000_000_000,
            pids_limit=64,
            labels=labels,
            log_config=LogConfig(type="none"),
            use_config_proxy=False,
            shm_size="8m",
            ulimits=[
                Ulimit(name="fsize", soft=16777216, hard=16777216),
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
            for name, data in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o555 if snapshot["modes"][name] == "100755" else 0o444
                archive.addfile(member, io.BytesIO(data))
        init.start()
        if not init.put_archive("/source", archive_bytes.getvalue()):
            raise ValueError("Could not initialize preflight source")
        observed = {}
        stream, _ = init.get_archive("/source")
        with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as archive:
            for member in archive:
                if member.isfile():
                    reader = archive.extractfile(member)
                    assert reader is not None
                    observed[member.name.removeprefix("source/")] = digest(reader.read())
        if observed != snapshot["file_hashes"]:
            raise ValueError("Preflight source differs from unchanged historical base")
        result["executed_source_hashes"] = observed
        if not remove_confirmed(client, init, "containers"):
            raise ValueError("Initializer cleanup unconfirmed")
        result["initializer_id"] = init.id
        init = None
        container = client.containers.create(
            image.id,
            ["sleep", "180"],
            user="1000:1000",
            working_dir="/work",
            environment={
                "HOME": "/tmp",
                "NODE_PATH": "/opt/test-tools/node_modules",
                "TZ": "UTC",
                "npm_config_offline": "true",
            },
            volumes={volume.name: {"bind": "/source", "mode": "ro"}},
            tmpfs={
                "/work": "rw,nosuid,nodev,size=128m,mode=1777",
                "/tmp": "rw,nosuid,nodev,size=8m,mode=1777",
            },
            **common,
        )
        container.start()
        container.reload()
        result["container_id"] = container.id
        result["sandbox"] = {
            "user": container.attrs["Config"]["User"],
            "host_config": container.attrs["HostConfig"],
            "mounts": [
                {k: m.get(k) for k in ("Type", "Name", "Destination", "RW")}
                for m in container.attrs["Mounts"]
            ],
        }
        verify_sandbox(result["sandbox"])
        deadline, cancel = time.monotonic() + 45, threading.Event()
        # Trusted verifier only reads capsule bytes; target package code runs only in this sandbox.
        check = command(
            client, container, ["node", "/opt/node-compat/verify.cjs"], "/source", cancel, deadline
        )
        result["commands"].append({"phase": "capsule_validation", **check})
        if check["status"] != "finished" or check["exit_code"] != 0:
            raise ValueError("Pinned dependency capsule failed validation")
        manifest = container.exec_run(["cat", "/opt/node-compat/manifest.json"], user="1000:1000")
        import json

        if (
            manifest.exit_code != 0
            or not isinstance(manifest.output, bytes)
            or json.loads(manifest.output) != plan["capsule"]
        ):
            raise ValueError("Image capsule differs from the approved dependency manifest")
        outcome = command(client, container, plan["tests"], "/source", cancel, deadline)
        result["commands"].append({"phase": "unchanged_ordinary_tests", **outcome})
        result["status"] = (
            "tests_passed"
            if outcome["status"] == "finished" and outcome["exit_code"] == 0
            else "preflight_failed"
        )
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)[:300]
    finally:
        cleanup = []
        for kind, resource in (
            ("containers", container),
            ("containers", init),
            ("volumes", volume),
        ):
            if resource is not None:
                try:
                    absent = remove_confirmed(client, resource, kind)
                except Exception:
                    absent = False
                cleanup.append(
                    {
                        "kind": kind,
                        "id": resource.name if kind == "volumes" else resource.id,
                        "confirmed_absent": absent,
                    }
                )
        result["cleanup"] = cleanup
        if any(not c["confirmed_absent"] for c in cleanup):
            result["status"] = "infrastructure_error"
        result["ended_at"] = datetime.now(UTC).isoformat()
        client.close()
    return result
