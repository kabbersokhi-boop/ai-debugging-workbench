"""Opt-in actual browser walkthrough of the declared real G1 GitHub examples."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from playwright.async_api import async_playwright, expect
from workbench.repository_audit.execution import validate
from workbench.repository_audit.intake import decode_files


async def main(args):
    manifest_path = await asyncio.to_thread(Path(args.manifest).resolve)
    manifest = json.loads(await asyncio.to_thread(manifest_path.read_text))
    output = await asyncio.to_thread(Path(args.output).resolve)
    await asyncio.to_thread(output.mkdir, parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for example in manifest["examples"]:
            if args.example and args.example != example["key"]:
                continue
            key = example["key"]
            await page.goto(args.base_url + "/?source=external")
            await expect(
                page.get_by_role("heading", name="Audit a completed patch")
            ).to_be_visible()
            await page.get_by_label("GitHub owner/repository", exact=True).fill(
                example["repository"]
            )
            await page.get_by_label("Immutable base commit", exact=True).fill(
                example["base_commit"]
            )
            async with page.expect_response(
                lambda r: (
                    r.request.method == "POST" and r.url.endswith("/api/repository-audits/sources")
                ),
                timeout=60000,
            ) as source_response:
                await page.get_by_role("button", name="Fetch source for review", exact=True).click()
            response = await source_response.value
            assert response.status == 201, await response.text()
            await page.get_by_label("Approved production file scope", exact=True).select_option(
                example["approved_paths"]
            )
            await page.get_by_label("External unified diff", exact=True).fill(
                (manifest_path.parent / example["patch"]).read_text()
            )
            await page.get_by_role("button", name="Admit patch for review", exact=True).click()
            review = page.get_by_role("region", name="External candidate review")
            await expect(review).to_be_visible()
            await page.get_by_text("Compare " + example["approved_paths"][0], exact=True).click()
            await expect(page.locator(".monaco-diff-editor:visible")).to_be_visible(timeout=20000)
            await page.get_by_label("Runtime preset", exact=True).select_option(example["runtime"])
            await page.get_by_label("Test command arguments", exact=True).fill(
                json.dumps(example["tests"])
            )
            await page.get_by_label("Selected test scope", exact=True).fill(
                example["test_description"]
            )
            await page.get_by_role(
                "button", name="Prepare exact plan for approval", exact=True
            ).click()
            run = page.get_by_role("button", name="Run approved repository tests", exact=True)
            await expect(run).to_be_disabled()
            await page.screenshot(path=output / f"{key}-review.png", full_page=True)
            if not args.confirm_local_execution:
                continue
            await page.get_by_role(
                "checkbox",
                name="I reviewed this exact source, patch and plan, and approve local execution.",
                exact=True,
            ).check()
            async with page.expect_response(
                lambda r: (
                    r.request.method == "POST" and r.url.endswith("/api/repository-audits/runs")
                )
            ) as started:
                await run.click()
            started_response = await started.value
            assert started_response.status == 202, await started_response.text()
            audit_id = (await started_response.json())["id"]
            region = page.get_by_role("region", name="External audit result")
            await expect(region.get_by_role("status")).to_have_text(
                example["expected_status"].replace("_", " "), timeout=60000
            )
            await expect(region).to_contain_text("Independent checks not configured")
            await region.screenshot(path=output / f"{key}-result.png")
            async with page.expect_download() as download:
                await region.get_by_role("link", name="Download repository evidence").click()
            audit = json.loads(
                await asyncio.to_thread(Path(await (await download.value).path()).read_text)
            )
            assert audit["id"] == audit_id and audit["status"] == example["expected_status"]
            evidence = audit["evidence"]
            decode_files(evidence["snapshot"])
            validate(
                evidence["result"],
                UUID(audit_id),
                evidence["snapshot"],
                evidence["candidate"],
                evidence["plan"],
                evidence["engine_id"],
            )
            (output / f"{key}-browser.json").write_text(json.dumps(audit, indent=2) + "\n")
            saved_url = page.url
            await page.reload()
            await expect(region.get_by_role("status")).to_have_text(
                example["expected_status"].replace("_", " "), timeout=15000
            )
            reopened = await page.request.get(
                args.base_url + "/api/repository-audits/runs/" + audit_id
            )
            assert await reopened.json() == audit
            print(key, audit["status"], saved_url, "browser download validated and reopened")
        assert not errors, errors
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="evaluation/repository-examples/g1/examples.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", default="artifacts/repository-audit/external")
    parser.add_argument("--example")
    parser.add_argument("--confirm-local-execution", action="store_true")
    asyncio.run(main(parser.parse_args()))
