"""End-to-end G2 local workflow; fixture intake only, real API/DB/broker/Docker thereafter."""

import copy
import json
import os

import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_independent_verification import fixture_verification
from test_repository_audit import fixture_source, patch_for

from workbench.config import ROOT, settings
from workbench.db import RepositorySource
from workbench.repository_audit.intake import summary

pytestmark = pytest.mark.integration
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_independent_browser_approval_failure_download_reopen_and_selection():
    source = fixture_source()
    db = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(db).begin() as session:
            if await session.get(RepositorySource, source["id"]) is None:
                session.add(RepositorySource(id=source["id"], record=source))
    finally:
        await db.dispose()
    req = copy.deepcopy(fixture_verification()["verification"]["requirements"][0])
    for key in ("id", "snapshot_id", "version"):
        req.pop(key)
    assertions = [{"id": "negative", "requirement_index": 0, "args": [-3, 2], "expected": -1}]
    patch = patch_for(source, replacement="def add(a, b):\n    return a + b if a >= 0 else 999\n")
    output = ROOT / "artifacts/repository-audit-g2/browser"
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p, httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.goto(BASE + "/?source=external")
        await page.get_by_label("GitHub owner/repository", exact=True).fill(source["repository"])
        await page.get_by_label("Immutable base commit", exact=True).fill(source["base_commit"])
        await page.get_by_role("button", name="Fetch source for review").click()
        await page.get_by_label("Approved production file scope").select_option("library.py")
        await page.get_by_label("External unified diff", exact=True).fill(patch)
        await page.get_by_role("button", name="Admit patch for review").click()
        await page.get_by_label("Test command arguments", exact=True).fill(
            '["python","-m","pytest","-q"]'
        )
        await page.get_by_role("button", name="Prepare exact plan for approval").click()
        await page.get_by_label("Add independent verification", exact=True).check()
        await page.get_by_role("button", name="Advanced JSON", exact=True).click()
        await page.get_by_label("Independent requirements", exact=True).fill(json.dumps([req]))
        await page.get_by_text("I reviewed the provenance", exact=False).click()
        await page.get_by_label("Independent target file", exact=True).fill("library.py")
        await page.get_by_label("Public function export", exact=True).fill("add")
        await page.get_by_label("Named assertions", exact=True).fill(json.dumps(assertions))
        await page.get_by_role("button", name="Prepare independent plan", exact=True).click()
        await expect(
            page.get_by_role("button", name="Validate independent checker")
        ).to_be_disabled()
        await page.get_by_text("I approve running this plan's positive", exact=False).click()
        async with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/api/repository-audits/runs")
        ) as validation_response:
            await page.get_by_role("button", name="Validate independent checker").click()
        validation_response_value = await validation_response.value
        assert validation_response_value.status == 202, await validation_response_value.text()
        await expect(page.get_by_label("Named assertions", exact=True)).to_be_disabled()
        await expect(page.get_by_label("GitHub owner/repository", exact=True)).to_be_disabled()
        await expect(
            page.get_by_label("Approve validated independent plan", exact=True)
        ).to_be_visible(timeout=60000)
        await expect(
            page.get_by_role("button", name="Run ordinary and independent checks")
        ).to_be_disabled()
        await page.screenshot(path=str(output / "validated-plan.png"), full_page=True)
        await page.get_by_label("Approve validated independent plan", exact=True).check()
        await page.get_by_text("I reviewed this exact source, patch and plan", exact=False).click()
        async with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/api/repository-audits/runs")
        ) as response:
            await page.get_by_role("button", name="Run ordinary and independent checks").click()
        audit_id = (await (await response.value).json())["id"]
        await expect(page.locator(".audit-result [role=status]")).to_have_text(
            "assertions failed", timeout=60000
        )
        await expect(page.get_by_label("Independent assertion observations")).to_contain_text("999")
        await expect(page.get_by_label("Independent assertion observations")).to_contain_text(
            "Addition returns the mathematical sum"
        )
        await page.get_by_text("Requirement provenance and assumptions", exact=True).click()
        await expect(page.get_by_label("Independent assertion observations")).to_contain_text(
            "Synthetic arithmetic specification v1"
        )
        await expect(page.locator(".audit-result")).to_contain_text("tests passed")
        await page.screenshot(
            path=str(output / "ordinary-pass-independent-fail.png"), full_page=True
        )
        saved = (await client.get("/api/repository-audits/runs/" + audit_id)).json()
        downloaded = (
            await client.get("/api/repository-audits/runs/" + audit_id + "/evidence")
        ).json()
        assert saved == downloaded and saved["status"] == "assertions_failed"
        (output / "saved.json").write_text(json.dumps(saved, indent=2))
        await page.reload()
        await expect(page.locator(".audit-result [role=status]")).to_have_text("assertions failed")
        await page.get_by_label("External unified diff", exact=True).fill(patch + "\n")
        await expect(page.get_by_label("External audit result")).to_have_count(0)
        await expect(page.get_by_label("Independent verification plan")).to_have_count(0)
        assert not errors
        await browser.close()
