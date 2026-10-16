"""Explicit opt-in for fresh live NVIDIA repair; failed attempts are retained too."""

import asyncio
import json
import os
from uuid import UUID, uuid4

import docker
import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_repair_integration import OfflineRepair

from workbench.config import ROOT, settings
from workbench.db import Investigation
from workbench.rag.snapshot import load_snapshot
from workbench.repair.service import RepairManager

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
pytestmark = pytest.mark.e2e


async def inspect_candidate(page, run_id, folder, prefix="live-repair"):
    await expect(
        page.get_by_role("heading", name="Verified for the supported checks", exact=True)
    ).to_be_visible(timeout=310000)
    await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
    await page.get_by_role("button", name="Start / reset candidate preview", exact=True).click()
    await expect(page.locator('iframe[title="Candidate application"]')).to_be_visible(timeout=25000)
    original = page.frame_locator('iframe[title="Original application"]')
    candidate = page.frame_locator('iframe[title="Candidate application"]')
    for frame in (original, candidate):
        await frame.locator("#add-to-cart").click()
        await frame.locator("#increase").click()
        await frame.locator("#increase").click()
        await expect(frame.locator("#quantity")).to_have_value("3")
    await expect(original.get_by_test_id("total")).to_have_text("$72.00")
    await expect(candidate.get_by_test_id("total")).to_have_text("$192.00")
    # Opaque sandbox forbids parent document access.
    blocked = await page.locator('iframe[title="Candidate application"]').evaluate("""
    el => {
        try { return el.contentWindow.document.body.textContent; }
        catch (error) { return error.name; }
    }""")
    assert blocked == "SecurityError"
    await original.get_by_test_id("total").scroll_into_view_if_needed()
    await candidate.get_by_test_id("total").scroll_into_view_if_needed()
    await page.locator(".repair-previews").screenshot(path=folder / f"{prefix}-before-after.png")
    await page.locator(".monaco-diff-editor").screenshot(path=folder / f"{prefix}-diff.png")
    await page.locator(".verification-table").screenshot(path=folder / f"{prefix}-checks.png")
    await page.evaluate("window.scrollTo(0,0)")
    await page.screenshot(path=folder / f"{prefix}.png", full_page=True)
    await page.get_by_role("button", name="Start / reset candidate preview", exact=True).click()
    await expect(candidate.get_by_test_id("bag-count")).to_have_text("0")
    await expect(original.get_by_test_id("bag-count")).to_have_text("3")
    await page.reload()
    await page.locator(".history-item").filter(has_text=run_id[:6]).click()
    await page.get_by_role("tab", name="Investigation", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Verified for the supported checks", exact=True)
    ).to_be_visible(timeout=15000)
    await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=15000)
    async with page.expect_download() as download:
        await page.get_by_role("link", name="Download patch", exact=True).click()
    assert (await download.value).suggested_filename == "candidate.patch"
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.wait_for_timeout(300)
    assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    await page.screenshot(path=folder / f"{prefix}-mobile.png", full_page=True)


@pytest.mark.skipif(
    os.environ.get("LIVE_NVIDIA_REPAIR") != "1", reason="Opt-in required for live NVIDIA repair"
)
async def test_live_nvidia_repair_diff_verification_preview_and_reopen():
    folder = ROOT / "artifacts/milestone-03"
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    repair_id = None
    run_id = None
    investigation_id = None
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1512, "height": 1100}, reduced_motion="reduce"
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            await page.goto(BASE_URL)
            async with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.endswith("/api/runs")
            ) as response:
                await page.get_by_role("button", name="Reproduce bug").click()
            run_id = (await (await response.value).json())["id"]
            await expect(
                page.get_by_role("heading", name="Defect reproduced", exact=True)
            ).to_be_visible(timeout=75000)
            await page.get_by_role("tab", name="Investigation", exact=True).click()
            async with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.endswith("/investigations")
            ) as response:
                await page.get_by_role("button", name="Investigate with NVIDIA", exact=True).click()
            investigation_id = (await (await response.value).json())["id"]
            await expect(
                page.get_by_role("heading", name="Diagnosis proposed", exact=True)
            ).to_be_visible(timeout=190000)
            async with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.endswith("/repairs")
            ) as response:
                await page.get_by_role(
                    "button", name="Generate candidate with NVIDIA", exact=True
                ).click()
            repair_id = (await (await response.value).json())["id"]
            await inspect_candidate(page, run_id, folder)
            assert not errors, errors
        finally:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
                payload = {
                    "mode": "live_nvidia",
                    "run_id": run_id,
                    "investigation_id": investigation_id,
                    "repair_id": repair_id,
                }
                if repair_id:
                    payload["repair"] = (await client.get(f"/api/repairs/{repair_id}")).json()
                if run_id:
                    payload["reproduction"] = (await client.get(f"/api/runs/{run_id}")).json()
                if investigation_id:
                    payload["investigation"] = (
                        await client.get(f"/api/investigations/{investigation_id}")
                    ).json()
                (folder / f"live-repair-{repair_id or investigation_id or run_id}.json").write_text(
                    json.dumps(payload, indent=2)
                )
            await page.screenshot(path=folder / "last-browser-state.png", full_page=True)
            await browser.close()


