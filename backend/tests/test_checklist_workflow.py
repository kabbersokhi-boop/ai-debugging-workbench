"""Real browser/terminal parity and a second patch reusing the same project checklist."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workbench.config import ROOT, settings
from workbench.db import RepositorySource
from workbench.repository_audit.cli import approval_id
from workbench.repository_audit.intake import summary
from workbench.repository_audit.service import validate_saved

EXAMPLES = ROOT / "evaluation/repository-examples/g2"
ACCEPTED = ROOT / "docs/reports/assets/generalized-patch-audit-g02/accepted"
BASE = "http://127.0.0.1:8010"


async def cli(*args, code=0):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "workbench.repository_audit.cli",
        *map(str, args),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(ROOT / "backend/src")},
    )
    stdout, stderr = await process.communicate()
    assert process.returncode == code, (stdout.decode()[-3000:], stderr.decode()[-3000:])
    return stdout.decode()


@pytest.mark.integration
@pytest.mark.parametrize("language", ["python", "node"])
async def test_checklist_export_browser_cli_parity_and_second_patch(tmp_path, language):
    retained = next(
        p
        for p in ACCEPTED.glob(f"{language}-positive-*.json")
        if "review" not in p.name and "validation" not in p.name
    )
    source = json.loads(retained.read_text())["evidence"]["snapshot"]
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
            viewport={"width": 1440, "height": 1000}, accept_downloads=True
        )
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.goto(BASE + f"/?source=external&prepared={language}-positive")
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value(
            f"{language}-positive"
        )
        await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        await page.get_by_role("button", name="Prepare exact plan for approval", exact=True).click()
        await page.get_by_label("Checklist name", exact=True).fill("Reusable function contract")
        async with page.expect_download() as download:
            await page.get_by_role(
                "button", name="Download reusable project checklist", exact=True
            ).click()
        checklist_file = tmp_path / "project-checklist.json"
        await (await download.value).save_as(checklist_file)
        checklist = json.loads(checklist_file.read_text())
        assert checklist["revision"] == 1 and checklist["version"] == "project-checklist-v1"
        assert "approval" not in checklist["requirements"][0]
        panel = page.get_by_label("Reusable project checklist", exact=True)
        await panel.get_by_label("Project checklist file", exact=True).set_input_files(
            checklist_file
        )
        await expect(panel.get_by_role("status")).to_have_text("Checklist compatible")
        await expect(
            panel.get_by_role("button", name="Prepare checklist plans for review")
        ).to_be_disabled()
        # Verify imported checklist review on mobile and by keyboard.
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        review = panel.get_by_label("Approve checklist requirements", exact=True)
        await review.focus()
        await page.keyboard.press("Space")
        await page.set_viewport_size({"width": 1440, "height": 1000})
        await panel.get_by_role("button", name="Prepare checklist plans for review").click()
        await expect(
            page.get_by_role("button", name="Validate independent checker", exact=True)
        ).to_be_disabled()
        await page.get_by_text("I approve running this plan's positive", exact=False).click()
        await page.get_by_role("button", name="Validate independent checker", exact=True).click()
        await expect(
            page.get_by_label("Approve validated independent plan", exact=True)
        ).to_be_visible(timeout=60000)
        await page.get_by_label("Approve validated independent plan", exact=True).check()
        await page.get_by_text("I reviewed this exact source, patch and plan", exact=False).click()
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/runs") and r.request.method == "POST"
        ) as started:
            await page.get_by_role(
                "button", name="Run ordinary and independent checks", exact=True
            ).click()
        browser_id = (await (await started.value).json())["id"]
        region = page.get_by_label("External audit result", exact=True)
        await expect(region.get_by_role("status")).to_have_text("completed", timeout=60000)
        browser_audit = (
            await client.get(f"/api/repository-audits/runs/{browser_id}/evidence")
        ).json()
        validate_saved(browser_audit["evidence"], UUID(browser_id))
        async with page.expect_download() as report_download:
            await region.get_by_role("link", name="Download readable report", exact=True).click()
        report_text = await asyncio.to_thread(
            Path(await (await report_download.value).path()).read_text
        )
        assert (
            "Reused project checklist" in report_text
            and "Reusable function contract" in report_text
        )
        assert all(
            label in report_text
            for label in (
                "Why this expectation is justified:",
                "Expected behavior:",
                "Actual observation:",
            )
        )
        # Same source/checklist/patch through the CLI must compile identical exact plans.
        positive_validation = ""
        for key, expected_status, exit_code in (
            (f"{language}-positive", "completed", 0),
            (f"{language}-negative", "assertions_failed", 1),
        ):
            preparation_file = tmp_path / f"{key}-preparation.json"
            out = tmp_path / key
            await cli(
                "prepare",
                "--checklist",
                checklist_file,
                "--patch",
                EXAMPLES / f"{key}.patch",
                "--commit",
                source["base_commit"],
                "--snapshot-id",
                source["id"],
                "--approve-requirements",
                "--out",
                preparation_file,
            )
            prepared = json.loads(preparation_file.read_text())
            fingerprint = approval_id(prepared)
            controls_out = await cli(
                "controls",
                "--preparation",
                preparation_file,
                "--approve-exact",
                fingerprint,
                "--out-dir",
                out,
            )
            validation_id = json.loads(controls_out.splitlines()[-1])["audit_id"]
            if key == f"{language}-negative":
                # An earlier patch's validation cannot authorize this candidate.
                stale = await client.post(
                    "/api/repository-audits/runs",
                    json={
                        "candidate_id": prepared["checklist_use"]["candidate_id"],
                        "plan_id": prepared["ordinary"]["id"],
                        "verification_id": prepared["verification"]["id"],
                        "checklist_use_id": prepared["checklist_use"]["id"],
                        "validation_run_id": positive_validation,
                        "approve_exact_plan": True,
                        "approve_independent_plan": True,
                        "confirm_local_execution": True,
                    },
                )
                assert stale.status_code == 409
            execution_out = await cli(
                "run",
                "--preparation",
                preparation_file,
                "--approve-exact",
                fingerprint,
                "--validation",
                validation_id,
                "--out-dir",
                out,
                code=exit_code,
            )
            audit_id = json.loads(execution_out.splitlines()[-1])["audit_id"]
            audit = json.loads((out / f"{audit_id}.json").read_text())
            assert audit["status"] == expected_status
            validate_saved(audit["evidence"], UUID(audit_id))
            assert (out / f"{audit_id}.md").read_text() == (
                await client.get(f"/api/repository-audits/runs/{audit_id}/report")
            ).text
            assert (out / f"{audit_id}.patch").read_text() == (
                EXAMPLES / f"{key}.patch"
            ).read_text()
            if key == f"{language}-positive":
                positive_validation = validation_id
                for field in ("snapshot", "candidate", "plan", "verification", "checklist_use"):
                    assert audit["evidence"][field] == browser_audit["evidence"][field]
                assert (
                    audit["evidence"]["result"]["independent"]["checks"]
                    == browser_audit["evidence"]["result"]["independent"]["checks"]
                )
            else:
                assert (
                    audit["evidence"]["checklist_use"]["checklist_id"]
                    == browser_audit["evidence"]["checklist_use"]["checklist_id"]
                )
                assert audit["evidence"]["plan"] != browser_audit["evidence"]["plan"]
                assert audit["evidence"]["result"]["ordinary"]["status"] == "tests_passed"
        # An explicitly incompatible revision must be visible and unapprovable.
        outdated = {
            **checklist,
            "supported_sources": [{**checklist["supported_sources"][0], "base_commit": "a" * 40}],
        }
        outdated_file = tmp_path / "outdated.json"
        outdated_file.write_text(json.dumps(outdated))
        await panel.get_by_label("Project checklist file", exact=True).set_input_files(
            outdated_file
        )
        await expect(panel.get_by_role("status")).to_have_text("Checklist outdated")
        await expect(
            panel.get_by_label("Approve checklist requirements", exact=True)
        ).to_be_disabled()
        assert not errors, errors
        await browser.close()
