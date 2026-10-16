"""Trusted Docker boundary. No model, DB or provider credentials; never accepts commands."""

import asyncio
import json
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import docker
import httpx
import uvicorn
from docker.errors import APIError
from docker.types import LogConfig
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from playwright.async_api import async_playwright
from pydantic import Field

from workbench.rag.contracts import StrictModel
from workbench.rag.snapshot import load_snapshot
from workbench.repair.contracts import PatchProposal, apply_patch, sha256
from workbench.repair.verifier import VERIFIER_VERSION, verify

ROOT = Path(os.environ.get("REPAIR_ARTIFACT_DIR", "/tmp/workbench-repairs"))
IMAGE = "ai-debugging-candidate:milestone-03"
LABEL = "ai-debugging-workbench.repair"
CONTROL_IP = socket.gethostbyname(os.environ.get("REPAIR_CONTROL_HOST", socket.gethostname()))
LOCK = asyncio.Lock()
LIVE: dict[str, dict[str, Any]] = {}
TASKS: dict[str, asyncio.Task] = {}


class CreateCandidate(StrictModel):
    repair_id: UUID
    attempt: int = Field(ge=1, le=2)
    patch: PatchProposal


def directory(repair_id: UUID, attempt: int) -> Path:
    if attempt not in (1, 2):
        raise HTTPException(404, "Unknown attempt")
    return ROOT / str(repair_id) / str(attempt)


def saved(repair_id: UUID, attempt: int) -> dict[str, Any]:
    path = directory(repair_id, attempt) / "candidate.json"
    if not path.is_file():
        raise HTTPException(404, "Candidate not found")
    return json.loads(path.read_text())


def cleanup_sync(key: str) -> None:
    client = docker.from_env()
    try:
        for container in client.containers.list(all=True, filters={"label": f"{LABEL}={key}"}):
            container.remove(force=True)
        for network in client.networks.list(filters={"label": f"{LABEL}={key}"}):
            try:
                network.disconnect(os.environ.get("HOSTNAME", ""), force=True)
            except APIError:
                pass
            network.remove()
        for volume in client.volumes.list(filters={"label": f"{LABEL}={key}"}):
            volume.remove(force=True)
    finally:
        client.close()


async def cleanup(key: str) -> None:
    LIVE.pop(key, None)
    await asyncio.to_thread(cleanup_sync, key)


def create_sync(key: str, files: dict[str, str]) -> dict[str, Any]:
    client = docker.from_env()
    labels = {LABEL: key}
    try:
        network = client.networks.create(f"wb-candidate-{key}", internal=True, labels=labels)
        volume = client.volumes.create(f"wb-candidate-{key}", labels=labels)
        # An initialized volume becomes read-only before any generated JS is executed.
        init = client.containers.create(
            IMAGE,
            command=["init"],
            environment={"SOURCE_FILES": json.dumps(files)},
            user="0:0",
            volumes={volume.name: {"bind": "/site", "mode": "rw"}},
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit="96m",
            pids_limit=32,
            labels=labels,
        )
        try:
            init.start()
            result = init.wait(timeout=15)
            if result["StatusCode"] != 0:
                raise RuntimeError("Candidate initialization failed")
        finally:
            init.remove(force=True)
        container = client.containers.create(
            IMAGE,
            environment={"HOME": "/tmp", "XDG_CONFIG_HOME": "/tmp/config"},
            network=network.name,
            read_only=True,
            user="1000:1000",
            volumes={volume.name: {"bind": "/site", "mode": "ro"}},
            tmpfs={"/tmp": "rw,nosuid,nodev,noexec,size=256m,mode=1777"},
            shm_size="256m",
            mem_limit="1g",
            nano_cpus=1_000_000_000,
            pids_limit=192,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            labels=labels,
            log_config=LogConfig(type="none"),
        )
        # Control HTTP binds only to the original management address, not this interface.
        broker_id = os.environ.get("HOSTNAME", "")
        network.connect(broker_id)
        container.start()
        container.reload()
        ip = container.attrs["NetworkSettings"]["Networks"][network.name]["IPAddress"]
        image = container.image
        if image is None:
            raise RuntimeError("Candidate image identity unavailable")
        return {
            "container_id": container.id,
            "image_id": image.id,
            "network_id": network.id,
            "ip": ip,
            "created_monotonic": time.monotonic(),
            "isolation": {
                "internal_network": True,
                "read_only": True,
                "source_mount": "ro",
                "memory_bytes": 1073741824,
                "cpu_cores": 1,
                "pids": 192,
                "capabilities": [],
                "secrets": False,
                "docker_socket": False,
            },
        }
    except BaseException:
        cleanup_sync(key)
        raise
    finally:
        client.close()


