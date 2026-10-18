"""Real retained producer evidence journey; rendering fixtures are explicitly separate tests."""

import asyncio
import copy
import json
import os
from pathlib import Path

import httpx
import pytest
from playwright.async_api import async_playwright, expect

from workbench.config import ROOT

pytestmark = pytest.mark.e2e
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
URL = BASE + "/?workspace=evaluation&comparison=m02-v1"
API = "/api/evaluator/comparisons/m02-v1"


async def test_comparison_actual_evidence_navigation_download_and_controls():
    folder = ROOT / "artifacts/evaluator-m02/ui"
    folder.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        response = await client.get(API)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["complete"] and data["attempted"] == data["scheduled"] == 24
        assert sum(g["completed"] for g in data["groups"]) == 6
        assert sum(g["incremental_numerator"] for g in data["groups"]) == 0
        assert sum(g["incremental_denominator"] for g in data["groups"]) == 6
        assert len(data["controls"]) == 16
        assert all(r["evaluation_id"] for r in data["trials"] if r["outcome"] == "both_passed")
        (folder.parent / "comparison-persisted.json").write_text(json.dumps(data, indent=2) + "\n")
        for trial in data["trials"]:
            saved = (await client.get(API + "/trials/" + trial["id"])).json()
            if saved.get("candidate"):
                cid = saved["candidate"]["id"]
                assert (await client.get("/api/evaluator/candidates/" + cid)).status_code == 200
                assert (
                    await client.post("/api/evaluator/runs", json={"candidate_id": cid})
                ).status_code == 422
        assert (await client.get(API + "/trials/not-an-approved-id")).status_code == 404
        assert (await client.post(API, json={"command": "anything"})).status_code == 405
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(BASE + "/?workspace=evaluation")
        await page.get_by_role("link", name="Controlled producer comparison").click()
        await expect(
            page.get_by_role("heading", name="Controlled producer comparison")
        ).to_be_visible()
        conclusion = page.get_by_role("region", name="Comparison conclusion")
        await expect(conclusion.get_by_text("0/6", exact=True)).to_be_visible(timeout=30000)
        await expect(conclusion.get_by_text("6/24", exact=True)).to_be_visible()
        await expect(conclusion).to_contain_text("inconclusive")
        await page.screenshot(path=folder / "comparison.png", full_page=True)
        await page.get_by_label("Filter by task").select_option("more-bucket")
        await page.get_by_role("button", name="more-bucket nemotron3 trial 1", exact=True).click()
        detail = page.get_by_role("region", name="Trial evidence")
        await expect(detail).to_contain_text("Genuine controlled producer trial", timeout=30000)
        await expect(detail).to_contain_text("both passed")
        await page.reload()
        await expect(detail).to_contain_text("Genuine controlled producer trial", timeout=30000)
        async with page.expect_download() as download:
            await page.get_by_role("link", name="Download complete trial evidence").click()
        path = await (await download.value).path()
        saved = json.loads(await asyncio.to_thread(Path(path).read_text))
        assert saved["candidate"]["id"] == saved["generation"]["id"]
        assert saved["result"]["trial_binding_hash"] == saved["scoring"]["trial_binding_hash"]
        await detail.get_by_text("Open code comparison", exact=False).first.click()
        await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
        await detail.screenshot(path=folder / "genuine-trial.png")
        await page.get_by_role("link", name="Open saved evaluation", exact=True).click()
        await expect(
            page.get_by_role("region", name="Evaluation result").get_by_role("status")
        ).to_have_text("passed", timeout=30000)
        await expect(page.locator(".run-error[role=alert]")).to_have_count(0)
        await page.get_by_role("link", name="Open its comparison and generation conditions").click()
        await expect(page.get_by_role("region", name="Trial evidence")).to_contain_text(
            "Genuine controlled producer trial", timeout=30000
        )
        await page.get_by_role("button", name="Close evidence", exact=True).click()
        await expect(page.get_by_role("region", name="Trial evidence")).to_have_count(0)
        provider = next(
            r for r in data["trials"] if r["outcome"] == "infrastructure_or_provider_failure"
        )
        await page.goto(URL + "&trial=" + provider["id"])
        await expect(conclusion.get_by_text("0/6", exact=True)).to_be_visible(timeout=30000)
        await expect(detail).to_contain_text("No candidate code defect is inferred", timeout=30000)
        await expect(detail).not_to_contain_text("undefined")
        await detail.screenshot(path=folder / "provider-failure.png")
        unusable = next(r for r in data["trials"] if r["outcome"] == "no_usable_candidate")
        await page.goto(URL + "&trial=" + unusable["id"])
        await expect(conclusion.get_by_text("0/6", exact=True)).to_be_visible(timeout=30000)
        await expect(detail).to_contain_text("without a final submission", timeout=30000)
        await expect(detail).to_contain_text("No submitted final patch exists")
        await detail.screenshot(path=folder / "no-submission.png")
        await page.goto(URL + "&control=boltons-addlist-baseline")
        await expect(conclusion.get_by_text("0/6", exact=True)).to_be_visible(timeout=30000)
        await expect(detail).to_contain_text("Authored control", timeout=30000)
        await expect(detail).to_contain_text("len() is 1")
        await expect(detail).to_contain_text("keys() and items() are empty")
        await detail.screenshot(path=folder / "control-empty-state.png")
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(path=folder / "comparison-mobile.png", full_page=True)
        assert not errors, errors
        await browser.close()


async def test_comparison_deterministic_rendering_fixtures_ties_zero_and_pending():
    """Network interception only: never stored, scored, or captured as genuine evidence."""
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        actual = (await client.get(API)).json()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        fixture = copy.deepcopy(actual)
        for g in fixture["groups"]:
            g["completed"] = 0
            g["incremental_numerator"] = g["incremental_denominator"] = 0
            g["outcomes"] = {
                key: 12 if key == "no_usable_candidate" else 0 for key in g["outcomes"]
            }
        for row in fixture["trials"]:
            row["outcome"] = "no_usable_candidate"

        async def render(route):
            await route.fulfill(json=fixture)

        await page.route("**" + API, render)
        await page.goto(URL)
        await expect(page.get_by_text("Observed outcome counts tie.", exact=False)).to_be_visible()
        await expect(
            page.get_by_text("An incremental rate is unknown.", exact=False)
        ).to_be_visible()
        assert "NaN" not in await page.locator("body").inner_text()
        fixture["complete"] = False
        fixture["groups"][0]["outcomes"]["no_usable_candidate"] = 11
        fixture["groups"][0]["awaiting_evaluation"] = 1
        await page.reload()
        await expect(
            page.get_by_text("Currently retained (provisional):", exact=False)
        ).to_be_visible()
        await expect(page.get_by_text("1 submitted trials await final evaluation.")).to_be_visible()
        await browser.close()
