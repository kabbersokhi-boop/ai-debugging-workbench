"""Actual Docker and browser journeys using deterministic offline synthetic repositories."""

import asyncio
import json
import os
import threading
from pathlib import Path
from uuid import uuid4

import docker
import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_repository_audit import candidate_for, fixture_source, patch_for

from workbench.config import ROOT, settings
from workbench.db import RepositorySource
from workbench.evaluator.runner import LABEL
from workbench.repository_audit.contracts import RUNTIMES, Plan
from workbench.repository_audit.execution import evaluate, validate
from workbench.repository_audit.intake import summary

pytestmark = pytest.mark.integration
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
FOLDER = ROOT / "artifacts/repository-audit"


def actual_plan(source, candidate, runtime="python312", **overrides):
    client = docker.from_env()
    try:
        image_id = client.images.get(RUNTIMES[runtime]).id
        assert image_id
    finally:
        client.close()
    values = {
        "snapshot_id": source["id"],
        "candidate_hash": candidate["candidate_hash"],
        "runtime": runtime,
        "image_id": image_id,
        "tests": ["python", "-m", "pytest", "-q"]
        if runtime == "python312"
        else ["node", "--test", "test.js"],
        "test_description": "Offline synthetic repository existing tests",
        **overrides,
    }
    return Plan.model_validate(values).model_dump()


def execute_fixture(runtime="python312", **overrides):
    source = fixture_source(runtime)
    candidate = candidate_for(source)
    audit_id = uuid4()
    plan = actual_plan(source, candidate, runtime, **overrides)
    result = evaluate(audit_id, source, candidate, plan, threading.Event())
    validate(result, audit_id, source, candidate, plan)
    return result