async def ensure(repair_id: UUID, attempt: int) -> dict[str, Any]:
    key = f"{repair_id}-{attempt}"
    async with LOCK:
        if key in LIVE:
            return LIVE[key]
        if len(LIVE) >= 3:
            idle = [key for key in LIVE if key not in TASKS]
            if not idle:
                raise HTTPException(429, "Candidate capacity is occupied by verification")
            oldest = min(idle, key=lambda k: LIVE[k]["created_monotonic"])
            await cleanup(oldest)
        candidate = saved(repair_id, attempt)
        snapshot = load_snapshot()
        # Revalidate retained proposal/hash before reconstruction; never use latest working files.
        validated = apply_patch(snapshot, PatchProposal.model_validate(candidate["proposal"]))
        if validated["candidate_hash"] != candidate["candidate_hash"]:
            raise HTTPException(409, "Retained candidate hash does not match its proposal")
        files = {
            Path(f.path).name: f.content
            for f in snapshot.files
            if f.path.endswith((".html", ".css", ".js"))
        }
        files["cart.js"] = validated["content"]
        creation = asyncio.create_task(asyncio.to_thread(create_sync, key, files))
        try:
            instance = await asyncio.shield(creation)
        except asyncio.CancelledError:
            await creation
            await cleanup(key)
            raise
        LIVE[key] = instance
    async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
        for _ in range(50):
            try:
                response = await client.get(f"http://{instance['ip']}:9223/json/version")
                if response.status_code == 200:
                    return instance
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.15)
    await cleanup(key)
    raise HTTPException(503, "Candidate browser did not become ready")


async def inspect_executed_files(
    instance: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, str]:
    """Hash bytes served from the actual immutable candidate volume, outside its browser."""
    snapshot = load_snapshot()
    hashes = {}
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        for source in snapshot.files:
            name = Path(source.path).name
            if name not in ("index.html", "styles.css", "cart.js"):
                continue
            path = "" if name == "index.html" else name
            response = await client.get(f"http://{instance['ip']}:8080/retail/{path}")
            response.raise_for_status()
            expected = candidate["content"] if name == "cart.js" else source.content
            if response.content != expected.encode():
                raise ValueError("Actual candidate file bytes differ from the approved manifest")
            hashes[source.path] = sha256(expected)
    return hashes


async def reap() -> None:
    while True:
        await asyncio.sleep(30)
        for key, value in list(LIVE.items()):
            if time.monotonic() - value["created_monotonic"] > 600 and key not in TASKS:
                await cleanup(key)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(ROOT.mkdir, parents=True, exist_ok=True)
    # A broker restart discards running environments. Saved immutable bytes/evidence remain.
    client = docker.from_env()
    try:
        keys = {c.labels[LABEL] for c in client.containers.list(all=True, filters={"label": LABEL})}
    finally:
        client.close()
    for key in keys:
        await cleanup(key)
    reaper = asyncio.create_task(reap())
    try:
        yield
    finally:
        reaper.cancel()
        await asyncio.gather(reaper, return_exceptions=True)
        for task in list(TASKS.values()):
            task.cancel()
        await asyncio.gather(*TASKS.values(), return_exceptions=True)
        for key in list(LIVE):
            await cleanup(key)


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
preview = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {"status": "ok", "active_candidates": len(LIVE), "verifier_version": VERIFIER_VERSION}


@app.post("/original/verify")
async def verify_original():
    folder = ROOT / "original" / VERIFIER_VERSION
    folder.mkdir(parents=True, exist_ok=True)
    retained = folder / "verification.json"
    if await asyncio.to_thread(retained.exists):
        return json.loads(retained.read_text())
    snapshot = load_snapshot()
    key = "original-baseline"
    files = {
        Path(f.path).name: f.content
        for f in snapshot.files
        if f.path.endswith((".html", ".css", ".js"))
    }
    instance = await asyncio.to_thread(create_sync, key, files)
    try:
        async with asyncio.timeout(55), async_playwright() as p:
            # Startup readiness is bounded by Playwright's connection retry.
            await asyncio.sleep(1)
            browser = await p.chromium.connect_over_cdp(
                f"http://{instance['ip']}:9223", timeout=15000
            )
            result = await verify(browser, snapshot.fixture_sha256, folder / "after.png")
        result["source_snapshot"] = snapshot.id
        retained.write_text(json.dumps(result))
        return result
    finally:
        await cleanup(key)


@app.post("/candidates")
async def create(payload: CreateCandidate):
    candidate = apply_patch(load_snapshot(), payload.patch)
    folder = directory(payload.repair_id, payload.attempt)
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / "candidate.json"
    if (
        manifest.exists()
        and json.loads(manifest.read_text())["candidate_hash"] != candidate["candidate_hash"]
    ):
        raise HTTPException(409, "Attempt identities are immutable")
    manifest.write_text(json.dumps(candidate))
    instance = await ensure(payload.repair_id, payload.attempt)
    return {**candidate, "attempt": payload.attempt, "isolation": instance["isolation"]}


