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
async def test_g4_accepted_example_guided_approval_execution_download_history(key):
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
    output = OUT / ("live-source" if live else "fixture-transport") / key
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
        await page.get_by_label("GitHub owner/repository", exact=True).fill(example["repository"])
        await page.get_by_label("Immutable base commit", exact=True).fill(example["base_commit"])
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/sources") and r.request.method == "POST"
        ) as admission:
            await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        response = await admission.value
        assert response.status == 201 if live else response.status == 200, await response.text()
        admitted = await response.json()
        assert admitted["base_commit"] == example["base_commit"]
        assert admitted["source_tree_hash"] == source["source_tree_hash"]
        await page.get_by_label("Approved production file scope", exact=True).select_option(
            example["module"]
        )
        await page.get_by_label("External unified diff", exact=True).fill(
            (EXAMPLES / example["patch"]).read_text()
        )
        await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        await expect(page.get_by_label("External candidate review", exact=True)).to_be_visible()
        await page.get_by_label("Runtime preset", exact=True).select_option(example["runtime"])
        await page.get_by_label("Test command arguments", exact=True).fill(
            json.dumps(example["tests"])
        )
        await page.get_by_label("Selected test scope", exact=True).fill(
            "G4 product acceptance · unchanged selected upstream tests"
        )
        await page.get_by_role("button", name="Prepare exact plan for approval", exact=True).click()
        await expect(
            page.get_by_text("Independent checks not configured.", exact=False).first
        ).to_be_visible()
        await page.get_by_label("Add independent verification", exact=True).check()
        await page.get_by_role("button", name="Advanced JSON", exact=True).click()
        req = copy.deepcopy(example["requirement"])
        await page.get_by_label("Independent requirements", exact=True).fill(json.dumps([req]))
        await page.get_by_role("button", name="Guided requirement", exact=True).click()
        await expect(page.get_by_label("Required behavior", exact=True)).to_have_value(
            req["statement"]
        )
        await page.get_by_text("I reviewed the provenance", exact=False).click()
        # Guided edits invalidate approval; advanced details survive round-trip unchanged.
        await page.get_by_label("Required behavior", exact=True).fill(req["statement"] + " ")
        await expect(
            page.get_by_role("button", name="Prepare independent plan", exact=True)
        ).to_be_disabled()
        await page.get_by_label("Required behavior", exact=True).fill(req["statement"])
        await page.get_by_role("button", name="Advanced JSON", exact=True).click()
        authored = json.loads(
            await page.get_by_label("Independent requirements", exact=True).input_value()
        )
        assert authored == [req]
        await page.get_by_role("button", name="Guided requirement", exact=True).click()
        await page.get_by_text("I reviewed the provenance", exact=False).click()
        await page.get_by_label("Independent target file", exact=True).fill(example["module"])
        await page.get_by_label("Public function export", exact=True).fill(example["export"])
        for assertion in example["assertions"]:
            await page.get_by_label("Example name", exact=True).fill(assertion["id"])
            await page.get_by_label("Function arguments", exact=True).fill(
                json.dumps(assertion["args"])
            )
            await page.get_by_label("Expected JSON result", exact=True).fill(
                json.dumps(assertion["expected"])
            )
            await page.get_by_role("button", name="Add named example", exact=True).click()
            await expect(page.get_by_label("Declared assertions", exact=True)).to_contain_text(
                assertion["id"]
            )
        await page.get_by_role("button", name="Advanced JSON", exact=True).click()
        authored_assertions = json.loads(
            await page.get_by_label("Named assertions", exact=True).input_value()
        )
        assert authored_assertions == [{**a, "requirement_index": 0} for a in example["assertions"]]
        await page.get_by_role("button", name="Guided requirement", exact=True).click()
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
        assert not errors, errors
        await browser.close()


@pytest.mark.integration
async def test_g4_unsupported_preview_and_keyboard_mobile():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(BASE + "/?source=external")
        await expect(
            page.get_by_role("heading", name="Audit a completed patch", exact=True)
        ).to_be_visible()
        await page.keyboard.press("Tab")
        await expect(page.get_by_role("link", name="Skip to audit content")).to_be_focused()
        await page.get_by_text("Start from a public GitHub pull request", exact=False).click()
        await page.get_by_label("Public GitHub PR URL", exact=True).fill("http://127.0.0.1/private")
        await page.get_by_role("button", name="Preview public PR", exact=True).click()
        await expect(page.get_by_role("alert")).to_contain_text("Preview unavailable")
        await expect(page.get_by_label("External audit result", exact=True)).to_have_count(0)
        await page.get_by_role("alert").scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT / "unsupported-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await page.get_by_role("alert").scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT / "unsupported-mobile.png"))
        await browser.close()