@pytest.mark.parametrize("runtime", ["python312", "node22"])
def test_generalized_actual_sandbox_python_node_and_unknown_counts(runtime):
    result = execute_fixture(runtime)
    assert result["status"] == "tests_passed", result
    assert result["ordinary"]["exit_code"] == 0
    assert result["ordinary"]["counts"] is None
    assert result["independent"]["status"] == "not_configured"
    sandbox = result["sandbox"]
    config = sandbox["host_config"]
    assert sandbox["user"] == "1000:1000"
    assert config["NetworkMode"] == "none" and config["ReadonlyRootfs"]
    assert config["Memory"] == 536870912 and config["MemorySwap"] == 536870912
    assert config["NanoCpus"] == 1000000000 and config["PidsLimit"] == 64
    assert config["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in config["SecurityOpt"]
    assert all(m["Type"] != "bind" for m in sandbox["mounts"])
    assert any(m["Destination"] == "/source" and not m["RW"] for m in sandbox["mounts"])


def test_actual_sandbox_no_network_credentials_host_or_source_writes():
    expression = (
        "import os,socket; assert os.getuid()==1000; "
        "assert 'NVIDIA_API_KEY' not in os.environ; assert 'DATABASE_URL' not in os.environ; "
        "assert not os.path.exists('/var/run/docker.sock'); s=socket.socket(); s.settimeout(.2); "
        "assert s.connect_ex(('1.1.1.1',443))!=0; "
        "print('no credentials, socket or external network')"
    )
    result = execute_fixture(tests=["python", "-c", expression])
    assert result["status"] == "tests_passed", result
    result = execute_fixture(tests=["python", "-c", "open('/source/library.py','w')"])
    assert (
        result["status"] == "tests_failed"
        and "Read-only file system" in result["ordinary"]["stderr"]
    )


def test_actual_setup_failure_timeout_cancel_and_cleanup():
    result = execute_fixture(
        setup=[
            [
                "pip",
                "install",
                "--no-index",
                "--target",
                "/work/deps",
                "patch-audit-missing-dependency==0",
            ]
        ]
    )
    assert result["status"] == "environment_preparation_failed", result
    assert len(result["commands"]) == 1 and result["ordinary"]["status"] == "not_run"
    result = execute_fixture(
        tests=["python", "-c", "import time; time.sleep(10)"], timeout_seconds=1
    )
    assert result["status"] == "timeout", result
    source = fixture_source()
    candidate = candidate_for(source)
    plan = actual_plan(source, candidate, tests=["python", "-c", "import time; time.sleep(10)"])
    cancel = threading.Event()
    timer = threading.Timer(0.5, cancel.set)
    timer.start()
    try:
        result = evaluate(uuid4(), source, candidate, plan, cancel)
    finally:
        timer.cancel()
    assert result["status"] == "cancelled", result
    client = docker.from_env()
    try:
        assert not client.containers.list(all=True, filters={"label": LABEL})
        assert not client.volumes.list(filters={"label": LABEL})
    finally:
        client.close()


async def test_repository_browser_review_approval_download_reopen_and_stale_selection():
    """Fetch transport is an offline fixture; subsequent API/DB/broker/Docker execution is real."""
    source = fixture_source()
    db = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(db).begin() as session:
            if await session.get(RepositorySource, source["id"]) is None:
                session.add(RepositorySource(id=source["id"], record=source))
    finally:
        await db.dispose()
    await asyncio.to_thread(FOLDER.mkdir, parents=True, exist_ok=True)
    async with async_playwright() as p, httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        runtime_requested = asyncio.Event()
        release_runtime = asyncio.Event()

        async def delayed_runtime(route):
            response = await route.fetch()
            runtime_requested.set()
            await release_runtime.wait()
            await route.fulfill(response=response)

        await page.route("**/api/repository-audits/runtimes", delayed_runtime)
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.goto(BASE + "/?source=external")
        await expect(page.get_by_role("heading", name="Bring your own repository")).to_be_visible()
        await page.get_by_label("GitHub owner/repository", exact=True).fill(source["repository"])
        await page.get_by_label("Immutable base commit", exact=True).fill(source["base_commit"])
        await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        await page.get_by_label("Approved production file scope", exact=True).select_option(
            ["library.py"]
        )
        exact_patch = patch_for(source)
        await page.get_by_label("External patch file", exact=True).set_input_files(
            {
                "name": "bom.patch",
                "mimeType": "text/plain",
                "buffer": b"\xef\xbb\xbf" + exact_patch.encode(),
            }
        )
        await expect(page.get_by_label("External unified diff", exact=True)).to_have_value(
            "\ufeff" + exact_patch
        )
        await page.get_by_label("External unified diff", exact=True).fill(exact_patch)
        await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        await expect(page.get_by_role("region", name="External candidate review")).to_be_visible()
        assert await page.get_by_role("region", name="External audit result").count() == 0
        await page.get_by_text("Compare library.py", exact=True).click()
        await expect(page.locator(".monaco-diff-editor:visible")).to_be_visible(timeout=20000)
        prepare = page.get_by_role("button", name="Prepare exact plan for approval", exact=True)
        await asyncio.wait_for(runtime_requested.wait(), 15)
        await expect(prepare).to_be_disabled()
        release_runtime.set()
        await expect(prepare).to_be_enabled()
        await prepare.click()
        run = page.get_by_role("button", name="Run approved repository tests", exact=True)
        await expect(run).to_be_disabled()
        await page.get_by_role(
            "checkbox",
            name="I reviewed this exact source, patch and plan, and approve local execution.",
            exact=True,
        ).check()
        async with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/api/repository-audits/runs")
        ) as response:
            await run.click()
        audit_id = (await (await response.value).json())["id"]
        region = page.get_by_role("region", name="External audit result")
        await expect(region.get_by_role("status")).to_have_text("tests passed", timeout=60000)
        await expect(region).to_contain_text("Not configured")
        async with page.expect_download() as download:
            await region.get_by_role("link", name="Download repository evidence").click()
        downloaded = json.loads(
            await asyncio.to_thread(Path(await (await download.value).path()).read_text)
        )
        fetched = (await client.get("/api/repository-audits/runs/" + audit_id)).json()
        assert fetched == downloaded
        assert fetched["evidence"]["result"]["ordinary"]["exit_code"] == 0
        await region.screenshot(path=FOLDER / "offline-browser.png")
        await page.reload()
        await expect(region.get_by_role("status")).to_have_text("tests passed", timeout=15000)
        await page.get_by_label("GitHub owner/repository", exact=True).fill("other/project")
        await expect(region).to_have_count(0)
        await expect(page.get_by_role("region", name="External candidate review")).to_have_count(0)
        assert not errors, errors
        await browser.close()


