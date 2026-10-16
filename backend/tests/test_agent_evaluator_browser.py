import asyncio
import json
import os
import re
from pathlib import Path

import httpx
import pytest
from playwright.async_api import async_playwright, expect

from workbench.config import ROOT

pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8010")


async def test_evaluator_real_ui_candidates_failure_evidence_and_reopen():
    folder = ROOT / "artifacts/evaluator/ui"
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(BASE_URL)
        await page.get_by_role("link", name="Agent Evaluation", exact=True).click()
        await expect(
            page.get_by_role("heading", name="Agent Evaluation", exact=True)
        ).to_be_visible()
        for task_id in ("more-bucket", "boltons-addlist"):
            for label in ("negative", "nvidia-01"):
                await page.get_by_label("Software task").select_option(task_id)
                await page.get_by_label("Candidate patch").select_option(task_id + "-" + label)
                await expect(
                    page.get_by_role("button", name="Run evaluation", exact=True)
                ).to_be_enabled()
                async with page.expect_response(
                    lambda r: r.request.method == "POST" and r.url.endswith("/api/evaluator/runs")
                ) as response:
                    await page.get_by_role("button", name="Run evaluation", exact=True).click()
                run_id = (await (await response.value).json())["id"]
                await expect(
                    page.get_by_role("region", name="Evaluation result").get_by_role("status")
                ).to_have_text(
                    "failed" if label == "negative" else re.compile("^(passed|failed)$"),
                    timeout=90000,
                )
                await expect(
                    page.get_by_text("Ordinary repository checks", exact=True)
                ).to_be_visible()
                await expect(
                    page.get_by_text("Independent behavioral checks", exact=True)
                ).to_be_visible()
                if label == "negative":
                    await expect(
                        page.get_by_text("Ordinary checks passed.", exact=False)
                    ).to_be_visible()
                    assert await page.locator(".evaluation-checks details[open]").count() > 0
                await page.screenshot(path=folder / f"{task_id}-{label}.png", full_page=True)
                await page.get_by_role("region", name="Evaluation result").screenshot(
                    path=folder / f"{task_id}-{label}-result.png"
                )
                async with page.expect_download() as download:
                    await page.get_by_role(
                        "link", name="Download complete evaluation evidence"
                    ).click()
                saved = await (await download.value).path()
                evidence = json.loads(await asyncio.to_thread(Path(saved).read_text))
                assert evidence["id"] == run_id
                assert (
                    evidence["candidate_hash"]
                    == evidence["evidence"]["result"]["binding"]["candidate_hash"]
                )
                await asyncio.to_thread(
                    (folder / f"{task_id}-{label}.json").write_text,
                    json.dumps(evidence, indent=2) + "\n",
                )
                await page.reload()
                await expect(
                    page.get_by_role("region", name="Evaluation result").get_by_role("status")
                ).to_have_text(evidence["status"], timeout=15000)
                # Reopening the exact saved link reads persisted evidence without creating a run.
                async with httpx.AsyncClient(base_url=BASE_URL) as client:
                    stored = (await client.get(f"/api/evaluator/runs/{run_id}")).json()
                assert stored == evidence
                if task_id == "more-bucket" and label == "negative":
                    await page.get_by_text("Open code comparison", exact=False).first.click()
                    await expect(page.locator(".monaco-diff-editor")).to_be_visible(timeout=20000)
                    await page.screenshot(path=folder / "candidate-diff.png", full_page=True)
                    await page.set_viewport_size({"width": 390, "height": 844})
                    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    await page.screenshot(path=folder / "failure-mobile.png", full_page=True)
                    await page.set_viewport_size({"width": 1440, "height": 1100})
        assert not errors, errors
        await browser.close()


async def test_evaluator_api_rejects_arbitrary_inputs_and_cancels():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        response = await client.post(
            "/api/evaluator/runs", json={"candidate_id": "../../etc/passwd"}
        )
        assert response.status_code == 422
        response = await client.post(
            "/api/evaluator/runs",
            json={"candidate_id": "more-bucket-reference", "command": "anything"},
        )
        assert response.status_code == 422
        response = await client.post(
            "/api/evaluator/runs", json={"candidate_id": "more-bucket-reference"}
        )
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert (await client.post(f"/api/evaluator/runs/{run_id}/cancel")).status_code == 200
        async with asyncio.timeout(70):
            while True:
                saved = (await client.get(f"/api/evaluator/runs/{run_id}")).json()
                if saved["status"] != "running":
                    break
                await asyncio.sleep(0.2)
        assert saved["status"] == "cancelled", saved
