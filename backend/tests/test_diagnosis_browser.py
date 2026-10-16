import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest
from playwright.async_api import async_playwright, expect

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
pytestmark = pytest.mark.e2e


async def test_presentation_regression_for_passed_checks_and_interactive_footer() -> None:
    # Explicit browser-only deterministic fixture; never used by the product API.
    fixture = json.loads(
        await asyncio.to_thread(Path("../docs/reports/assets/verified-run.json").read_text)
    )
    fixture["status"] = "not_reproduced"
    fixture["result"]["status"] = "not_reproduced"
    fixture["result"]["observed"].update(subtotal_cents=19200, shipping_cents=0, total_cents=19200)
    for check in fixture["result"]["checks"]:
        check["passed"] = True
        check["observed_cents"] = check["expected_cents"]
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.route("**/api/runs", lambda route: route.fulfill(json=[fixture]))
        await page.route(f"**/api/runs/{fixture['id']}", lambda route: route.fulfill(json=fixture))
        await page.goto(BASE_URL)
        await page.get_by_role("button", name="Not reproduced", exact=False).first.click()
        await expect(
            page.get_by_role("img", name="Actual Playwright after state", exact=False)
        ).to_have_attribute(
            "alt",
            "Actual Playwright after state: quantity 3, line amount $192.00, "
            "subtotal $192.00, shipping $0.00, total $192.00. "
            "The reported defect was not observed.",
        )
        await expect(
            page.get_by_text("Baseline and after-action pricing checks passed.", exact=False)
        ).to_be_visible()
        await page.get_by_role("button", name="Interactive storefront", exact=True).click()
        await expect(page.locator(".browser-footer")).to_contain_text(
            "Interactive fixture · Separate from the automated session"
        )
        await expect(page.locator(".browser-footer")).not_to_contain_text("Captured by Playwright")
        await browser.close()


@pytest.mark.skipif(
    os.environ.get("LIVE_NVIDIA_E2E") != "1",
    reason="Explicit opt-in required for real NVIDIA calls",
)
async def test_live_nvidia_investigation_citations_inspector_and_reopened_history() -> None:
    folder = Path("../artifacts/milestone-02")
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1512, "height": 1100}, reduced_motion="reduce"
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE_URL)
        async with page.expect_response(
            lambda response: (
                response.request.method == "POST" and response.url.endswith("/api/runs")
            )
        ) as created_response:
            await page.get_by_role("button", name="Reproduce bug").click()
        run = await (await created_response.value).json()
        await expect(
            page.get_by_role("heading", name="Defect reproduced", exact=True)
        ).to_be_visible(timeout=75000)
        await page.get_by_role("tab", name="Investigation", exact=True).click()
        async with page.expect_response(
            lambda response: (
                response.request.method == "POST" and response.url.endswith("/investigations")
            )
        ) as investigation_response:
            await page.get_by_role("button", name="Investigate with NVIDIA").click()
        created = await (await investigation_response.value).json()
        assert "id" in created, created
        await expect(
            page.get_by_role("heading", name="Diagnosis proposed", exact=True)
        ).to_be_visible(timeout=190000)
        await expect(page.get_by_role("heading", name="Retrieval Inspector")).to_be_visible()
        await page.locator(".citation-links button").first.click()
        await expect(page.get_by_label("Frozen source snippet")).to_be_visible()
        await page.evaluate("window.scrollTo(0, 0)")
        await page.screenshot(path=folder / "live-investigation.png", full_page=True)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
            saved = (await client.get(f"/api/investigations/{created['id']}")).json()
            reproduction = (await client.get(f"/api/runs/{run['id']}")).json()
        assert saved["status"] == "completed", saved
        assert saved["diagnosis"]["citations"]
        supplied = {row["source_id"]: row for row in saved["retrieval"]["supplied_context"]}
        for citation in saved["diagnosis"]["citations"]:
            chunk = supplied[citation["source_id"]]
            assert (
                chunk["start_line"]
                <= citation["start_line"]
                <= citation["end_line"]
                <= chunk["end_line"]
            )
        assert all(call.get("status") == 200 for call in saved["provider_calls"])
        assert any(call["workload"] == "chat" for call in saved["provider_calls"])
        await page.reload()
        await page.get_by_role("button", name="Defect reproduced", exact=False).first.click()
        await page.get_by_role("tab", name="Investigation", exact=True).click()
        await expect(
            page.get_by_role("heading", name="Diagnosis proposed", exact=True)
        ).to_be_visible()
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        await page.screenshot(path=folder / "live-investigation-mobile.png", full_page=True)
        assert not errors, errors
        (folder / "live-investigation.json").write_text(
            json.dumps(
                {"mode": "live_nvidia", "reproduction": reproduction, "investigation": saved},
                indent=2,
            )
        )
        print(f"Live NVIDIA investigation saved: {saved['id']}; reproduction {run['id']}")
        await browser.close()