async def test_offline_repair_browser_diff_preview_download_and_saved_history():
    """Real candidate/verifier/browser with an explicitly deterministic OFFLINE provider."""
    folder = ROOT / "artifacts/milestone-03"
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as http:
        response = await http.post("/api/runs", json={"bug_id": "cart-quantity"})
        response.raise_for_status()
        run_id = response.json()["id"]
        async with asyncio.timeout(70):
            while True:
                run = (await http.get(f"/api/runs/{run_id}")).json()
                if run["status"] not in ("queued", "running"):
                    break
                await asyncio.sleep(0.25)
        assert run["status"] == "reproduced"
    fixture = json.loads(
        (ROOT / "docs/reports/assets/milestone-02/live-investigation.json").read_text()
    )["investigation"]
    engine = create_async_engine(settings.database_url)
    store = async_sessionmaker(engine, expire_on_commit=False)
    investigation_id = uuid4()
    client = docker.from_env()
    try:
        broker = client.containers.get("ai-debugging-workbench-repair-broker-1")
        ip = broker.attrs["NetworkSettings"]["Networks"]["ai-debugging-workbench_repair-control"][
            "IPAddress"
        ]
    finally:
        client.close()
    try:
        async with store.begin() as session:
            session.add(
                Investigation(
                    id=investigation_id,
                    run_id=UUID(run_id),
                    status="completed",
                    report="OFFLINE deterministic browser fixture: " + fixture["report"],
                    snapshot_id=load_snapshot().id,
                    diagnosis=fixture["diagnosis"],
                    retrieval=fixture["retrieval"],
                    model_input={"mode": "offline_fixture"},
                    provider_calls=[{"mode": "offline_fixture"}],
                    events=[],
                )
            )
        manager = RepairManager(lambda: OfflineRepair(), store, f"http://{ip}:8012")
        created = await manager.create(investigation_id)
        await asyncio.gather(*list(manager.tasks.values()))
        saved = await manager.get(created["id"])
        assert saved["status"] == "verified", saved
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": 1512, "height": 1100}, reduced_motion="reduce"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(BASE_URL)
            await page.locator(".history-item").filter(has_text=run_id[:6]).click()
            await page.get_by_role("tab", name="Investigation", exact=True).click()
            await inspect_candidate(page, run_id, folder, "offline-repair")
            # An old preview response must not appear under a newly selected repair identity.
            second = {**saved, "id": str(uuid4())}
            await page.route(
                f"**/investigations/{investigation_id}/repairs",
                lambda route: route.fulfill(
                    json=[
                        json.loads(json.dumps(saved, default=str)),
                        json.loads(json.dumps(second, default=str)),
                    ]
                ),
            )
            await page.set_viewport_size({"width": 1512, "height": 1100})
            await page.reload()
            await page.locator(".history-item").filter(has_text=run_id[:6]).click()
            await page.get_by_role("tab", name="Investigation", exact=True).click()
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed_preview(route):
                started.set()
                await release.wait()
                await route.fulfill(json={"url": "http://127.0.0.1:8013/preview/stale-response/"})

            await page.route("**/api/repairs/*/attempts/*/preview", delayed_preview)
            await page.get_by_role(
                "button", name="Start / reset candidate preview", exact=True
            ).click()
            async with asyncio.timeout(10):
                await started.wait()
            await expect(
                page.get_by_role("button", name="Starting candidate preview…", exact=True)
            ).to_be_disabled()
            await page.locator("#saved-repairs").select_option(second["id"])
            async with page.expect_response(lambda r: r.url.endswith("/preview")) as pending:
                release.set()
            await (await pending.value).finished()
            await page.evaluate(
                "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
            await expect(page.locator('iframe[title="Candidate application"]')).to_have_count(0)
            assert not errors, errors
            await browser.close()
        await manager.close()
    finally:
        await engine.dispose()
