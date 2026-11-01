"""Deterministic delayed-catalog regressions; no fresh candidate execution in these tests."""

import asyncio
import json

import pytest
from playwright.async_api import async_playwright, expect
from test_prepared_browser import ACCEPTED, BASE

pytestmark = pytest.mark.integration


def retained():
    return json.loads(
        next(
            p
            for p in ACCEPTED.glob("python-positive-*.json")
            if "review" not in p.name and "validation" not in p.name
        ).read_text()
    )


@pytest.mark.parametrize("width", [1440, 390])
async def test_manual_edits_survive_delayed_initial_prepared_catalog(width):
    captured = asyncio.Event()
    release = asyncio.Event()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": width, "height": 900})

        async def catalog(route):
            response = await route.fetch()
            captured.set()
            await release.wait()
            await route.fulfill(response=response)

        await page.route("**/api/repository-audits/prepared-examples", catalog)
        await page.goto(BASE + "/?source=external&prepared=python-positive")
        await asyncio.wait_for(captured.wait(), 15)
        await page.get_by_label("GitHub owner/repository", exact=True).fill("manual/project")
        await page.get_by_label("Immutable base commit", exact=True).fill("b" * 40)
        release.set()
        await expect(
            page.get_by_label("Prepared example", exact=True).locator("option")
        ).to_have_count(3)
        await expect(page.get_by_label("GitHub owner/repository", exact=True)).to_have_value(
            "manual/project"
        )
        await expect(page.get_by_label("Immutable base commit", exact=True)).to_have_value("b" * 40)
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value("")
        await expect(page.get_by_label("External audit result", exact=True)).to_have_count(0)
        await page.get_by_label("Prepared example", exact=True).select_option("node-positive")
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value(
            "node-positive"
        )
        await expect(page.get_by_label("GitHub owner/repository", exact=True)).not_to_have_value(
            "manual/project"
        )
        await page.get_by_label("Prepared example", exact=True).select_option("python-positive")
        await expect(page.get_by_label("GitHub owner/repository", exact=True)).to_have_value(
            "hynek/first"
        )
        await expect(page.get_by_label("External candidate review", exact=True)).to_have_count(0)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await browser.close()


async def test_opened_history_survives_late_initial_catalog_and_deep_link_still_wins():
    audit = retained()
    captured = asyncio.Event()
    release = asyncio.Event()
    detail_captured = asyncio.Event()
    release_detail = asyncio.Event()
    mutations = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async def catalog(route):
            response = await route.fetch()
            captured.set()
            await release.wait()
            await route.fulfill(response=response)

        await page.route("**/api/repository-audits/prepared-examples", catalog)
        await page.route(
            "**/api/repository-audits/runs",
            lambda route: route.fulfill(
                json=[
                    {k: audit[k] for k in ("id", "created_at", "status", "candidate_id")}
                    | {"repository": audit["evidence"]["snapshot"]["repository"]}
                ]
            ),
        )

        async def detail(route):
            detail_captured.set()
            await release_detail.wait()
            await route.fulfill(json=audit)

        await page.route("**/api/repository-audits/runs/" + audit["id"], detail)
        page.on(
            "request",
            lambda r: (
                mutations.append(r.url) if r.method not in ("GET", "HEAD", "OPTIONS") else None
            ),
        )
        await page.goto(BASE + "/?source=external&prepared=python-positive")
        await asyncio.wait_for(captured.wait(), 15)
        await page.get_by_role("button", name="Refresh repository history", exact=True).click()
        await page.locator("#repository-history button").filter(has_text=audit["id"]).click()
        region = page.get_by_label("External audit result", exact=True)
        await asyncio.wait_for(detail_captured.wait(), 15)
        release.set()
        await expect(
            page.get_by_label("Prepared example", exact=True).locator("option")
        ).to_have_count(3)
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value("")
        release_detail.set()
        await expect(region.get_by_role("status")).to_have_text("completed")
        await expect(region).to_contain_text(audit["evidence"]["candidate"]["candidate_hash"])
        await page.get_by_label("Prepared example", exact=True).select_option("node-positive")
        await expect(region).to_have_count(0)
        await expect(page.get_by_label("External candidate review", exact=True)).to_have_count(0)
        await page.goto(
            BASE + f"/?source=external&prepared=python-positive&repositoryAudit={audit['id']}"
        )
        await expect(region.get_by_role("status")).to_have_text("completed")
        await expect(page.get_by_label("Prepared example", exact=True)).to_have_value("")
        assert not mutations
        await browser.close()


async def test_late_catalog_failure_preserves_manual_state_and_remains_visible():
    captured = asyncio.Event()
    release = asyncio.Event()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async def catalog(route):
            captured.set()
            await release.wait()
            await route.fulfill(status=503, json={"detail": "Catalog intentionally unavailable"})

        await page.route("**/api/repository-audits/prepared-examples", catalog)
        await page.goto(BASE + "/?source=external&prepared=python-positive")
        await asyncio.wait_for(captured.wait(), 15)
        await page.get_by_label("GitHub owner/repository", exact=True).fill("manual/project")
        release.set()
        await expect(page.get_by_role("alert")).to_contain_text("Catalog intentionally unavailable")
        await expect(page.get_by_label("GitHub owner/repository", exact=True)).to_have_value(
            "manual/project"
        )
        await expect(page.get_by_label("External audit result", exact=True)).to_have_count(0)
        await browser.close()
