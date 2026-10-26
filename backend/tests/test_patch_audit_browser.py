"""Real local import/execution and recorded browser journeys. No inference."""

import asyncio
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench.config import ROOT, settings
from workbench.db import PatchAudit, PatchCandidate
from workbench.patch_audit.curated import FAIL, PASS, examples
from workbench.patch_audit.execution import verifier_id

pytestmark = pytest.mark.e2e
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
FOLDER = ROOT / "artifacts/patch-audit"


async def wait_audit(client, audit_id):
    async with asyncio.timeout(90):
        while True:
            r = await client.get("/api/patch-audits/runs/" + audit_id)
            r.raise_for_status()
            value = r.json()
            if value["status"] != "running":
                return value
            await asyncio.sleep(0.3)


async def test_patch_audit_real_ui_import_failing_passing_download_and_reopen(tmp_path):
    FOLDER.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p, httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for key, outcome in ((FAIL, "failed"), (PASS, "passed")):
            await page.goto(BASE)
            await expect(
                page.get_by_role("heading", name="Patch Audit", exact=True)
            ).to_be_visible()
            await expect(page.get_by_role("region", name="Candidate review")).to_be_visible()
            before = (await client.get("/api/patch-audits/runs")).json()
            await page.get_by_text(
                "Import a completed patch · review before execution", exact=True
            ).click()
            patch = examples()[key]["candidate"]["patch"]
            if key == FAIL:
                path = tmp_path / "genuine-missed.patch"
                path.write_text(patch)
                await page.get_by_label("Plain-text patch file", exact=True).set_input_files(path)
                await expect(page.get_by_label("Unified diff", exact=True)).to_have_value(patch)
            else:
                await page.get_by_label("Unified diff", exact=True).fill(patch)
            await page.get_by_label("Declared authorship").select_option("user_declared")
            await page.get_by_label("Optional producer label", exact=True).fill(
                "Reviewer import of retained "
                + ("incomplete" if key == FAIL else "complete")
                + " patch"
            )
            await page.get_by_label("Optional model or tool", exact=True).fill(
                "NVIDIA model / declared import"
            )
            async with page.expect_response(
                lambda r: (
                    r.request.method == "POST" and r.url.endswith("/api/patch-audits/candidates")
                )
            ) as response:
                await page.get_by_role("button", name="Import for review", exact=True).click()
            imported = await (await response.value).json()
            assert imported["candidate_hash"] == examples()[key]["candidate"]["candidate_hash"]
            await expect(page.get_by_role("region", name="Candidate review")).to_contain_text(
                "user-declared provenance (unverified)"
            )
            assert len((await client.get("/api/patch-audits/runs")).json()) == len(before)
            button = page.get_by_role("button", name="Run fresh audit", exact=True)
            await expect(button).to_be_disabled()
            await page.get_by_text(
                "Open code comparison · boltons/dictutils.py", exact=True
            ).click()
            await expect(page.locator(".monaco-diff-editor:visible")).to_be_visible(timeout=20000)
            await page.get_by_role("checkbox").check()
            async with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.endswith("/api/patch-audits/runs")
            ) as started:
                await button.click()
            audit_id = (await (await started.value).json())["id"]
            region = page.get_by_role("region", name="Patch audit result")
            await expect(region.get_by_role("status")).to_have_text(outcome, timeout=90000)
            await expect(
                region.get_by_text("Ordinary repository checks", exact=True)
            ).to_be_visible()
            saved = await wait_audit(client, audit_id)
            result = saved["evidence"]["envelope"]["result"]
            assert result["ordinary"]["outcome"] == "passed"
            assert "155 passed" in result["ordinary"]["stdout"]
            assert result["independent"]["outcome"] == outcome
            assert result["binding"]["candidate_hash"] == imported["candidate_hash"]
            assert result["ordinary"]["container_id"] != result["independent"]["container_id"]
            if key == FAIL:
                await expect(region).to_contain_text(
                    "length one while its keys and items are empty"
                )
                await expect(region).to_contain_text("boltons/urlutils.py")
                await expect(region.locator(".evaluation-observations")).not_to_have_attribute(
                    "open", ""
                )
            else:
                await expect(region).to_contain_text(
                    "Passed the declared checks for this task and environment."
                )
            await region.screenshot(
                path=FOLDER / ("fresh-missed.png" if key == FAIL else "fresh-complete.png")
            )
            async with page.expect_download() as download:
                await page.get_by_role("link", name="Download audit evidence", exact=True).click()
            downloaded = json.loads(
                await asyncio.to_thread(Path(await (await download.value).path()).read_text)
            )
            assert downloaded == saved
            (FOLDER / ("fresh-missed.json" if key == FAIL else "fresh-complete.json")).write_text(
                json.dumps(saved, indent=2) + "\n"
            )
            await page.reload()
            await expect(
                page.get_by_role("region", name="Patch audit result").get_by_role("status")
            ).to_have_text(outcome, timeout=15000)
            assert (await client.get("/api/patch-audits/runs/" + audit_id)).json() == saved
            await expect(page.get_by_role("heading", name="Saved audit history")).to_be_visible()
        assert not errors, errors
        await browser.close()


