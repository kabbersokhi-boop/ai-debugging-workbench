"""Deterministic response races and first-visit recorded UX; no inference is performed."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from playwright.async_api import async_playwright, expect

from workbench.config import ROOT
from workbench.contracts import BUG

BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("action", ["start", "cancel"])
async def test_repair_action_response_cannot_cross_investigation_selection(action):
    record = json.loads((ROOT / "recordings/m3-live-success.json").read_text())
    run, original = record["reproduction"], record["investigation"]
    a = {**original, "id": str(uuid4()), "report": "Offline investigation A"}
    b = {**original, "id": str(uuid4()), "report": "Offline investigation B"}
    stale = {**record["repair"], "investigation_id": a["id"], "id": str(uuid4())}
    stale["state"]["attempts"][-1]["proposal"]["explanation"] = "STALE INVESTIGATION A EVIDENCE"
    pending, release = asyncio.Event(), asyncio.Event()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1512, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def route_api(route):
            path = route.request.url.split("/api", 1)[1]
            method = route.request.method
            if method == "POST" and (path.endswith("/repairs") or path.endswith("/cancel")):
                pending.set()
                await release.wait()
                await route.fulfill(json=stale)
            elif path == "/mode":
                await route.fulfill(json={"mode": "private_live"})
            elif path == "/health":
                await route.fulfill(json={"status": "ok"})
            elif path == "/bugs":
                await route.fulfill(json=[BUG.model_dump()])
            elif path == "/runs":
                await route.fulfill(json=[run])
            elif path == f"/runs/{run['id']}":
                await route.fulfill(json=run)
            elif path.endswith("/investigations"):
                await route.fulfill(json=[a, b])
            elif path == f"/investigations/{a['id']}/repairs":
                await route.fulfill(
                    json=[{**stale, "status": "inspecting"}] if action == "cancel" else []
                )
            elif path.endswith("/repairs"):
                await route.fulfill(json=[])
            elif path == f"/repairs/{stale['id']}":
                await route.fulfill(json={**stale, "status": "inspecting"})
            else:
                await route.continue_()

        await page.route("**/api/**", route_api)
        await page.goto(BASE)
        await page.locator(".history-item").first.click()
        await page.get_by_role("tab", name="Investigation", exact=True).click()
        await expect(page.locator("#saved-investigations")).to_have_value(a["id"])
        button = "Generate candidate with NVIDIA" if action == "start" else "Cancel repair"
        if action == "cancel":
            await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
        await page.get_by_role("button", name=button, exact=True).click()
        async with asyncio.timeout(10):
            await pending.wait()
        await page.locator("#saved-investigations").select_option(b["id"])
        await expect(page.locator("#saved-repairs")).to_have_count(0)
        async with page.expect_response(
            lambda response: response.request.method == "POST"
        ) as response:
            release.set()
        await (await response.value).finished()
        await page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        await expect(page.locator("#saved-investigations")).to_have_value(b["id"])
        await expect(page.locator("#saved-repairs")).to_have_count(0)
        await expect(page.locator(".repair-workspace")).not_to_contain_text(
            "STALE INVESTIGATION A EVIDENCE"
        )
        await expect(
            page.get_by_role("button", name="Generate candidate with NVIDIA", exact=True)
        ).to_be_enabled()
        assert not errors, errors
        await browser.close()


@pytest.mark.skipif(
    os.environ.get("M4_SAVED_REOPEN") != "1",
    reason="Requires the saved local M4 live run; makes no inference",
)
async def test_m4_saved_shipping_reopen_without_inference_after_ui_correction():
    folder = ROOT / "artifacts/milestone-04"
    saved = json.loads((folder / "live-shipping-run.json").read_text())
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1000},
            record_video_dir=folder / "reopen-video",
            record_video_size={"width": 1280, "height": 888},
        )
        page = await context.new_page()
        errors, inference = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "request",
            lambda r: (
                inference.append(r.url)
                if r.method == "POST"
                and (r.url.endswith("/investigations") or r.url.endswith("/repairs"))
                else None
            ),
        )
        await page.goto(BASE)
        await page.locator(".history-item").filter(has_text=saved["reproduction"]["id"][:6]).click()
        await page.get_by_role("tab", name="Investigation", exact=True).click()
        await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
        await page.get_by_role("button", name="Start / reset candidate preview", exact=True).click()
        remote = page.get_by_role("region", name="Remote candidate application")
        await remote.get_by_role("button", name="Reset candidate", exact=True).click()
        await expect(remote.get_by_test_id("remote-quantity")).to_have_text("0", timeout=15000)
        for label in ("Add to bag", "Increase quantity"):
            await remote.get_by_role("button", name=label, exact=True).click()
            await expect(remote.get_by_role("button", name=label, exact=True)).to_be_enabled(
                timeout=15000
            )
        await expect(remote.get_by_test_id("remote-total")).to_have_text("$128.00")
        original = page.frame_locator('iframe[title="Original application"]')
        await original.locator("#add-to-cart").click()
        await original.locator("#increase").click()
        await expect(original.get_by_test_id("total")).to_have_text("$136.00")
        await page.locator(".repair-previews").screenshot(
            path=folder / "final-shipping-comparison.png"
        )
        await page.get_by_role("tab", name="Browser evidence", exact=True).click()
        await page.get_by_role("tab", name="Investigation", exact=True).click()
        await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(path=folder / "final-shipping-mobile.png", full_page=True)
        assert not errors, errors
        assert not inference, inference
        await context.close()
        await browser.close()


async def test_recorded_explorer_first_visit_mobile_and_no_live_requests():
    folder = ROOT / "artifacts/milestone-04"
    folder.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
        )
        mutations = []
        errors = []
        page.on(
            "request",
            lambda request: mutations.append(request.url) if request.method == "POST" else None,
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE + "/recorded/")
        await expect(
            page.get_by_role("heading", name="Verified for the recorded checks")
        ).to_be_visible()
        await page.get_by_role("link", name="Original / candidate", exact=True).click()
        await expect(page.locator(".recorded-comparison")).to_be_visible()
        await page.screenshot(path=folder / "recorded-desktop.png", full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.get_by_role(
            "heading", name="Verified for the recorded checks"
        ).scroll_into_view_if_needed()
        await page.screenshot(path=folder / "recorded-mobile.png", full_page=True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not mutations
        assert not errors
        await browser.close()


@pytest.mark.skipif(
    os.environ.get("LIVE_NVIDIA_M4") != "1", reason="Explicit live milestone 4 demonstration"
)
async def test_m4_live_workflow_shipping_scenario_video():
    import httpx

    folder = ROOT / "artifacts/milestone-04"
    folder.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1000},
            record_video_dir=folder / "video",
            record_video_size={"width": 1280, "height": 888},
        )
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        run_id = None
        try:
            await page.goto(BASE)
            await page.locator("#scenario").select_option("shipping-threshold")
            async with page.expect_response(
                lambda r: r.request.method == "POST" and r.url.endswith("/api/runs")
            ) as response:
                await page.get_by_role("button", name="Start full workflow", exact=True).click()
            run_id = (await (await response.value).json())["id"]
            await expect(
                page.locator(".workflow-launcher").get_by_role(
                    "heading", name="Verified for the supported checks", exact=True
                )
            ).to_be_visible(timeout=550000)
            await page.get_by_role(
                "link", name="Inspect diff, checks and original / candidate comparison ↓"
            ).click()
            await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
            await page.get_by_role(
                "button", name="Start / reset candidate preview", exact=True
            ).click()
            remote = page.get_by_role("region", name="Remote candidate application")
            await remote.get_by_role("button", name="Reset candidate", exact=True).click()
            await expect(remote.get_by_test_id("remote-quantity")).to_have_text("0", timeout=15000)
            for label in ("Add to bag", "Increase quantity"):
                await remote.get_by_role("button", name=label, exact=True).click()
                await expect(remote.get_by_role("button", name=label, exact=True)).to_be_enabled(
                    timeout=15000
                )
            await expect(remote.get_by_test_id("remote-total")).to_have_text("$128.00")
            original = page.frame_locator('iframe[title="Original application"]')
            await original.locator("#add-to-cart").click()
            await original.locator("#increase").click()
            await expect(original.get_by_test_id("total")).to_have_text("$136.00")
            await page.locator(".repair-previews").screenshot(
                path=folder / "live-shipping-comparison.png"
            )
            await page.screenshot(path=folder / "live-shipping-workspace.png", full_page=True)
            assert not errors, errors
        finally:
            if run_id:
                async with httpx.AsyncClient(base_url=BASE, timeout=10) as client:
                    run = (await client.get(f"/api/runs/{run_id}")).json()
                    investigations = (await client.get(f"/api/runs/{run_id}/investigations")).json()
                    repairs = (
                        (
                            await client.get(
                                f"/api/investigations/{investigations[0]['id']}/repairs"
                            )
                        ).json()
                        if investigations
                        else []
                    )
                    (folder / "live-shipping-run.json").write_text(
                        json.dumps(
                            {
                                "mode": "live_nvidia",
                                "reproduction": run,
                                "investigation": investigations[0] if investigations else None,
                                "repair": repairs[0] if repairs else None,
                            },
                            indent=2,
                        )
                    )
            await context.close()
            await browser.close()