@pytest.mark.e2e
async def test_recorded_explorer_first_g4_boltons_provenance_and_mobile_boundary():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        mutations, errors = [], []
        page.on(
            "request",
            lambda r: mutations.append(r.url) if r.method not in ("GET", "HEAD") else None,
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(BASE + "/recorded/?recordedAudit=" + MISSED)
        region = page.get_by_label("Patch audit result", exact=True)
        await expect(region.get_by_role("status")).to_have_text("failed")
        await expect(page.get_by_label("Evidence provenance", exact=True)).to_contain_text(
            "Zero additional independent discoveries"
        )
        await page.screenshot(path=str(OUT / "recorded-intro-desktop.png"))
        await region.scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT / "boltons-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await page.evaluate("scrollTo(0,0)")
        await page.screenshot(path=str(OUT / "recorded-intro-mobile.png"))
        await region.scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT / "boltons-mobile.png"))
        async with page.expect_download() as download:
            await region.get_by_role("link", name="Download audit evidence", exact=True).click()
        value = json.loads(
            await asyncio.to_thread(Path(await (await download.value).path()).read_text)
        )
        assert value["id"] == MISSED and value["execution_mode"] == "recorded"
        assert value["evidence"]["candidate"]["provenance"]["category"] == "retained_model"
        assert not await page.get_by_role("button", name="Preview public PR", exact=True).count()
        assert not await page.get_by_role("button", name="Run fresh audit", exact=True).count()
        # The featured-case action must select the missed fix even after browsing
        # the passing record; an anchor into whichever record is selected is misleading.
        await page.get_by_label("Saved patch audit", exact=True).select_option(
            "m02-v1-boltons-addlist-nemotron35-r02"
        )
        await expect(region.get_by_role("status")).to_have_text("passed")
        featured = page.get_by_role("link", name="Explore the real missed fix", exact=True)
        await featured.focus()
        await page.keyboard.press("Enter")
        await expect(region.get_by_role("status")).to_have_text("failed")
        assert "recordedAudit=" + MISSED in page.url
        await expect(region).to_be_in_viewport()
        assert not mutations and not errors, (mutations, errors)
        (OUT / "recorded-journey.json").write_text(
            json.dumps(
                {
                    "record": MISSED,
                    "execution": "replayed immutable authentic evidence",
                    "fresh_execution": False,
                    "mutation_requests": mutations,
                    "console_errors": errors,
                    "mobile_overflow": False,
                },
                indent=2,
            )
            + "\n"
        )
        await browser.close()


@pytest.mark.e2e
@pytest.mark.parametrize("action", ["edit_url", "manual_intake"])
async def test_g4_late_pr_preview_cannot_replace_edited_input(action):
    """Controlled transport race; no upstream network, source import or execution."""
    pending, release = asyncio.Event(), asyncio.Event()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async def delayed(route):
            pending.set()
            await release.wait()
            await route.fulfill(
                json={
                    "repository": "stale/repository",
                    "number": 1,
                    "title": "STALE PREVIEW",
                    "base_commit": "a" * 40,
                    "head_commit": "b" * 40,
                    "head_repository": "stale/repository",
                    "changed_files": 1,
                    "additions": 1,
                    "deletions": 0,
                    "observed_at": "2026-10-27T00:00:00Z",
                    "admission": "not_admitted",
                    "execution_authorized": False,
                    "limitation": "Controlled transport fixture",
                }
            )

        from test_repository_audit import fixture_source

        source = fixture_source()
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.route("**/api/repository-audits/github-preview", delayed)
        await page.goto(BASE + "/?source=external")
        await page.get_by_text("Start from a public GitHub pull request", exact=False).click()
        field = page.get_by_label("Public GitHub PR URL", exact=True)
        if action == "manual_intake":
            await page.get_by_label("GitHub owner/repository", exact=True).fill(
                source["repository"]
            )
            await page.get_by_label("Immutable base commit", exact=True).fill(source["base_commit"])
            await page.get_by_text("Start from a public GitHub pull request", exact=False).click()
        await field.fill("https://github.com/stale/repository/pull/1")
        await page.get_by_role("button", name="Preview public PR", exact=True).click()
        await asyncio.wait_for(pending.wait(), 5)
        if action == "edit_url":
            await field.fill("https://github.com/new/repository/pull/2")
        else:
            await page.get_by_role("button", name="Fetch source for review", exact=True).click()
            await expect(
                page.get_by_label("Approved production file scope", exact=True)
            ).to_be_visible()
        async with page.expect_response(lambda r: r.url.endswith("/github-preview")) as response:
            release.set()
        await (await response.value).finished()
        await page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        if action == "edit_url":
            await expect(field).to_have_value("https://github.com/new/repository/pull/2")
        await expect(page.get_by_label("GitHub PR preview", exact=True)).to_have_count(0)
        await expect(page.get_by_label("External audit result", exact=True)).to_have_count(0)
        await browser.close()