@app.post("/candidates/{repair_id}/{attempt}/verify")
async def trusted_verify(repair_id: UUID, attempt: int):
    key = f"{repair_id}-{attempt}"
    candidate = saved(repair_id, attempt)
    folder = directory(repair_id, attempt)
    result_path = folder / f"verification-{VERIFIER_VERSION}.json"
    if result_path.is_file():
        retained = json.loads(result_path.read_text())
        if (
            retained["candidate_hash"] == candidate["candidate_hash"]
            and retained["verifier_version"] == VERIFIER_VERSION
        ):
            return retained
    if key in TASKS:
        raise HTTPException(409, "Verification already active")
    task = asyncio.current_task()
    assert task is not None
    TASKS[key] = task
    try:
        async with asyncio.timeout(55):
            instance = await ensure(repair_id, attempt)
            executed = await inspect_executed_files(instance, candidate)
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://{instance['ip']}:9223")
                result = await verify(
                    browser, candidate["candidate_hash"], folder / f"after-{VERIFIER_VERSION}.png"
                )
                # Disconnect transport on leaving Playwright; no target process may assert success.
            if executed != await inspect_executed_files(instance, candidate):
                raise ValueError("Candidate changed during verification")
            result["executed_file_hashes"] = executed
            result["container_id"] = instance["container_id"]
            result["container_image_id"] = instance["image_id"]
            result_path.write_text(json.dumps(result))
            return result
    except TimeoutError:
        raise HTTPException(504, "Trusted verification timed out; no pass result exists") from None
    finally:
        TASKS.pop(key, None)
        await cleanup(key)


@app.post("/repairs/{repair_id}/cleanup")
async def stop(repair_id: UUID):
    for attempt in (1, 2):
        key = f"{repair_id}-{attempt}"
        task = TASKS.get(key)
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await cleanup(key)
    return {"status": "cleaned", "repair_id": str(repair_id)}


@app.get("/candidates/{repair_id}/{attempt}/reconcile")
async def reconcile(repair_id: UUID, attempt: int):
    key = f"{repair_id}-{attempt}"
    candidate = saved(repair_id, attempt)
    verification = directory(repair_id, attempt) / f"verification-{VERIFIER_VERSION}.json"
    return {
        "candidate_hash": candidate["candidate_hash"],
        "live": key in LIVE,
        "verification": json.loads(verification.read_text()) if verification.is_file() else None,
        "safe_to_resume": False,
    }


@app.post("/candidates/{repair_id}/{attempt}/preview")
async def start_preview(repair_id: UUID, attempt: int):
    await ensure(repair_id, attempt)
    return {
        "path": f"/preview/{repair_id}/{attempt}/retail/",
        "ttl_seconds": 600,
        "candidate_hash": saved(repair_id, attempt)["candidate_hash"],
    }


@app.get("/candidates/{repair_id}/{attempt}/artifacts/{name}")
async def artifact(repair_id: UUID, attempt: int, name: str):
    import re

    folder = directory(repair_id, attempt)
    if name in ("after.png", "verification.json"):
        stem, extension = name.rsplit(".", 1)
        path = folder / f"{stem}-{VERIFIER_VERSION}.{extension}"
        if not path.is_file():
            path = folder / name  # Historical initial-version evidence; never rewritten.
    elif name == "candidate.json" or re.fullmatch(
        r"(?:after|verification)-[a-f0-9]{64}\.(?:png|json)", name
    ):
        path = folder / name
        if not path.is_file() and name.startswith("after-"):
            legacy = folder / "verification.json"
            version = name.removeprefix("after-").removesuffix(".png")
            if legacy.is_file() and json.loads(legacy.read_text())["verifier_version"] == version:
                path = folder / "after.png"
    else:
        raise HTTPException(404, "Unknown evidence")
    if not path.is_file():
        raise HTTPException(404, "Evidence unavailable")
    return FileResponse(path)


@preview.get("/preview/{repair_id}/{attempt}/retail/{name:path}")
async def preview_file(repair_id: UUID, attempt: int, name: str):
    key = f"{repair_id}-{attempt}"
    if name not in ("", "index.html", "cart.js", "styles.css") or key not in LIVE:
        return Response(
            "Preview expired. Use Start / reset candidate preview in the workbench.",
            status_code=410,
        )
    candidate = saved(repair_id, attempt)
    source = next(f for f in load_snapshot().files if Path(f.path).name == (name or "index.html"))
    body = candidate["content"] if name == "cart.js" else source.content
    if name in ("", "index.html"):
        body = body.replace('"/retail/', f'"/preview/{repair_id}/{attempt}/retail/')
    return Response(
        body,
        media_type={"cart.js": "text/javascript", "styles.css": "text/css"}.get(name, "text/html"),
        headers={
            ("Content-Security-Policy"): (
                "sandbox allow-scripts; default-src 'none'; script-src 'self'; "
                "style-src 'self'; connect-src 'none'; img-src 'none'; object-src "
                "'none'; base-uri 'none'; form-action 'none'; frame-ancestors "
                "http://localhost:8010 http://127.0.0.1:8010"
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


async def main() -> None:
    await asyncio.gather(
        uvicorn.Server(
            uvicorn.Config(app, host=CONTROL_IP, port=8012, log_level="warning")
        ).serve(),
        uvicorn.Server(
            uvicorn.Config(preview, host="0.0.0.0", port=8013, log_level="warning")
        ).serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
