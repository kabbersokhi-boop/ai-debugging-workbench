import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from playwright.async_api import async_playwright, expect

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
EVIDENCE = Path(os.environ.get("E2E_EVIDENCE_DIR", "../artifacts/acceptance"))
pytestmark = pytest.mark.e2e


async def completed(client: httpx.AsyncClient, run_id: str) -> dict:
    async with asyncio.timeout(75):
        while True:
            response = await client.get(f"/api/runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            if run["status"] not in ("queued", "running"):
                return run
            await asyncio.sleep(0.2)


async def test_first_visitor_can_reproduce_inspect_and_reopen_history() -> None:
    await asyncio.to_thread(EVIDENCE.mkdir, parents=True, exist_ok=True)
    errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1512, "height": 1100}, reduced_motion="reduce"
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE_URL)
        await expect(
            page.get_by_role("heading", name="From bug report to browser proof.")
        ).to_be_visible()
        await expect(page.get_by_role("button", name="Reproduce bug")).to_be_enabled()
        await page.screenshot(path=EVIDENCE / "workspace-ready.png", full_page=True)
        await page.get_by_role("button", name="Reproduce bug").click()
        await expect(
            page.get_by_role("heading", name="Defect reproduced", exact=True)
        ).to_be_visible(timeout=75000)
        await expect(page.get_by_text("3 mismatches found")).to_be_visible()
        screenshot = page.get_by_role("img", name="Actual Playwright defect", exact=False)
        await expect(screenshot).to_be_visible()
        assert await screenshot.evaluate("img => img.complete && img.naturalWidth === 1200")
        await page.screenshot(path=EVIDENCE / "workspace-reproduced.png", full_page=True)
        await page.get_by_role("button", name="Baseline", exact=True).click()
        await expect(
            page.get_by_role("img", name="Actual Playwright baseline", exact=False)
        ).to_be_visible()
        await page.get_by_role("button", name="Defect", exact=True).click()
        await page.get_by_role("button", name="Interactive storefront", exact=True).click()
        fixture = page.frame_locator('iframe[title="Interactive synthetic retail storefront"]')
        await fixture.get_by_role("button", name="Add to bag").click()
        await fixture.get_by_role("button", name="Increase quantity").click(click_count=2)
        await expect(fixture.get_by_test_id("line-total")).to_have_text("$192.00")
        await expect(fixture.get_by_test_id("subtotal")).to_have_text("$64.00")
        await page.get_by_role("tab", name="Bug report").click()
        await expect(page.get_by_role("heading", name="The reported defect")).to_be_visible()
        await page.get_by_role("tab", name="Run details").click()
        await expect(page.get_by_role("link", name="Playwright trace")).to_be_visible()
        await page.reload()
        await expect(page.get_by_role("button", name="Reproduce bug")).to_be_enabled()
        await page.get_by_role("button", name="Defect reproduced", exact=False).first.click()
        await expect(page.get_by_text("3 mismatches found")).to_be_visible()
        await page.set_viewport_size({"width": 390, "height": 844})
        await expect(page.get_by_role("button", name="Run again")).to_be_visible()
        assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        await page.screenshot(path=EVIDENCE / "workspace-mobile.png", full_page=True)
        assert not errors, errors
        await browser.close()


async def test_actual_api_evidence_and_idempotency() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        assert (await client.get("/api/health")).json()["database"] == "postgresql"
        key = str(uuid4())
        response = await client.post(
            "/api/runs", json={"bug_id": "cart-quantity"}, headers={"Idempotency-Key": key}
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        duplicate = await client.post(
            "/api/runs", json={"bug_id": "cart-quantity"}, headers={"Idempotency-Key": key}
        )
        assert duplicate.json()["id"] == run_id
        run = await completed(client, run_id)
        assert run["status"] == "reproduced", run
        result = run["result"]
        assert result["baseline"]["total_cents"] == 7200
        assert result["observed"]["quantity"] == 3
        assert result["observed"]["line_total_cents"] == 19200
        assert result["observed"]["subtotal_cents"] == 6400
        assert sum(not check["passed"] for check in result["checks"]) == 3
        assert len(result["fixture_sha256"]) == 64
        assert [e["sequence"] for e in run["events"]] == list(range(1, len(run["events"]) + 1))
        for name in ["before.png", "after.png", "trace.zip", "console.json", "result.json"]:
            artifact = await client.get(f"/api/runs/{run_id}/artifacts/{name}")
            assert artifact.status_code == 200
            assert artifact.content
            if name.endswith(".png"):
                assert artifact.content.startswith(b"\x89PNG")
            elif name == "trace.zip":
                assert artifact.content.startswith(b"PK")
            elif name == "result.json":
                assert artifact.json() == result
        assert (await client.get(f"/api/runs/{run_id}/artifacts/.env")).status_code == 404
        assert (await client.get(f"/api/runs/{run_id}/artifacts/cart.js")).status_code == 404
        assert any(item["id"] == run_id for item in (await client.get("/api/runs")).json())
        assert (await client.post(f"/api/runs/{run_id}/cancel")).json()["status"] == "reproduced"
        await asyncio.to_thread(EVIDENCE.mkdir, parents=True, exist_ok=True)
        (EVIDENCE / "verified-run.json").write_text(json.dumps(run, indent=2))


@pytest.mark.parametrize(
    "payload",
    [
        {"bug_id": "unknown"},
        {"bug_id": "cart-quantity", "command": "echo unsafe"},
        {"bug_id": "cart-quantity", "url": "https://example.com"},
    ],
)
async def test_api_rejects_unsupported_authority(payload: dict) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        assert (await client.post("/api/runs", json=payload)).status_code == 422


async def test_capacity_cancellation_and_no_late_success() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        responses = [
            await client.post("/api/runs", json={"bug_id": "cart-quantity"}) for _ in range(3)
        ]
        assert [response.status_code for response in responses] == [202, 202, 429]
        ids = [response.json()["id"] for response in responses[:2]]
        for run_id in ids:
            response = await client.post(f"/api/runs/{run_id}/cancel")
            assert response.json()["status"] == "cancelled"
            assert response.json()["result"] is None
        await asyncio.sleep(1)
        for run_id in ids:
            run = (await client.get(f"/api/runs/{run_id}")).json()
            assert run["status"] == "cancelled"
            assert run["result"] is None