@pytest.mark.integration
async def test_g4_actual_rejected_test_patch_creates_no_audit():
    source = json.loads(next(ACCEPTED.glob("python-positive-50*.json")).read_text())["evidence"][
        "snapshot"
    ]
    db = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(db).begin() as session:
            if await session.get(RepositorySource, source["id"]) is None:
                session.add(RepositorySource(id=source["id"], record=source))
    finally:
        await db.dispose()
    async with async_playwright() as p, httpx.AsyncClient(base_url=BASE) as client:
        before = (await client.get("/api/repository-audits/runs")).json()
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.goto(BASE + "/?source=external")
        await page.get_by_label("GitHub owner/repository", exact=True).fill(source["repository"])
        await page.get_by_label("Immutable base commit", exact=True).fill(source["base_commit"])
        await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        await page.get_by_label("Approved production file scope", exact=True).select_option(
            "first.py"
        )
        rejected = (
            (EXAMPLES / "python-positive.patch")
            .read_text()
            .replace("a/first.py", "a/test_first.py")
            .replace("b/first.py", "b/test_first.py")
        )
        await page.get_by_label("External unified diff", exact=True).fill(rejected)
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/candidates")
        ) as admission:
            await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        assert (await admission.value).status == 422
        await expect(page.get_by_role("alert")).to_contain_text("patch rejected")
        await expect(page.get_by_label("External candidate review", exact=True)).to_have_count(0)
        await expect(page.get_by_label("External audit result", exact=True)).to_have_count(0)
        assert (await client.get("/api/repository-audits/runs")).json() == before
        await page.get_by_role("alert").scroll_into_view_if_needed()
        OUT.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(OUT / "rejected-patch-desktop.png"))
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        await page.get_by_role("alert").scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT / "rejected-patch-mobile.png"))
        (OUT / "rejected-patch.json").write_text(
            json.dumps(
                {
                    "transport": "retained accepted source fixture; actual API admission rejection",
                    "response": 422,
                    "runs_unchanged": True,
                    "candidate_created": False,
                    "execution_requested": False,
                },
                indent=2,
            )
            + "\n"
        )
        await browser.close()


@pytest.mark.e2e
@pytest.mark.parametrize("ordinary", ["tests_passed", "tests_failed"])
async def test_g4_result_summary_keeps_both_failure_outcomes_visible(ordinary):
    """UI contract fixture only; failure combinations are not new experimental results."""
    saved = next(
        p
        for p in ACCEPTED.glob("python-negative-*.json")
        if "review" not in p.name and "validation" not in p.name
    )
    audit = json.loads(saved.read_text())
    audit["evidence"]["result"]["ordinary"]["status"] = ordinary
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.route(
            "**/api/repository-audits/runs/" + audit["id"], lambda route: route.fulfill(json=audit)
        )
        await page.goto(BASE + "/?source=external&repositoryAudit=" + audit["id"])
        region = page.get_by_label("External audit result", exact=True)
        summary_text = (
            "Existing tests and independent behavioral checks failed"
            if ordinary == "tests_failed"
            else "Selected existing tests passed; an independent behavioral check failed"
        )
        await expect(region.locator(".audit-summary")).to_contain_text(summary_text)
        await expect(region).to_contain_text(ordinary.replace("_", " "))
        await browser.close()
