"""Actual UI replay of the separate addendum; no new target executions."""

import json
import os

import httpx
import pytest
from playwright.async_api import async_playwright, expect

from workbench.config import ROOT

pytestmark = pytest.mark.integration
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_node_addendum_separate_history_candidate_download_and_reopen():
    output = ROOT / "artifacts/repository-audit-g3c/browser"
    output.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        before = (await client.get("/api/repository-audits/runs")).json()
        response = await client.get("/api/repository-audits/campaigns/g3-node-compatibility")
        assert response.status_code == 200, response.text
        summary = response.json()
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 1100})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(BASE + "/?source=external")
            old = page.get_by_role("region", name="G3 real change campaign", exact=True)
            new = page.get_by_role("region", name="G3 Node compatibility addendum", exact=True)
            await expect(old).to_contain_text("4 / 6 genuine candidates formally evaluated")
            await expect(new).to_contain_text("2 / 2 genuine candidates formally evaluated")
            await expect(new).to_contain_text("Combined distinct coverage: 6 / 6")
            for key in ("flatten-recursive", "flatten-for"):
                await page.get_by_label("Node compatibility candidate", exact=True).select_option(
                    key
                )
                await new.get_by_role("button", name="Inspect candidate 1", exact=True).click()
                result = page.get_by_label("External audit result", exact=True)
                await expect(result).to_contain_text(
                    "Saved G3 Node compatibility addendum evidence"
                )
                async with page.expect_download() as info:
                    await result.get_by_role(
                        "link", name="Download repository evidence", exact=True
                    ).click()
                download = await info.value
                path = output / (key + ".json")
                await download.save_as(path)
                audit = json.loads(path.read_text())
                row = next(
                    r
                    for r in summary["rows"]
                    if r["case"] == key and r["role"] == "candidate" and r["trial"] == 1
                )
                assert audit["id"] == row["run_id"]
                assert (
                    audit
                    == (
                        await client.get(
                            "/api/repository-audits/campaigns/g3-node-compatibility/runs/"
                            + row["run_id"]
                        )
                    ).json()
                )
                assert audit["evidence"]["plan"]["runtime"] == "node22_compat"
                await result.screenshot(path=str(output / (key + ".png")))
                url = page.url
                await page.reload()
                await expect(page.get_by_label("External audit result", exact=True)).to_be_visible()
                assert page.url == url
                await expect(
                    page.get_by_label("Node compatibility candidate", exact=True)
                ).to_have_value(key)
            await new.screenshot(path=str(output / "separate-addendum.png"))
            assert not errors, errors
            await browser.close()
        assert (await client.get("/api/repository-audits/runs")).json() == before