@pytest.fixture
async def audit_db():
    local_engine = create_async_engine(settings.database_url)
    try:
        yield async_sessionmaker(local_engine, expire_on_commit=False)
    finally:
        await local_engine.dispose()


async def test_patch_audit_rejections_identity_cancel_additional_tasks_and_restart(audit_db):
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        for bad in (
            "not a diff",
            examples()[FAIL]["candidate"]["patch"].replace("Called ``addlist``", "stale source", 1),
        ):
            r = await client.post(
                "/api/patch-audits/candidates", json={"task_id": "boltons-addlist", "patch": bad}
            )
            assert r.status_code == 422
        oversized = await client.post(
            "/api/patch-audits/candidates",
            content=b" " * 450001,
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        c = (await client.get("/api/patch-audits/examples/" + PASS)).json()
        assert (await client.get("/api/patch-audits/candidates/" + c["id"])).json() == c
        imported_payload = {"task_id": "boltons-addlist", "patch": c["patch"]}
        first = (await client.post("/api/patch-audits/candidates", json=imported_payload)).json()
        duplicate = (
            await client.post("/api/patch-audits/candidates", json=imported_payload)
        ).json()
        other = (
            await client.post(
                "/api/patch-audits/candidates", json=imported_payload | {"producer": "user label"}
            )
        ).json()
        assert first == duplicate and first["id"] != other["id"]
        assert first["candidate_hash"] == other["candidate_hash"] == c["candidate_hash"]
        with pytest.raises(DBAPIError, match="immutable"):
            async with audit_db.begin() as session:
                await session.execute(
                    update(PatchCandidate).where(PatchCandidate.id == first["id"]).values(record={})
                )
        assert (await client.get("/api/patch-audits/candidates/" + first["id"])).json() == first

        payload = {
            "candidate_id": c["id"],
            "candidate_hash": c["candidate_hash"],
            "record_hash": c["record_hash"],
            "confirm_local_execution": True,
        }
        assert (
            await client.post("/api/patch-audits/runs", json=payload | {"candidate_hash": "0" * 64})
        ).status_code == 409
        assert (
            await client.post(
                "/api/patch-audits/runs", json=payload | {"confirm_local_execution": False}
            )
        ).status_code == 422
        r = await client.post("/api/patch-audits/runs", json=payload)
        assert r.status_code == 202
        cancel_id = r.json()["id"]
        assert (
            await client.post("/api/evaluator/runs", json={"candidate_id": "more-bucket-reference"})
        ).status_code == 429
        assert (
            await client.post("/api/patch-audits/runs/" + cancel_id + "/cancel")
        ).status_code == 200
        cancelled = await wait_audit(client, cancel_id)
        assert cancelled["status"] == "cancelled"
        for task_id in ("more-seekable", "boltons-indexedset"):
            c = (await client.get("/api/patch-audits/examples/" + task_id + "-reference")).json()
            r = await client.post(
                "/api/patch-audits/runs",
                json={
                    "candidate_id": c["id"],
                    "candidate_hash": c["candidate_hash"],
                    "record_hash": c["record_hash"],
                    "confirm_local_execution": True,
                },
            )
            assert r.status_code == 202, r.text
            saved = await wait_audit(client, r.json()["id"])
            assert saved["status"] == "passed", saved
            assert saved["evidence"]["envelope"]["result"]["binding"][
                "verifier_hash"
            ] == verifier_id(task_id)
        # Reconcile our own completed run after simulating loss of only its DB terminal update.
        completed_id = saved["id"]
        expected = saved["evidence"]
        interrupted_id = uuid4()
        async with audit_db.begin() as session:
            row = await session.get(PatchAudit, UUID(completed_id))
            assert row
            row.status = "running"
            row.evidence = {
                k: v for k, v in row.evidence.items() if k not in ("envelope", "envelope_hash")
            }
            session.add(
                PatchAudit(
                    id=interrupted_id,
                    candidate_id=row.candidate_id,
                    candidate_hash=row.candidate_hash,
                    status="running",
                    evidence=row.evidence,
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
        assert process.returncode == 0, output.decode()
        async with asyncio.timeout(60):
            while True:
                try:
                    response = await client.get("/api/patch-audits/runs/" + completed_id)
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.4)
        recovered = response.json()
        assert recovered["status"] == "passed" and recovered["evidence"] == expected
        interrupted = (await client.get("/api/patch-audits/runs/" + str(interrupted_id))).json()
        assert interrupted["status"] == "interrupted"
        assert "envelope" not in interrupted["evidence"]
        FOLDER.mkdir(parents=True, exist_ok=True)
        (FOLDER / "recovery.json").write_text(
            json.dumps(
                {
                    "completed_id": completed_id,
                    "terminal_restored": True,
                    "interrupted_id": str(interrupted_id),
                    "interrupted_status": interrupted["status"],
                    "cancelled_id": cancel_id,
                    "cancelled_status": cancelled["status"],
                },
                indent=2,
            )
            + "\n"
        )


async def test_patch_audit_delayed_candidate_cannot_replace_selected_task():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(BASE)
        await expect(page.get_by_role("region", name="Candidate review")).to_be_visible()
        captured = asyncio.Event()
        release = asyncio.Event()

        async def delayed(route):
            response = await route.fetch()
            captured.set()
            await release.wait()
            await route.fulfill(response=response)

        await page.route("**/api/patch-audits/examples/" + PASS, delayed)
        await page.get_by_label("Retained candidate", exact=True).select_option(PASS)
        await asyncio.wait_for(captured.wait(), 10)
        await page.get_by_label("Supported software task", exact=True).select_option("more-bucket")
        release.set()
        await asyncio.sleep(0.4)
        await expect(page.get_by_label("Supported software task", exact=True)).to_have_value(
            "more-bucket"
        )
        await expect(page.get_by_role("region", name="Candidate review")).to_have_count(0)
        await expect(page.get_by_role("region", name="Patch audit result")).to_have_count(0)
        await browser.close()


async def test_recorded_explorer_first_patch_audit_failure_pass_mobile_and_no_execution():
    FOLDER.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        mutations = []
        errors = []
        page.on(
            "request",
            lambda r: mutations.append(r.url) if r.method not in ("GET", "HEAD") else None,
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(BASE + "/recorded/")
        region = page.get_by_role("region", name="Patch audit result")
        await expect(region.get_by_role("status")).to_have_text("failed")
        await expect(
            page.get_by_text("REAL SAVED EVIDENCE · NO LIVE EXECUTION", exact=True)
        ).to_be_visible()
        await expect(region).to_contain_text("length one while its keys and items are empty")
        await expect(page.get_by_role("button", name="Run fresh audit")).to_have_count(0)
        await expect(page.get_by_label("Unified diff", exact=True)).to_have_count(0)
        await region.screenshot(path=FOLDER / "recorded-missed.png")
        await page.get_by_label("Saved patch audit", exact=True).select_option(PASS)
        await expect(region.get_by_role("status")).to_have_text("passed")
        await expect(region).to_contain_text(
            "Passed the declared checks for this task and environment."
        )
        await page.get_by_text("Open code comparison · boltons/urlutils.py", exact=True).click()
        await expect(page.locator(".monaco-diff-editor:visible")).to_be_visible(timeout=20000)
        await page.set_viewport_size({"width": 390, "height": 844})
        # Monaco's ResizeObserver lays out asynchronously after the viewport changes.
        await page.wait_for_function(
            "document.documentElement.scrollWidth <= innerWidth", timeout=5000
        )
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await region.scroll_into_view_if_needed()
        await region.screenshot(path=FOLDER / "recorded-mobile.png")
        async with page.expect_download() as download:
            await page.get_by_role("link", name="Download audit evidence", exact=True).click()
        value = json.loads(
            await asyncio.to_thread(Path(await (await download.value).path()).read_text)
        )
        assert value["execution_mode"] == "recorded"
        assert value["evidence"]["candidate"]["provenance"]["category"] == "retained_model"
        await page.get_by_role("link", name="Debugger", exact=True).click()
        await expect(
            page.get_by_role("heading", name="Verified for the recorded checks", exact=True)
        ).to_be_visible()
        assert not mutations and not errors, (mutations, errors)
        await browser.close()


async def test_patch_audit_polling_fixture_serializes_requests_and_keeps_terminal_result():
    """Deterministic browser transport fixture, not a fresh execution or producer observation."""
    fixture = json.loads((ROOT / "recordings/patch-audit-missed.json").read_text())
    fixture["id"] = "ui-poll-fixture"
    running = {
        **fixture,
        "status": "running",
        "evidence": {k: v for k, v in fixture["evidence"].items() if k != "envelope"},
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        polled = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def route_poll(route):
            calls.append(1)
            if len(calls) == 1:
                await route.fulfill(json=running)
            else:
                polled.set()
                await release.wait()
                await route.fulfill(json=fixture)

        await page.route("**/api/patch-audits/runs/ui-poll-fixture", route_poll)
        await page.goto(BASE + "/?audit=ui-poll-fixture")
        await asyncio.wait_for(polled.wait(), 15)
        await asyncio.sleep(1.6)
        assert len(calls) == 2  # Initial load + one poll; no overlapping 700ms poll.
        release.set()
        await expect(
            page.get_by_role("region", name="Patch audit result").get_by_role("status")
        ).to_have_text("failed")
        await asyncio.sleep(1.2)
        assert len(calls) == 2
        await browser.close()
