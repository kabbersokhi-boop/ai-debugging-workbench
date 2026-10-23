"""Deterministic replay navigation in the real local UI; no new external audit executions."""

import json
import os

import httpx
import pytest
from playwright.async_api import async_playwright, expect

from workbench.config import ROOT

pytestmark = pytest.mark.integration
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_campaign_candidate_navigation_download_and_saved_reopen():
    output = ROOT / "artifacts/repository-audit-g3/browser"
    output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        before = (await client.get("/api/repository-audits/runs")).json()
        response = await client.get("/api/repository-audits/campaigns/g3")
        assert response.status_code == 200, response.text
        summary = response.json()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 1100})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(BASE + "/?source=external")
            campaign = page.get_by_role("region", name="G3 real change campaign")
            # A named section is exposed as a region by its aria-label.
            await expect(campaign).to_be_visible()
            for key in ("inflection-title", "stringcase-camel", "flatten-recursive"):
                await page.get_by_label("Campaign candidate", exact=True).select_option(key)
                await expect(page.get_by_label("External audit result", exact=True)).to_have_count(
                    0
                )
                role = "reference" if key == "flatten-recursive" else "candidate"
                row = next(
                    r
                    for r in summary["rows"]
                    if r["case"] == key and r["role"] == role and r["trial"] == 1
                )
                await campaign.get_by_role("button", name=f"Inspect {role} 1", exact=True).click()
                result = page.get_by_label("External audit result", exact=True)
                await expect(result).to_be_visible()
                await expect(
                    result.get_by_text("Saved G3 campaign evidence", exact=False)
                ).to_be_visible()
                async with page.expect_download() as download_info:
                    await result.get_by_role(
                        "link", name="Download repository evidence", exact=True
                    ).click()
                download = await download_info.value
                path = output / f"{key}.json"
                await download.save_as(path)
                saved = json.loads(path.read_text())
                assert saved["id"] == row["run_id"]
                reopened = (
                    await client.get("/api/repository-audits/campaigns/g3/runs/" + row["run_id"])
                ).json()
                assert saved == reopened
                await result.screenshot(path=str(output / f"{key}.png"))
                url = page.url
                await page.reload()
                await expect(page.get_by_label("External audit result", exact=True)).to_be_visible()
                assert page.url == url
                # Reload may reset the selector; choose the next key explicitly in the loop.
                campaign = page.get_by_role("region", name="G3 real change campaign")
            assert not errors, errors
            await page.get_by_label("Campaign candidate", exact=True).select_option("flatten-for")
            await expect(
                campaign.get_by_text("No admitted execution evidence", exact=False)
            ).to_be_visible()
            await expect(
                campaign.get_by_text("Intake rejects the immutable base tree", exact=False)
            ).to_be_visible()
            await campaign.screenshot(path=str(output / "unsupported-source.png"))
            await browser.close()
        after = (await client.get("/api/repository-audits/runs")).json()
        assert before == after, "Campaign replay must not start execution"
