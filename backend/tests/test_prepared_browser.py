"""Product acceptance: real local execution of accepted G2 examples, not a new campaign.

Only public-source transport is replayed for deterministic CI; admission, approval,
validation, execution, downloads and saved history use the real API/DB/broker/Docker.
G4_LIVE_SOURCE=1 instead exercises the bounded upstream source adapter locally.
"""

import asyncio
import copy
import json
import os
from pathlib import Path

import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench.config import ROOT, settings
from workbench.db import RepositorySource
from workbench.repository_audit.intake import decode_files, summary
from workbench.repository_audit.service import validate_saved

BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")
OUT = ROOT / "artifacts/g4"
ACCEPTED = ROOT / "docs/reports/assets/generalized-patch-audit-g02/accepted"
EXAMPLES = ROOT / "evaluation/repository-examples/g2"
MISSED = "m02-v2-development-boltons-addlist-nemotron3-r02"


@pytest.mark.integration
@pytest.mark.parametrize("key", ["python-positive", "node-positive"])
async def test_prepared_example_without_json_editing(key):
    example = next(
        x
        for x in json.loads((EXAMPLES / "examples.json").read_text())["examples"]
        if x["key"] == key
    )
    retained = next(
        p
        for p in ACCEPTED.glob(key + "-*.json")
        if "review" not in p.name and "validation" not in p.name
    )
    source = json.loads(retained.read_text())["evidence"]["snapshot"]
    decode_files(source)
    live = os.environ.get("G4_LIVE_SOURCE") == "1"
    output = ROOT / "artifacts/prepared-workflow" / key
    output.mkdir(parents=True, exist_ok=True)
    if not live:
        db = create_async_engine(settings.database_url)
        try:
            async with async_sessionmaker(db).begin() as session:
                if await session.get(RepositorySource, source["id"]) is None:
                    session.add(RepositorySource(id=source["id"], record=source))
        finally:
            await db.dispose()
    async with async_playwright() as p, httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1050}, accept_downloads=True
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        if not live:
            await page.route(
                "**/api/repository-audits/sources",
                lambda route: route.fulfill(json=summary(source)),
            )
        await page.goto(BASE + "/?source=external")
        await expect(
            page.get_by_role("heading", name="Audit a completed patch", exact=True)
        ).to_be_visible()
        await page.screenshot(path=str(output / "intake-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(path=str(output / "intake-mobile.png"))
        await page.set_viewport_size({"width": 1440, "height": 1050})
        await page.get_by_label("Prepared example", exact=True).select_option(key)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await page.get_by_role("button", name="Fetch source for review", exact=True).focus()
        await expect(
            page.get_by_role("button", name="Fetch source for review", exact=True)
        ).to_be_focused()
        await page.set_viewport_size({"width": 1440, "height": 1050})
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/sources") and r.request.method == "POST"
        ) as admission:
            await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        response = await admission.value
        assert response.status == 201 if live else response.status == 200, await response.text()
        admitted = await response.json()
        assert admitted["base_commit"] == example["base_commit"]
        assert admitted["source_tree_hash"] == source["source_tree_hash"]
        await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        await expect(page.get_by_label("External candidate review", exact=True)).to_be_visible()
        compare = page.get_by_text("Compare " + example["module"], exact=True)
        await expect(page.get_by_label("Read-only candidate diff", exact=True)).to_have_count(0)
        await compare.focus()
        await page.keyboard.press("Enter")
        await expect(page.get_by_label("Read-only candidate diff", exact=True)).to_be_visible()
        await page.keyboard.press("Enter")
        await expect(page.get_by_label("Read-only candidate diff", exact=True)).to_have_count(0)
        await page.get_by_role("button", name="Prepare exact plan for approval", exact=True).click()
        req = copy.deepcopy(example["requirement"])
        await expect(page.get_by_label("Prepared requirements and checks")).to_contain_text(
            req["statement"]
        )
        await expect(
            page.get_by_role("button", name="Prepare independent plan", exact=True)
        ).to_be_disabled()
        await page.get_by_text("I reviewed the provenance", exact=False).click()
        await page.get_by_label(
            "Independent verification plan", exact=True
        ).scroll_into_view_if_needed()
        await page.screenshot(path=str(output / "requirements.png"))
        await page.get_by_role("button", name="Prepare independent plan", exact=True).click()
        await expect(
            page.get_by_role("button", name="Validate independent checker", exact=True)
        ).to_be_disabled()
        await page.get_by_text("I approve running this plan's positive", exact=False).click()
        await page.get_by_role("button", name="Validate independent checker", exact=True).click()
        await expect(
            page.get_by_label("Approve validated independent plan", exact=True)
        ).to_be_visible(timeout=60000)
        run = page.get_by_role("button", name="Run ordinary and independent checks", exact=True)
        await expect(run).to_be_disabled()
        await page.get_by_label("Approve validated independent plan", exact=True).check()
        await page.get_by_text("I reviewed this exact source, patch and plan", exact=False).click()
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/runs") and r.request.method == "POST"
        ) as execution:
            await run.click()
        audit_id = (await (await execution.value).json())["id"]
        region = page.get_by_label("External audit result", exact=True)
        await expect(region.get_by_role("status")).to_have_text("completed", timeout=60000)
        await expect(region).to_contain_text("tests passed")
        await expect(region).to_contain_text("Passed the declared checks")
        await expect(region).to_contain_text(example["base_commit"])
        await region.scroll_into_view_if_needed()
        await page.screenshot(path=str(output / "result-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await region.scroll_into_view_if_needed()
        await page.screenshot(path=str(output / "result-mobile.png"))
        async with page.expect_download() as download:
            await region.get_by_role(
                "link", name="Download repository evidence", exact=True
            ).click()
        value = json.loads(
            await asyncio.to_thread(Path(await (await download.value).path()).read_text)
        )
        fetched = (await client.get(f"/api/repository-audits/runs/{audit_id}")).json()
        assert value == fetched and value["status"] == "completed"
        validate_saved(value["evidence"], audit_id)
        approved_requirement = value["evidence"]["verification"]["requirements"][0]
        assert {k: approved_requirement[k] for k in req} == req
        approved_assertions = value["evidence"]["verification"]["plan"]["assertions"]
        assert [
            {k: a[k] for k in expected}
            for a, expected in zip(approved_assertions, example["assertions"], strict=True)
        ] == example["assertions"]
        # A new edit after successful validation and execution cannot reuse exact approval.
        await page.get_by_text("I reviewed this exact source, patch and plan", exact=False).click()
        await expect(run).to_be_enabled()
        await page.get_by_text("Advanced requirement configuration", exact=True).click()
        await page.get_by_label("Required behavior", exact=True).fill(
            req["statement"] + " changed scope"
        )
        await expect(page.get_by_label("Independent validation result", exact=True)).to_have_count(
            0
        )
        await expect(
            page.get_by_label("Approve validated independent plan", exact=True)
        ).to_have_count(0)
        await expect(run).to_be_disabled()
        await expect(
            page.get_by_role(
                "checkbox",
                name="I reviewed this exact source, patch and plan, and approve local execution.",
                exact=True,
            )
        ).not_to_be_checked()
        await expect(region).to_have_count(0)
        await page.reload()
        await expect(region.get_by_role("status")).to_have_text("completed")
        # Reopen from discoverable history after navigating away from this result.
        await page.get_by_label("GitHub owner/repository", exact=True).fill("other/project")
        await expect(region).to_have_count(0)
        await page.locator("#repository-history button").filter(has_text=audit_id).click()
        await expect(region.get_by_role("status")).to_have_text("completed")
        reopened = (await client.get(f"/api/repository-audits/runs/{audit_id}/evidence")).json()
        assert reopened == value
        (output / "evidence.json").write_text(json.dumps(value, indent=2) + "\n")
        (output / "journey.json").write_text(
            json.dumps(
                {
                    "example": key,
                    "source_transport": "live GitHub"
                    if live
                    else "retained accepted public snapshot; source response replayed",
                    "fresh_execution": True,
                    "audit_id": audit_id,
                    "status": value["status"],
                    "history_and_download_exact": True,
                    "console_errors": errors,
                },
                indent=2,
            )
            + "\n"
        )
        # A new example cannot inherit the saved candidate/plan or final exact approval.
        final_approval = page.get_by_role(
            "checkbox", name="I reviewed this exact source, patch and plan"
        )
        await final_approval.check()
        await expect(final_approval).to_be_checked()
        other = "node-positive" if key == "python-positive" else "python-positive"
        await page.get_by_label("Prepared example", exact=True).select_option(other)
        await expect(page.get_by_label("External candidate review", exact=True)).to_have_count(0)
        await expect(region).to_have_count(0)
        await expect(final_approval).to_have_count(0)
        await expect(page.get_by_label("Independent validation result", exact=True)).to_have_count(
            0
        )
        await expect(
            page.get_by_label("Approve validated independent plan", exact=True)
        ).to_have_count(0)
        await expect(
            page.get_by_role("button", name="Run ordinary and independent checks", exact=True)
        ).to_have_count(0)
        assert not errors, errors
        await browser.close()


@pytest.mark.integration
async def test_boltons_guided_saved_playback_keyboard_mobile_and_no_execution():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        mutations = []
        page.on(
            "request",
            lambda request: (
                mutations.append(request.url)
                if request.method not in {"GET", "HEAD", "OPTIONS"}
                else None
            ),
        )
        await page.goto(BASE + "/recorded/?recordedAudit=" + MISSED)
        guide = page.get_by_label("Guided Boltons walkthrough", exact=True)
        await expect(guide).to_contain_text("155 selected existing tests")
        await expect(guide).to_contain_text("SAVED PLAYBACK")
        next_button = guide.get_by_role("button", name="Next", exact=True)
        await next_button.focus()
        await page.keyboard.press("Enter")
        await expect(guide.get_by_role("heading", level=2)).to_have_text(
            "A second implementation was overlooked"
        )
        await expect(guide).to_contain_text("boltons/urlutils.py")
        await expect(guide.locator("pre")).to_contain_text("dictutils.py")
        await page.keyboard.press("Enter")
        await expect(guide).to_contain_text("Expected behavior")
        await expect(guide).to_contain_text("Actual behavior")
        await expect(guide).to_contain_text('"length": 1')
        await expect(next_button).to_be_disabled()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await guide.get_by_role("button", name="Previous", exact=True).click()
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        assert not mutations, mutations
        await browser.close()