async def test_repository_cancel_and_restart_reconcile_completed_without_reexecution():
    from sqlalchemy import select

    from workbench.db import RepositoryAudit

    source = fixture_source()
    local_engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(local_engine, expire_on_commit=False)
    try:
        async with session_factory.begin() as session:
            if await session.get(RepositorySource, source["id"]) is None:
                session.add(RepositorySource(id=source["id"], record=source))
        async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:

            async def post(route, value):
                response = await client.post("/api/repository-audits/" + route, json=value)
                response.raise_for_status()
                return response.json()

            c = await post(
                "candidates",
                {
                    "snapshot_id": source["id"],
                    "patch": patch_for(source),
                    "approved_paths": ["library.py"],
                },
            )
            plan = actual_plan(source, c, tests=["python", "-c", "import time; time.sleep(8)"])
            p = await post("plans", plan)
            run = await post(
                "runs",
                {
                    "candidate_id": c["id"],
                    "plan_id": p["id"],
                    "approve_exact_plan": True,
                    "confirm_local_execution": True,
                },
            )
            assert (
                await client.post("/api/repository-audits/runs/" + run["id"] + "/cancel")
            ).status_code == 200
            async with asyncio.timeout(30):
                while True:
                    cancelled = (
                        await client.get("/api/repository-audits/runs/" + run["id"])
                    ).json()
                    if cancelled["status"] != "running":
                        break
                    await asyncio.sleep(0.2)
            assert cancelled["status"] == "cancelled", cancelled
            completed_id = uuid4()
            missing_id = uuid4()
            # Produce a real completed result, then simulate losing only its DB terminal update.
            p = await post("plans", actual_plan(source, c))
            started = await post(
                "runs",
                {
                    "candidate_id": c["id"],
                    "plan_id": p["id"],
                    "approve_exact_plan": True,
                    "confirm_local_execution": True,
                },
            )
            completed_id = started["id"]
            async with asyncio.timeout(45):
                while True:
                    completed = (
                        await client.get("/api/repository-audits/runs/" + completed_id)
                    ).json()
                    if completed["status"] != "running":
                        break
                    await asyncio.sleep(0.2)
            assert completed["status"] == "tests_passed", completed
            from uuid import UUID

            async with session_factory.begin() as session:
                row = await session.scalar(
                    select(RepositoryAudit).where(RepositoryAudit.id == UUID(completed_id))
                )
                assert row
                evidence = {
                    k: v for k, v in row.evidence.items() if k not in ("result", "result_hash")
                }
                row.status = "running"
                row.evidence = evidence
                session.add(
                    RepositoryAudit(
                        id=missing_id,
                        candidate_id=row.candidate_id,
                        plan_id=row.plan_id,
                        status="running",
                        evidence=evidence,
                    )
                )
            process = await asyncio.create_subprocess_exec(
                "docker",
                "compose",
                "restart",
                "api",
                cwd=ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await process.communicate()
            assert process.returncode == 0, output
            async with asyncio.timeout(90):
                while True:
                    try:
                        response = await client.get("/api/repository-audits/runs/" + completed_id)
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.4)
            restored = response.json()
            assert restored["status"] == "tests_passed"
            assert restored["evidence"] == completed["evidence"]
            missing = (await client.get("/api/repository-audits/runs/" + str(missing_id))).json()
            assert missing["status"] == "interrupted" and "result" not in missing["evidence"]
            await asyncio.to_thread(FOLDER.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(
                (FOLDER / "recovery.json").write_text,
                json.dumps(
                    {
                        "cancelled": run["id"],
                        "restored": completed_id,
                        "missing_terminal": str(missing_id),
                        "restored_without_reexecution": True,
                    },
                    indent=2,
                )
                + "\n",
            )
    finally:
        await local_engine.dispose()
