"""Actual Docker generation, reduction and fresh reproduction on authored controls."""

import copy
import json
from uuid import UUID

import httpx
import pytest
from playwright.async_api import async_playwright, expect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_checklist_workflow import ACCEPTED, BASE, EXAMPLES, cli

from workbench.config import ROOT, settings
from workbench.db import RepositorySource
from workbench.evaluator.catalog import identity
from workbench.repository_audit.cli import approval_id
from workbench.repository_audit.intake import summary
from workbench.repository_audit.service import validate_saved


@pytest.mark.integration
async def test_generated_positive_browser_negative_cli_reduction_and_explicit_replay(tmp_path):
    retained = next(
        p
        for p in ACCEPTED.glob("python-positive-*.json")
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
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.route(
            "**/api/repository-audits/sources", lambda route: route.fulfill(json=summary(source))
        )
        await page.goto(BASE + "/?source=external&prepared=python-positive")
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value(
            "python-positive"
        )
        await page.get_by_role("button", name="Fetch source for review", exact=True).click()
        await page.get_by_role("button", name="Admit patch for review", exact=True).click()
        await page.get_by_role("button", name="Prepare exact plan for approval", exact=True).click()
        await page.get_by_label("Generate bounded Python checks", exact=True).check()
        section = page.get_by_label("Generated Python verification", exact=True)
        await expect(
            section.get_by_role("button", name="Prepare generated verification plan")
        ).to_be_disabled()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        review = page.get_by_label("Approve generated property", exact=True)
        await review.focus()
        await page.keyboard.press("Space")
        await page.set_viewport_size({"width": 1440, "height": 1050})
        await page.get_by_role(
            "button", name="Prepare generated verification plan", exact=True
        ).click()
        await expect(
            page.get_by_role("button", name="Validate generated checker", exact=True)
        ).to_be_disabled()
        await page.get_by_label("Approve generated controls", exact=True).check()
        await page.get_by_role("button", name="Validate generated checker", exact=True).click()
        await expect(
            page.get_by_label("Approve validated generated plan", exact=True)
        ).to_be_visible(timeout=60000)
        await page.get_by_label("Approve validated generated plan", exact=True).check()
        await page.get_by_text("I reviewed this exact source, patch and plan", exact=False).click()
        async with page.expect_response(
            lambda r: r.url.endswith("/repository-audits/runs") and r.request.method == "POST"
        ) as response:
            await page.get_by_role(
                "button", name="Run ordinary and independent checks", exact=True
            ).click()
        positive_id = (await (await response.value).json())["id"]
        region = page.get_by_label("External audit result", exact=True)
        await expect(region.get_by_role("status")).to_have_text("completed", timeout=60000)
        await expect(page.get_by_label("Generated failure evidence", exact=True)).to_contain_text(
            "Passed the declared generated cases only"
        )
        positive = (await client.get(f"/api/repository-audits/runs/{positive_id}/evidence")).json()
        validate_saved(positive["evidence"], UUID(positive_id))
        assert (
            positive["evidence"]["verification"]["plan"]["verifier_version"] == "json-generated-v3"
        )
        # A generated-property edit discards exact approval and all previous controls.
        await section.locator("summary").filter(has_text="Generation and reduction limits").click()
        await page.get_by_label("Generation seed", exact=True).fill("2")
        await expect(
            page.get_by_label("Approve validated generated plan", exact=True)
        ).to_have_count(0)
        await expect(
            page.get_by_label("Approve generated property", exact=True)
        ).not_to_be_checked()
        await expect(
            page.get_by_role("button", name="Run ordinary and independent checks", exact=True)
        ).to_be_disabled()
        # The accepted authored negative passes upstream tests but skips truthy strings.
        base = tmp_path / "negative-base.json"
        await cli(
            "prepare",
            "--checklist",
            ROOT / "examples/checklists/python-first-v1.json",
            "--patch",
            EXAMPLES / "python-negative.patch",
            "--commit",
            source["base_commit"],
            "--snapshot-id",
            source["id"],
            "--approve-requirements",
            "--out",
            base,
        )
        search = ROOT / "examples/generation/first-truthy-v3.json"
        generated_file = tmp_path / "generated.json"
        await cli(
            "generated-prepare",
            "--preparation",
            base,
            "--search",
            search,
            "--approve-property",
            "--out",
            generated_file,
        )
        prepared = json.loads(generated_file.read_text())
        out = tmp_path / "evidence"
        controls = await cli(
            "controls",
            "--preparation",
            generated_file,
            "--approve-exact",
            approval_id(prepared),
            "--out-dir",
            out,
        )
        validation_id = json.loads(controls.splitlines()[-1])["audit_id"]
        executed = await cli(
            "run",
            "--preparation",
            generated_file,
            "--approve-exact",
            approval_id(prepared),
            "--validation",
            validation_id,
            "--out-dir",
            out,
            code=1,
        )
        negative_id = json.loads(executed.splitlines()[-1])["audit_id"]
        negative = json.loads((out / f"{negative_id}.json").read_text())
        validate_saved(negative["evidence"], UUID(negative_id))
        result = negative["evidence"]["result"]
        case = result["counterexample"]
        assert (
            negative["status"] == "assertions_failed"
            and result["ordinary"]["status"] == "tests_passed"
        )
        assert case["input"] == ["a"] and case["expected"] == "a" and case["observed"] is None
        assert case["reduced"] and case["fresh_reproductions"] == 2
        container_ids = [result["ordinary"]["container_id"]] + [
            r["execution"]["container_id"] for r in result["generated_runs"]
        ]
        assert len(container_ids) == len(set(container_ids))
        # A client cannot invent reduction evidence by simply recomputing its JSON hash.
        tampered = copy.deepcopy(negative["evidence"])
        tampered["result"]["counterexample"]["input"] = ["forged"]
        tampered["result_hash"] = identity(tampered["result"])
        with pytest.raises(ValueError):
            validate_saved(tampered, UUID(negative_id))
        tampered = copy.deepcopy(negative["evidence"])
        tampered["result"]["generated_runs"].pop()
        tampered["result_hash"] = identity(tampered["result"])
        with pytest.raises(ValueError):
            validate_saved(tampered, UUID(negative_id))
        await page.goto(BASE + f"/?source=external&repositoryAudit={negative_id}")
        display = page.get_by_label("Generated failure evidence", exact=True)
        await expect(display).to_contain_text("Reproduced failing input")
        await expect(display).to_contain_text("Why this matters")
        await expect(display).to_contain_text('"a"')
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        report = (out / f"{negative_id}.md").read_text()
        assert "Reproduced counterexample" in report and "globally smallest" in report
        # Replay the exact reduced input as a newly approved plan and fresh audit.
        replay_file = tmp_path / "replay.json"
        await cli(
            "generated-prepare",
            "--preparation",
            base,
            "--search",
            search,
            "--replay-audit",
            negative_id,
            "--approve-property",
            "--out",
            replay_file,
        )
        replay_prepared = json.loads(replay_file.read_text())
        assert replay_prepared["verification"]["plan"]["search"]["replay_inputs"] == [["a"]]
        validation = await cli(
            "controls",
            "--preparation",
            replay_file,
            "--approve-exact",
            approval_id(replay_prepared),
            "--out-dir",
            out,
        )
        replay_validation = json.loads(validation.splitlines()[-1])["audit_id"]
        replay_execution = await cli(
            "run",
            "--preparation",
            replay_file,
            "--approve-exact",
            approval_id(replay_prepared),
            "--validation",
            replay_validation,
            "--out-dir",
            out,
            code=1,
        )
        replay_id = json.loads(replay_execution.splitlines()[-1])["audit_id"]
        replay = json.loads((out / f"{replay_id}.json").read_text())
        validate_saved(replay["evidence"], UUID(replay_id))
        assert replay_id != negative_id and replay["evidence"]["result"]["counterexample"][
            "input"
        ] == ["a"]
        assert replay["evidence"]["result"]["counterexample"]["fresh_reproductions"] == 2
        assert not errors, errors
        artifacts = ROOT / "artifacts/generated-verifier-v3"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "authored-negative.json").write_text(json.dumps(negative, indent=2) + "\n")
        (artifacts / "authored-negative.md").write_text(report)
        (artifacts / "reproduction.json").write_text(json.dumps(replay, indent=2) + "\n")
        await display.scroll_into_view_if_needed()
        await page.screenshot(path=str(artifacts / "failure-mobile.png"))
        await browser.close()
